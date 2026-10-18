"""Admin dashboard queries and non-destructive shipment archival."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationDecision, AuthorizationEngine, Scope
from nfpl_access_control.models import (
    AbsenceJobOutcome,
    AbsenceNomination,
    AbsenceNominationJob,
    AbsenceNominationStatus,
    AccountStatus,
    Branch,
    Client,
    EditRequestStatus,
    EmployeeAvailability,
    ExceptionalRequestStatus,
    ExceptionalTransitionRequest,
    Job,
    JobDelegation,
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


@dataclass(frozen=True, slots=True)
class AttentionJobItem:
    job_id: str
    reference: str
    client_name: str
    branch_name: str
    stage: JobStage
    version: int
    reasons: list[str]


class DashboardService:
    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)

    @staticmethod
    def _attention_predicate(current_time: datetime):
        assigned = lambda responsibility: exists(  # noqa: E731
            select(JobResponsibility.id).where(
                JobResponsibility.job_id == Job.id,
                JobResponsibility.responsibility == responsibility,
                JobResponsibility.user_id.is_not(None),
            )
        )
        problematic_outcome = exists(
            select(AbsenceNominationJob.id).where(
                AbsenceNominationJob.job_id == Job.id,
                AbsenceNominationJob.outcome.in_(
                    (AbsenceJobOutcome.INELIGIBLE, AbsenceJobOutcome.CONFLICT)
                ),
            )
        )
        effective_absence = exists(
            select(AbsenceNomination.id)
            .where(
                AbsenceNomination.requester_user_id == JobResponsibility.user_id,
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
            .correlate(JobResponsibility)
        )
        active_delegate = exists(
            select(JobDelegation.id)
            .where(
                JobDelegation.job_id == JobResponsibility.job_id,
                JobDelegation.responsibility == JobResponsibility.responsibility,
                JobDelegation.valid_from <= current_time,
                JobDelegation.valid_until > current_time,
                or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > current_time),
            )
            .correlate(JobResponsibility)
        )
        absent_without_cover = exists(
            select(JobResponsibility.id)
            .join(User, User.id == JobResponsibility.user_id)
            .where(
                JobResponsibility.job_id == Job.id,
                or_(User.availability == EmployeeAvailability.ABSENT, effective_absence),
                ~active_delegate,
            )
            .correlate(Job)
        )
        return or_(
            ~assigned(ResponsibilityType.MAKER),
            ~assigned(ResponsibilityType.CHECKER),
            ~assigned(ResponsibilityType.FILING_OFFICER),
            problematic_outcome,
            absent_without_cover,
        )

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
        flagged = int(
            self.session.scalar(
                select(func.count(Job.id)).where(
                    Job.archived_at.is_(None),
                    Job.stage.in_(
                        (
                            JobStage.CONFIRMED,
                            JobStage.PREPARED,
                            JobStage.CHECKED,
                            JobStage.REOPENED,
                        )
                    ),
                    self._attention_predicate(current_time),
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
    ) -> list[tuple[Job, str | None, str | None, str | None, str, str]]:
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
        statement = (
            select(
                Job,
                assignee(ResponsibilityType.MAKER),
                assignee(ResponsibilityType.CHECKER),
                assignee(ResponsibilityType.FILING_OFFICER),
                Client.name,
                Branch.name,
            )
            .join(Client, Client.id == Job.client_id)
            .join(Branch, Branch.id == Job.branch_id)
        )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Job.id.ilike(pattern),
                    Job.reference.ilike(pattern),
                    Client.name.ilike(pattern),
                    Job.goods_description.ilike(pattern),
                )
            )
        return list(
            self.session.execute(
                statement.order_by(Job.updated_at.desc(), Job.id.desc()).offset(offset).limit(limit)
            ).all()
        )

    def attention_jobs(
        self,
        *,
        actor: User,
        limit: int = 25,
        cursor: str | None = None,
        now: datetime | None = None,
    ) -> tuple[list[AttentionJobItem], str | None]:
        current_time = now or datetime.now(UTC)
        self._require_admin(actor, current_time)
        if limit not in range(1, 101):
            raise ValueError("Attention pagination is invalid.")
        statement = (
            select(Job, Client.name, Branch.name)
            .join(Client, Client.id == Job.client_id)
            .join(Branch, Branch.id == Job.branch_id)
            .where(
                Job.archived_at.is_(None),
                Job.stage.in_(
                    (JobStage.CONFIRMED, JobStage.PREPARED, JobStage.CHECKED, JobStage.REOPENED)
                ),
                self._attention_predicate(current_time),
            )
        )
        if cursor is not None:
            updated_at, job_id = self._decode_attention_cursor(cursor)
            statement = statement.where(
                or_(
                    Job.updated_at < updated_at,
                    and_(Job.updated_at == updated_at, Job.id < job_id),
                )
            )
        rows = self.session.execute(
            statement.order_by(Job.updated_at.desc(), Job.id.desc()).limit(limit + 1)
        ).all()
        visible = rows[:limit]
        reasons = self._attention_reasons([row[0].id for row in visible], current_time)
        items = [
            AttentionJobItem(
                job_id=row[0].id,
                reference=row[0].reference,
                client_name=row[1],
                branch_name=row[2],
                stage=row[0].stage,
                version=row[0].version,
                reasons=reasons.get(row[0].id, ["Assignment review required."]),
            )
            for row in visible
        ]
        next_cursor = None
        if len(rows) > limit and visible:
            next_cursor = self._encode_attention_cursor(visible[-1][0])
        return items, next_cursor

    @staticmethod
    def _encode_attention_cursor(job: Job) -> str:
        value = f"{job.updated_at.isoformat()}|{job.id}"
        return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    @staticmethod
    def _decode_attention_cursor(cursor: str) -> tuple[datetime, str]:
        try:
            value = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
            updated_value, job_id = value.split("|", 1)
            updated_at = datetime.fromisoformat(updated_value)
            if updated_at.tzinfo is None or updated_at.utcoffset() is None or not job_id:
                raise ValueError
        except (ValueError, UnicodeDecodeError, binascii.Error) as error:
            raise ValueError("Attention cursor is invalid.") from error
        return updated_at, job_id

    def _attention_reasons(
        self, job_ids: list[str], current_time: datetime
    ) -> dict[str, list[str]]:
        if not job_ids:
            return {}
        responsibility_rows = self.session.execute(
            select(JobResponsibility, User)
            .outerjoin(User, User.id == JobResponsibility.user_id)
            .where(JobResponsibility.job_id.in_(job_ids))
        ).all()
        active_delegations = set(
            self.session.execute(
                select(JobDelegation.job_id, JobDelegation.responsibility).where(
                    JobDelegation.job_id.in_(job_ids),
                    JobDelegation.valid_from <= current_time,
                    JobDelegation.valid_until > current_time,
                    or_(
                        JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > current_time
                    ),
                )
            ).all()
        )
        assigned_user_ids = [row[1].id for row in responsibility_rows if row[1] is not None]
        absent_user_ids = {
            row[1].id
            for row in responsibility_rows
            if row[1] is not None and row[1].availability is EmployeeAvailability.ABSENT
        }
        if assigned_user_ids:
            absent_user_ids.update(
                self.session.scalars(
                    select(AbsenceNomination.requester_user_id).where(
                        AbsenceNomination.requester_user_id.in_(assigned_user_ids),
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
            )
        outcomes = self.session.scalars(
            select(AbsenceNominationJob).where(
                AbsenceNominationJob.job_id.in_(job_ids),
                AbsenceNominationJob.outcome.in_(
                    (AbsenceJobOutcome.INELIGIBLE, AbsenceJobOutcome.CONFLICT)
                ),
            )
        )
        return self._format_attention_reasons(
            job_ids,
            responsibility_rows,
            active_delegations,
            absent_user_ids,
            list(outcomes),
        )

    @staticmethod
    def _format_attention_reasons(
        job_ids: list[str],
        responsibility_rows: list,
        active_delegations: set[tuple[str, ResponsibilityType]],
        absent_user_ids: set[str],
        outcomes: list[AbsenceNominationJob],
    ) -> dict[str, list[str]]:
        reasons = {job_id: [] for job_id in job_ids}
        assignments = {
            (responsibility.job_id, responsibility.responsibility): (responsibility, user)
            for responsibility, user in responsibility_rows
        }
        labels = {
            ResponsibilityType.MAKER: "Maker",
            ResponsibilityType.CHECKER: "Checker",
            ResponsibilityType.FILING_OFFICER: "Filing Officer",
        }
        for job_id in job_ids:
            for responsibility_type, label in labels.items():
                assignment = assignments.get((job_id, responsibility_type))
                if assignment is None or assignment[0].user_id is None:
                    reasons[job_id].append(f"Missing {label} assignment.")
                    continue
                employee = assignment[1]
                if (
                    employee is not None
                    and employee.id in absent_user_ids
                    and (job_id, responsibility_type) not in active_delegations
                ):
                    reasons[job_id].append(
                        f"{label} {employee.display_name} is absent without an "
                        "effective replacement."
                    )
        for outcome in outcomes:
            label = labels[outcome.responsibility]
            reasons[outcome.job_id].append(
                f"Nominated {label} replacement is {outcome.outcome.value}: {outcome.reason}"
            )
        return {job_id: list(dict.fromkeys(items)) for job_id, items in reasons.items() if items}

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
