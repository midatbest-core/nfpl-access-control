"""Employee absence nominations and authorization-bounded bulk delegation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import (
    AuthorizationDecision,
    AuthorizationEngine,
    ReasonCode,
    Scope,
)
from nfpl_access_control.models import (
    AbsenceJobOutcome,
    AbsenceNomination,
    AbsenceNominationJob,
    AbsenceNominationStatus,
    AccountStatus,
    EmployeeAvailability,
    Job,
    JobDelegation,
    JobResponsibility,
    JobResponsibilityEvent,
    JobStage,
    Notification,
    Permission,
    ResponsibilityEventType,
    ResponsibilityType,
    User,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService
from nfpl_access_control.services.notifications import NotificationService

RESPONSIBILITY_PERMISSION = {
    ResponsibilityType.MAKER: Permission.JOB_PREPARE,
    ResponsibilityType.CHECKER: Permission.JOB_CHECK,
    ResponsibilityType.FILING_OFFICER: Permission.JOB_FILE,
}
ACTIVE_JOB_STAGES = (
    JobStage.CONFIRMED,
    JobStage.PREPARED,
    JobStage.CHECKED,
    JobStage.REOPENED,
)


class AbsenceError(Exception):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.explanation)
        self.decision = decision


class AbsenceConflictError(RuntimeError):
    pass


class AbsenceValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AbsenceCandidate:
    user_id: str
    display_name: str
    eligible_assignment_count: int
    total_assignment_count: int


def has_effective_absence(session: Session, user: User, at: datetime) -> bool:
    if user.availability is EmployeeAvailability.ABSENT:
        return True
    return (
        session.scalar(
            select(AbsenceNomination.id).where(
                AbsenceNomination.requester_user_id == user.id,
                AbsenceNomination.status.in_(
                    (AbsenceNominationStatus.APPROVED, AbsenceNominationStatus.REVOKED)
                ),
                AbsenceNomination.decided_at <= at,
                AbsenceNomination.valid_from <= at,
                AbsenceNomination.valid_until > at,
                or_(AbsenceNomination.revoked_at.is_(None), AbsenceNomination.revoked_at > at),
            )
        )
        is not None
    )


class AbsenceService:
    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)

    def candidates(self, actor: User, limit: int = 50) -> list[AbsenceCandidate]:
        current_time = self._time(None)
        return self._candidate_summaries(actor, current_time, limit)

    def _candidate_summaries(
        self, actor: User, current_time: datetime, limit: int
    ) -> list[AbsenceCandidate]:
        if limit not in range(1, 101):
            raise AbsenceValidationError("Candidate limit is invalid.")
        if actor.kind is not UserKind.STAFF or actor.account_status is not AccountStatus.ACTIVE:
            raise AbsenceValidationError("Only an active employee can view candidates.")
        assignments = list(
            self.session.execute(
                select(JobResponsibility, Job)
                .join(Job, Job.id == JobResponsibility.job_id)
                .where(
                    JobResponsibility.user_id == actor.id,
                    Job.stage.in_(ACTIVE_JOB_STAGES),
                    Job.archived_at.is_(None),
                )
            ).all()
        )
        return self._rank_candidates(actor, assignments, current_time, limit)

    def _rank_candidates(
        self,
        actor: User,
        assignments: list[tuple[JobResponsibility, Job]],
        current_time: datetime,
        limit: int,
    ) -> list[AbsenceCandidate]:
        employees = self.session.scalars(
            select(User).where(
                User.id != actor.id,
                User.kind == UserKind.STAFF,
                User.account_status == AccountStatus.ACTIVE,
                User.is_active.is_(True),
                User.availability != EmployeeAvailability.ABSENT,
            )
        )
        candidates: list[AbsenceCandidate] = []
        for employee in employees:
            if has_effective_absence(self.session, employee, current_time):
                continue
            candidates.append(self._candidate(employee, assignments, current_time))
        return self._sort_candidates(candidates, bool(assignments), limit)

    def _candidate(
        self,
        employee: User,
        assignments: list[tuple[JobResponsibility, Job]],
        current_time: datetime,
    ) -> AbsenceCandidate:
        eligible_count = sum(
            self._eligibility(employee, job, responsibility.responsibility, current_time)[0]
            is AbsenceJobOutcome.DELEGATED
            for responsibility, job in assignments
        )
        return AbsenceCandidate(
            user_id=employee.id,
            display_name=employee.display_name,
            eligible_assignment_count=eligible_count,
            total_assignment_count=len(assignments),
        )

    @staticmethod
    def _sort_candidates(
        candidates: list[AbsenceCandidate], has_assignments: bool, limit: int
    ) -> list[AbsenceCandidate]:
        eligible = [
            item for item in candidates if not has_assignments or item.eligible_assignment_count > 0
        ]
        return sorted(
            eligible,
            key=lambda item: (
                -item.eligible_assignment_count,
                item.display_name.casefold(),
                item.user_id,
            ),
        )[:limit]

    def nominate(
        self,
        *,
        actor: User,
        nominee_user_id: str,
        valid_from: datetime,
        valid_until: datetime,
        reason: str,
        now: datetime | None = None,
    ) -> AbsenceNomination:
        current_time = self._time(now)
        self._aware(valid_from)
        self._aware(valid_until)
        if actor.kind is not UserKind.STAFF or actor.account_status is not AccountStatus.ACTIVE:
            raise AbsenceValidationError("Only an active employee can nominate a replacement.")
        if nominee_user_id == actor.id:
            raise AbsenceValidationError("An employee cannot nominate themselves.")
        nominee = self.session.get(User, nominee_user_id)
        if (
            nominee is None
            or nominee.kind is not UserKind.STAFF
            or nominee.account_status is not AccountStatus.ACTIVE
            or not nominee.is_active
            or nominee.availability is EmployeeAvailability.ABSENT
        ):
            raise AbsenceValidationError("The nominee must be an active, non-absent employee.")
        if valid_until <= valid_from or valid_until <= current_time:
            raise AbsenceValidationError("The absence interval must end after it starts and now.")
        if not reason.strip():
            raise AbsenceValidationError("An absence reason is required.")
        self.session.execute(
            select(User.id).where(User.id == actor.id).with_for_update()
        ).scalar_one()
        overlap = self.session.scalar(
            select(AbsenceNomination.id).where(
                AbsenceNomination.requester_user_id == actor.id,
                AbsenceNomination.status.in_(
                    (AbsenceNominationStatus.PENDING, AbsenceNominationStatus.APPROVED)
                ),
                AbsenceNomination.valid_from < valid_until,
                AbsenceNomination.valid_until > valid_from,
            )
        )
        if overlap is not None:
            raise AbsenceConflictError("An overlapping absence nomination already exists.")
        nomination = AbsenceNomination(
            requester_user_id=actor.id,
            nominee_user_id=nominee.id,
            valid_from=valid_from,
            valid_until=valid_until,
            reason=reason.strip(),
            status=AbsenceNominationStatus.PENDING,
            requested_at=current_time,
        )
        self.session.add(nomination)
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="absence.nomination_requested",
            reason=reason.strip(),
            occurred_at=current_time,
            context={
                "nomination_id": nomination.id,
                "nominee_user_id": nominee.id,
                "valid_from": valid_from.isoformat(),
                "valid_until": valid_until.isoformat(),
            },
        )
        return nomination

    def decide(
        self,
        *,
        actor: User,
        nomination: AbsenceNomination,
        approved: bool,
        reason: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> AbsenceNomination:
        current_time = self._time(now)
        nomination = self._lock(nomination.id)
        decision = self.authorization.authorize_admin(
            actor, Permission.JOB_UPDATE, requested_scope=Scope.global_scope(), at=current_time
        )
        self._require(decision, actor, "absence.nomination_decision.denied", current_time)
        if actor.id == nomination.requester_user_id:
            self._deny(
                actor,
                ReasonCode.SELF_APPROVAL_FORBIDDEN,
                "An employee cannot approve their own replacement nomination.",
                current_time,
            )
        if nomination.status is not AbsenceNominationStatus.PENDING:
            raise AbsenceConflictError("The nomination is no longer pending.")
        if nomination.version != expected_version:
            self._deny(
                actor,
                ReasonCode.STALE_VERSION,
                "The nomination changed since it was opened.",
                current_time,
            )
        if not reason.strip():
            raise AbsenceValidationError("An Admin decision reason is required.")
        nomination.decided_by_user_id = actor.id
        nomination.decided_at = current_time
        nomination.decision_reason = reason.strip()
        nomination.status = (
            AbsenceNominationStatus.APPROVED if approved else AbsenceNominationStatus.REJECTED
        )
        delegated = 0
        flagged = 0
        if approved:
            delegated, flagged = self._activate(actor, nomination, current_time)
        self.audit.record(
            actor=actor,
            action=("absence.nomination_approved" if approved else "absence.nomination_rejected"),
            reason=reason.strip(),
            occurred_at=current_time,
            decision=decision,
            context={
                "nomination_id": nomination.id,
                "requester_user_id": nomination.requester_user_id,
                "nominee_user_id": nomination.nominee_user_id,
                "delegated_count": delegated,
                "flagged_count": flagged,
            },
        )
        self.session.flush()
        self.notifications.create(
            actor=actor,
            recipient_user_id=nomination.requester_user_id,
            event_type=("absence_approved" if approved else "absence_rejected"),
            message=(
                "Your replacement nomination was approved."
                if approved
                else "Your replacement nomination was rejected."
            ),
            target_path="/v1/absence-nominations",
            dedupe_key=f"absence:{nomination.id}:decision:{nomination.version}",
            now=current_time,
        )
        self.session.execute(
            update(Notification)
            .where(
                Notification.dedupe_key.like(f"absence:{nomination.id}:%"),
                Notification.read_at.is_(None),
            )
            .values(read_at=current_time)
        )
        return nomination

    def revoke(
        self,
        *,
        actor: User,
        nomination: AbsenceNomination,
        reason: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> AbsenceNomination:
        current_time = self._time(now)
        nomination = self._lock(nomination.id)
        decision = self.authorization.authorize_admin(
            actor, Permission.JOB_UPDATE, requested_scope=Scope.global_scope(), at=current_time
        )
        self._require(decision, actor, "absence.nomination_revoke.denied", current_time)
        if nomination.status is not AbsenceNominationStatus.APPROVED:
            raise AbsenceConflictError("Only an approved nomination can be revoked.")
        if nomination.version != expected_version:
            self._deny(actor, ReasonCode.STALE_VERSION, "The nomination is stale.", current_time)
        if not reason.strip():
            raise AbsenceValidationError("A revocation reason is required.")
        nomination.status = AbsenceNominationStatus.REVOKED
        nomination.revoked_at = current_time
        delegations = self.session.scalars(
            select(JobDelegation).where(
                JobDelegation.absence_nomination_id == nomination.id,
                JobDelegation.revoked_at.is_(None),
            )
        )
        for delegation in delegations:
            delegation.revoked_at = current_time
            job = self.session.get(Job, delegation.job_id)
            self.session.add(
                JobResponsibilityEvent(
                    job_id=delegation.job_id,
                    responsibility=delegation.responsibility,
                    event_type=ResponsibilityEventType.DELEGATION_REVOKED,
                    previous_user_id=delegation.delegate_user_id,
                    new_user_id=nomination.requester_user_id,
                    actor_user_id=actor.id,
                    occurred_at=current_time,
                    reason=reason.strip(),
                )
            )
            self.audit.record(
                actor=actor,
                action="absence.delegation_revoked",
                reason=reason.strip(),
                occurred_at=current_time,
                job=job,
                decision=decision,
                context={
                    "nomination_id": nomination.id,
                    "delegation_id": delegation.id,
                    "responsibility": delegation.responsibility.value,
                },
            )
            self.notifications.create(
                actor=actor,
                recipient_user_id=delegation.delegate_user_id,
                event_type="delegation_revoked",
                message="Temporary absence coverage was ended.",
                target_path="/v1/my-work",
                dedupe_key=f"absence:{nomination.id}:{delegation.id}:revoked",
                job=job,
                now=current_time,
            )
        self.audit.record(
            actor=actor,
            action="absence.nomination_revoked",
            reason=reason.strip(),
            occurred_at=current_time,
            decision=decision,
            context={"nomination_id": nomination.id},
        )
        self.session.flush()
        return nomination

    def override_job(
        self,
        *,
        actor: User,
        outcome: AbsenceNominationJob,
        replacement_user_id: str,
        reason: str,
        now: datetime | None = None,
    ) -> AbsenceNominationJob:
        current_time = self._time(now)
        locked = self.session.scalar(
            select(AbsenceNominationJob)
            .where(AbsenceNominationJob.id == outcome.id)
            .with_for_update()
        )
        if locked is None:
            raise AbsenceValidationError("The absence job outcome no longer exists.")
        outcome = locked
        nomination = self._lock(outcome.nomination_id)
        job = self.session.get(Job, outcome.job_id)
        replacement = self.session.get(User, replacement_user_id)
        if job is None or replacement is None:
            raise AbsenceValidationError("The job or replacement no longer exists.")
        decision = self.authorization.authorize_admin(
            actor, Permission.JOB_UPDATE, requested_scope=Scope.for_job(job), at=current_time
        )
        self._require(decision, actor, "absence.override.denied", current_time)
        if nomination.status is not AbsenceNominationStatus.APPROVED:
            raise AbsenceConflictError("Only an approved nomination can be overridden.")
        if nomination.valid_until <= current_time:
            raise AbsenceConflictError("The absence delegation interval has expired.")
        if not reason.strip():
            raise AbsenceValidationError("An override reason is required.")
        self._lock_responsibility(job.id, outcome.responsibility)
        eligible, explanation = self._eligibility(
            replacement, job, outcome.responsibility, current_time
        )
        if eligible is not AbsenceJobOutcome.DELEGATED:
            raise AbsenceValidationError(f"Replacement is ineligible: {explanation}")
        if outcome.delegation_id is not None:
            previous = self.session.get(JobDelegation, outcome.delegation_id)
            if previous is not None and previous.revoked_at is None:
                previous.revoked_at = current_time
        if self._has_overlap(
            job.id,
            outcome.responsibility,
            current_time,
            nomination.valid_until,
            exclude_delegation_id=outcome.delegation_id,
        ):
            raise AbsenceConflictError("A conflicting active delegation already exists.")
        delegation = JobDelegation(
            job_id=job.id,
            responsibility=outcome.responsibility,
            delegator_user_id=nomination.requester_user_id,
            delegate_user_id=replacement.id,
            valid_from=current_time,
            valid_until=nomination.valid_until,
            created_by_user_id=actor.id,
            reason=reason.strip(),
            absence_nomination_id=nomination.id,
        )
        self.session.add(delegation)
        self.session.flush()
        outcome.nominee_user_id = replacement.id
        outcome.outcome = AbsenceJobOutcome.OVERRIDDEN
        outcome.reason = reason.strip()
        outcome.delegation_id = delegation.id
        self.session.add(
            JobResponsibilityEvent(
                job_id=job.id,
                responsibility=outcome.responsibility,
                event_type=ResponsibilityEventType.DELEGATED,
                previous_user_id=nomination.requester_user_id,
                new_user_id=replacement.id,
                actor_user_id=actor.id,
                occurred_at=current_time,
                reason=reason.strip(),
            )
        )
        self.audit.record(
            actor=actor,
            action="absence.delegation_overridden",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            decision=decision,
            context={
                "nomination_id": nomination.id,
                "outcome_id": outcome.id,
                "replacement_user_id": replacement.id,
            },
        )
        self.notifications.create(
            actor=actor,
            recipient_user_id=replacement.id,
            event_type="job_delegated",
            message=f"Temporary {outcome.responsibility.value} work was delegated to you.",
            target_path=f"/v1/jobs/{job.id}",
            dedupe_key=f"absence-override:{outcome.id}:{delegation.id}",
            job=job,
            now=current_time,
        )
        self.session.flush()
        return outcome

    def _activate(
        self, actor: User, nomination: AbsenceNomination, at: datetime
    ) -> tuple[int, int]:
        nominee = self.session.get(User, nomination.nominee_user_id)
        if nominee is None:
            raise AbsenceValidationError("The nominated replacement no longer exists.")
        records = self.session.execute(
            select(JobResponsibility, Job)
            .join(Job, Job.id == JobResponsibility.job_id)
            .where(
                JobResponsibility.user_id == nomination.requester_user_id,
                Job.stage.in_(ACTIVE_JOB_STAGES),
                Job.archived_at.is_(None),
            )
            .order_by(JobResponsibility.assigned_at, JobResponsibility.id)
            .with_for_update()
        ).all()
        delegated = 0
        flagged = 0
        for responsibility, job in records:
            outcome, explanation = self._eligibility(
                nominee, job, responsibility.responsibility, at
            )
            if outcome is AbsenceJobOutcome.DELEGATED and self._has_overlap(
                job.id, responsibility.responsibility, nomination.valid_from, nomination.valid_until
            ):
                outcome = AbsenceJobOutcome.CONFLICT
                explanation = "An overlapping active delegation already exists."
            result = AbsenceNominationJob(
                nomination_id=nomination.id,
                job_id=job.id,
                responsibility=responsibility.responsibility,
                nominee_user_id=nominee.id,
                outcome=outcome,
                reason=explanation,
            )
            self.session.add(result)
            if outcome is not AbsenceJobOutcome.DELEGATED:
                flagged += 1
                continue
            delegation = JobDelegation(
                job_id=job.id,
                responsibility=responsibility.responsibility,
                delegator_user_id=nomination.requester_user_id,
                delegate_user_id=nominee.id,
                valid_from=nomination.valid_from,
                valid_until=nomination.valid_until,
                created_by_user_id=actor.id,
                reason=nomination.reason,
                absence_nomination_id=nomination.id,
            )
            self.session.add(delegation)
            self.session.flush()
            result.delegation_id = delegation.id
            delegated += 1
            self.session.add(
                JobResponsibilityEvent(
                    job_id=job.id,
                    responsibility=responsibility.responsibility,
                    event_type=ResponsibilityEventType.DELEGATED,
                    previous_user_id=nomination.requester_user_id,
                    new_user_id=nominee.id,
                    actor_user_id=actor.id,
                    occurred_at=at,
                    reason=nomination.reason,
                )
            )
            self.audit.record(
                actor=actor,
                action="absence.delegation_activated",
                reason=nomination.reason,
                occurred_at=at,
                job=job,
                context={
                    "nomination_id": nomination.id,
                    "responsibility": responsibility.responsibility.value,
                    "delegate_user_id": nominee.id,
                },
            )
            self.notifications.create(
                actor=actor,
                recipient_user_id=nominee.id,
                event_type="job_delegated",
                message=(
                    f"Temporary {responsibility.responsibility.value} work was delegated to you."
                ),
                target_path=f"/v1/jobs/{job.id}",
                dedupe_key=f"absence:{nomination.id}:{job.id}:{responsibility.responsibility.value}",
                job=job,
                now=at,
            )
        return delegated, flagged

    def _eligibility(
        self, nominee: User, job: Job, responsibility: ResponsibilityType, at: datetime
    ) -> tuple[AbsenceJobOutcome, str]:
        if (
            not nominee.is_active
            or nominee.account_status is not AccountStatus.ACTIVE
            or nominee.kind is not UserKind.STAFF
            or has_effective_absence(self.session, nominee, at)
        ):
            return AbsenceJobOutcome.INELIGIBLE, "Replacement is not active and available."
        decision = self.authorization.authorize_job(
            nominee, RESPONSIBILITY_PERMISSION[responsibility], job, at=at
        )
        if not decision.allowed:
            return AbsenceJobOutcome.INELIGIBLE, decision.explanation
        if responsibility is ResponsibilityType.CHECKER and job.prepared_by_user_id == nominee.id:
            return AbsenceJobOutcome.INELIGIBLE, "The preparer cannot receive Checker delegation."
        return AbsenceJobOutcome.DELEGATED, "Replacement is eligible."

    def _has_overlap(
        self,
        job_id: str,
        responsibility: ResponsibilityType,
        valid_from: datetime,
        valid_until: datetime,
        exclude_delegation_id: str | None = None,
    ) -> bool:
        statement = select(JobDelegation.id).where(
            JobDelegation.job_id == job_id,
            JobDelegation.responsibility == responsibility,
            JobDelegation.valid_from < valid_until,
            JobDelegation.valid_until > valid_from,
            JobDelegation.revoked_at.is_(None),
        )
        if exclude_delegation_id is not None:
            statement = statement.where(JobDelegation.id != exclude_delegation_id)
        return self.session.scalar(statement) is not None

    def _lock(self, nomination_id: str) -> AbsenceNomination:
        nomination = self.session.scalar(
            select(AbsenceNomination).where(AbsenceNomination.id == nomination_id).with_for_update()
        )
        if nomination is None:
            raise AbsenceValidationError("The nomination no longer exists.")
        return nomination

    def _lock_responsibility(
        self, job_id: str, responsibility: ResponsibilityType
    ) -> JobResponsibility:
        record = self.session.scalar(
            select(JobResponsibility)
            .where(
                JobResponsibility.job_id == job_id,
                JobResponsibility.responsibility == responsibility,
            )
            .with_for_update()
        )
        if record is None or record.user_id is None:
            raise AbsenceValidationError("The job responsibility is no longer assigned.")
        return record

    def _require(
        self,
        decision: AuthorizationDecision,
        actor: User,
        action: str,
        at: datetime,
    ) -> None:
        if decision.allowed:
            return
        self.audit.record(
            actor=actor,
            action=action,
            reason=decision.explanation,
            occurred_at=at,
            decision=decision,
        )
        self.session.flush()
        raise AbsenceError(decision)

    def _deny(self, actor: User, code: ReasonCode, explanation: str, at: datetime) -> None:
        self._require(
            AuthorizationDecision(False, code, explanation, Permission.JOB_UPDATE),
            actor,
            "absence.nomination_decision.denied",
            at,
        )

    @staticmethod
    def _time(value: datetime | None) -> datetime:
        result = value or datetime.now(UTC)
        AbsenceService._aware(result)
        return result

    @staticmethod
    def _aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise AbsenceValidationError("Absence timestamps must include a UTC offset.")
