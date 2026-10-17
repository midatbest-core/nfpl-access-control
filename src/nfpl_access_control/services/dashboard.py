"""Admin dashboard queries and non-destructive shipment archival."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationDecision, AuthorizationEngine, Scope
from nfpl_access_control.models import (
    AbsenceJobOutcome,
    AbsenceNomination,
    AbsenceNominationJob,
    AbsenceNominationStatus,
    AccountStatus,
    EditRequestStatus,
    ExceptionalRequestStatus,
    ExceptionalTransitionRequest,
    Job,
    JobEditRequest,
    JobResponsibility,
    JobStage,
    Permission,
    ResponsibilityType,
    User,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService, job_snapshot


class DashboardAccessError(PermissionError):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.explanation)
        self.decision = decision


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    total_jobs: int
    jobs_by_stage: dict[str, int]
    total_employees: int
    employees_by_availability: dict[str, int]
    pending_requests: int
    reassignment_required_jobs: int


@dataclass(frozen=True, slots=True)
class UrgentRequestItem:
    request_type: str
    request_id: str
    requested_at: datetime
    requester_user_id: str
    reason: str
    job_id: str | None
    version: int


class DashboardService:
    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)

    def overview(self, *, actor: User, now: datetime | None = None) -> DashboardOverview:
        current_time = now or datetime.now(UTC)
        self._require_admin(actor, current_time)
        stage_rows = self.session.execute(
            select(Job.stage, func.count(Job.id))
            .where(Job.archived_at.is_(None))
            .group_by(Job.stage)
        ).all()
        effective_absence = exists(
            select(AbsenceNomination.id).where(
                AbsenceNomination.requester_user_id == User.id,
                AbsenceNomination.status.in_(
                    (AbsenceNominationStatus.APPROVED, AbsenceNominationStatus.REVOKED)
                ),
                AbsenceNomination.decided_at <= current_time,
                AbsenceNomination.valid_from <= current_time,
                AbsenceNomination.valid_until > current_time,
                or_(
                    AbsenceNomination.revoked_at.is_(None),
                    AbsenceNomination.revoked_at > current_time,
                ),
            )
        )
        effective_availability = case((effective_absence, "absent"), else_=User.availability).label(
            "effective_availability"
        )
        availability_rows = self.session.execute(
            select(effective_availability, func.count(User.id))
            .where(
                User.kind == UserKind.STAFF,
                User.account_status == AccountStatus.ACTIVE,
                User.is_active.is_(True),
            )
            .group_by(effective_availability)
        ).all()
        pending = sum(
            int(value or 0)
            for value in (
                self.session.scalar(
                    select(func.count(AbsenceNomination.id)).where(
                        AbsenceNomination.status == AbsenceNominationStatus.PENDING
                    )
                ),
                self.session.scalar(
                    select(func.count(JobEditRequest.id)).where(
                        JobEditRequest.status == EditRequestStatus.PENDING
                    )
                ),
                self.session.scalar(
                    select(func.count(ExceptionalTransitionRequest.id)).where(
                        ExceptionalTransitionRequest.status == ExceptionalRequestStatus.PENDING
                    )
                ),
            )
        )
        flagged_job_ids = select(AbsenceNominationJob.job_id).where(
            AbsenceNominationJob.outcome.in_(
                (AbsenceJobOutcome.INELIGIBLE, AbsenceJobOutcome.CONFLICT)
            )
        )
        assigned = lambda responsibility: exists(  # noqa: E731
            select(JobResponsibility.id).where(
                JobResponsibility.job_id == Job.id,
                JobResponsibility.responsibility == responsibility,
                JobResponsibility.user_id.is_not(None),
            )
        )
        flagged = int(
            self.session.scalar(
                select(func.count(Job.id)).where(
                    Job.archived_at.is_(None),
                    or_(
                        ~assigned(ResponsibilityType.MAKER),
                        ~assigned(ResponsibilityType.CHECKER),
                        ~assigned(ResponsibilityType.FILING_OFFICER),
                        Job.id.in_(flagged_job_ids),
                    ),
                )
            )
            or 0
        )
        return DashboardOverview(
            total_jobs=int(
                self.session.scalar(select(func.count(Job.id)).where(Job.archived_at.is_(None)))
                or 0
            ),
            jobs_by_stage={stage.value: count for stage, count in stage_rows},
            total_employees=sum(count for _, count in availability_rows),
            employees_by_availability={str(value): count for value, count in availability_rows},
            pending_requests=pending,
            reassignment_required_jobs=flagged,
        )

    def urgent_requests(
        self, *, actor: User, limit: int = 100, now: datetime | None = None
    ) -> list[UrgentRequestItem]:
        current_time = now or datetime.now(UTC)
        self._require_admin(actor, current_time)
        if not 1 <= limit <= 200:
            raise ValueError("Urgent request limit is invalid.")
        result = [
            UrgentRequestItem(
                "absence_nomination",
                item.id,
                item.requested_at,
                item.requester_user_id,
                item.reason,
                None,
                item.version,
            )
            for item in self.session.scalars(
                select(AbsenceNomination)
                .where(AbsenceNomination.status == AbsenceNominationStatus.PENDING)
                .limit(limit)
            )
        ]
        result.extend(
            UrgentRequestItem(
                "edit_request",
                item.id,
                item.requested_at,
                item.requested_by_user_id,
                item.reason,
                item.job_id,
                item.job.version,
            )
            for item in self.session.scalars(
                select(JobEditRequest)
                .where(JobEditRequest.status == EditRequestStatus.PENDING)
                .limit(limit)
            )
        )
        result.extend(
            UrgentRequestItem(
                "exceptional_transition",
                item.id,
                item.requested_at,
                item.requested_by_user_id,
                item.reason,
                item.job_id,
                item.job.version,
            )
            for item in self.session.scalars(
                select(ExceptionalTransitionRequest)
                .where(ExceptionalTransitionRequest.status == ExceptionalRequestStatus.PENDING)
                .limit(limit)
            )
        )
        return sorted(result, key=lambda item: (item.requested_at, item.request_id))[:limit]

    def list_jobs(
        self,
        *,
        actor: User,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        now: datetime | None = None,
    ) -> list[tuple[Job, str | None, str | None, str | None]]:
        current_time = now or datetime.now(UTC)
        self._require_admin(actor, current_time)
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Job pagination is invalid.")
        assignee = lambda responsibility: (  # noqa: E731
            select(JobResponsibility.user_id)
            .where(
                JobResponsibility.job_id == Job.id,
                JobResponsibility.responsibility == responsibility,
            )
            .correlate(Job)
            .scalar_subquery()
        )
        statement = select(
            Job,
            assignee(ResponsibilityType.MAKER),
            assignee(ResponsibilityType.CHECKER),
            assignee(ResponsibilityType.FILING_OFFICER),
        )
        if search and search.strip():
            statement = statement.where(Job.reference.ilike(f"%{search.strip()}%"))
        return list(
            self.session.execute(
                statement.order_by(Job.updated_at.desc(), Job.id.desc()).offset(offset).limit(limit)
            ).all()
        )

    def archive(
        self,
        *,
        actor: User,
        job: Job,
        expected_version: int,
        reason: str,
        now: datetime | None = None,
    ) -> Job:
        current_time = now or datetime.now(UTC)
        decision = self.authorization.authorize_admin(
            actor, Permission.JOB_UPDATE, requested_scope=Scope.for_job(job), at=current_time
        )
        if not decision.allowed:
            raise DashboardAccessError(decision)
        if job.version != expected_version:
            raise ValueError("The job changed since it was opened.")
        if job.stage not in {JobStage.FILED, JobStage.CANCELLED}:
            raise ValueError("Only filed or cancelled jobs can be archived.")
        if job.archived_at is not None:
            raise ValueError("The job is already archived.")
        if not reason.strip():
            raise ValueError("An archive reason is required.")
        before = job_snapshot(job)
        job.archived_at = current_time
        job.archived_by_user_id = actor.id
        job.archive_reason = reason.strip()
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.archived",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job

    def _require_admin(self, actor: User, at: datetime) -> None:
        decision = self.authorization.authorize_admin(
            actor, Permission.JOB_VIEW, requested_scope=Scope.global_scope(), at=at
        )
        if not decision.allowed:
            raise DashboardAccessError(decision)
