"""Transactional shipment workflow, responsibility, and assignment use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import (
    AuthorizationDecision,
    AuthorizationEngine,
    ReasonCode,
    Scope,
)
from nfpl_access_control.models import (
    EmployeeAvailability,
    ExceptionalAction,
    ExceptionalRequestStatus,
    ExceptionalTransitionRequest,
    Job,
    JobDelegation,
    JobDirection,
    JobMode,
    JobResponsibility,
    JobResponsibilityEvent,
    JobStage,
    Permission,
    ResponsibilityEventType,
    ResponsibilityType,
    RoleAssignment,
    RolePermission,
    User,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService, job_snapshot

RESPONSIBILITY_PERMISSION = {
    ResponsibilityType.MAKER: Permission.JOB_PREPARE,
    ResponsibilityType.CHECKER: Permission.JOB_CHECK,
    ResponsibilityType.FILING_OFFICER: Permission.JOB_FILE,
}
OPEN_STAGES = (
    JobStage.CONFIRMED,
    JobStage.PREPARED,
    JobStage.CHECKED,
    JobStage.REOPENED,
)


class WorkflowError(Exception):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.explanation)
        self.decision = decision


class WorkflowValidationError(ValueError):
    pass


class WorkflowConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AssignmentSuggestion:
    responsibility: ResponsibilityType
    user_id: str
    display_name: str
    pending_workload: int


class WorkflowService:
    """Mutate a job only inside the caller-owned database transaction."""

    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)

    def create_job(
        self,
        *,
        actor: User,
        reference: str,
        client_id: str,
        branch_id: str,
        direction: JobDirection,
        mode: JobMode,
        goods_description: str = "",
        container_reference: str | None = None,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        scope = self._scope(client_id, branch_id, direction, mode)
        decision = self.authorization.authorize_scope(
            actor, Permission.JOB_CREATE, scope, at=current_time
        )
        self._require(decision, actor, "job.create.denied", current_time)
        if not reference.strip():
            raise WorkflowValidationError("Shipment reference is required.")
        job = Job(
            reference=reference.strip(),
            client_id=client_id,
            branch_id=branch_id,
            direction=direction,
            mode=mode,
            goods_description=goods_description.strip(),
            container_reference=self._optional_text(container_reference),
        )
        self.session.add(job)
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.created",
            reason="Shipment job created.",
            occurred_at=current_time,
            job=job,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job

    def check(
        self,
        *,
        actor: User,
        job: Job,
        approved: bool,
        reason: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        decision = self.authorization.authorize_job(
            actor, Permission.JOB_CHECK, job, at=current_time
        )
        self._require(decision, actor, "job.check.denied", current_time, job)
        self._require_responsibility(
            actor, job, ResponsibilityType.CHECKER, Permission.JOB_CHECK, current_time
        )
        self._require_version(job, expected_version, Permission.JOB_CHECK)
        if job.stage is not JobStage.PREPARED:
            self._stage_error(Permission.JOB_CHECK, "Only prepared jobs can be checked.")
        if job.prepared_by_user_id is None:
            self._stage_error(
                Permission.JOB_CHECK, "The current revision has no recorded preparer."
            )
        if job.prepared_by_user_id == actor.id:
            self._deny(
                actor,
                job,
                Permission.JOB_CHECK,
                ReasonCode.SELF_CHECK_FORBIDDEN,
                "You cannot verify a checklist revision that you prepared.",
                "job.check.denied",
                current_time,
            )
        if not approved and not reason.strip():
            raise WorkflowValidationError("A rejection reason is required.")
        before = job_snapshot(job)
        if approved:
            job.stage = JobStage.CHECKED
            job.checked_by_user_id = actor.id
            job.checked_at = current_time
            action = "job.checked"
        else:
            job.stage = JobStage.CONFIRMED
            job.checked_by_user_id = None
            job.checked_at = None
            action = "job.check_rejected"
        self.session.flush()
        self.audit.record(
            actor=actor,
            action=action,
            reason=reason.strip() or "Checklist independently verified.",
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job

    def file(
        self,
        *,
        actor: User,
        job: Job,
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        decision = self.authorization.authorize_job(
            actor, Permission.JOB_FILE, job, at=current_time
        )
        self._require(decision, actor, "job.file.denied", current_time, job)
        self._require_responsibility(
            actor, job, ResponsibilityType.FILING_OFFICER, Permission.JOB_FILE, current_time
        )
        self._require_version(job, expected_version, Permission.JOB_FILE)
        if job.stage is not JobStage.CHECKED or job.checked_by_user_id is None:
            self._stage_error(Permission.JOB_FILE, "Only independently checked jobs can be filed.")
        before = job_snapshot(job)
        job.stage = JobStage.FILED
        job.filed_by_user_id = actor.id
        job.filed_at = current_time
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.filed",
            reason="Independently checked shipment filed.",
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job

    def assign(
        self,
        *,
        actor: User,
        job: Job,
        responsibility: ResponsibilityType,
        target_user_id: str | None,
        reason: str,
        now: datetime | None = None,
    ) -> JobResponsibility:
        current_time = self._time(now)
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_UPDATE,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        self._require(decision, actor, "job.assignment.denied", current_time, job)
        if not reason.strip():
            raise WorkflowValidationError("An assignment reason is required.")
        if target_user_id is not None:
            target = self.session.get(User, target_user_id)
            self._validate_candidate(target, job, responsibility, current_time)
            if responsibility is ResponsibilityType.CHECKER:
                maker = self._responsibility(job.id, ResponsibilityType.MAKER)
                if maker is not None and maker.user_id == target_user_id:
                    raise WorkflowValidationError(
                        "The same employee cannot be assigned as Maker and Checker."
                    )
        record = self._responsibility(job.id, responsibility)
        previous_user_id = record.user_id if record else None
        if record is None:
            record = JobResponsibility(
                job_id=job.id,
                responsibility=responsibility,
                user_id=target_user_id,
                assigned_by_user_id=actor.id,
                assigned_at=current_time,
            )
            self.session.add(record)
            event_type = ResponsibilityEventType.ASSIGNED
        else:
            record.user_id = target_user_id
            record.assigned_by_user_id = actor.id
            record.assigned_at = current_time
            event_type = (
                ResponsibilityEventType.UNASSIGNED
                if target_user_id is None
                else ResponsibilityEventType.REASSIGNED
            )
        self.session.add(
            JobResponsibilityEvent(
                job_id=job.id,
                responsibility=responsibility,
                event_type=event_type,
                previous_user_id=previous_user_id,
                new_user_id=target_user_id,
                actor_user_id=actor.id,
                occurred_at=current_time,
                reason=reason.strip(),
            )
        )
        self.audit.record(
            actor=actor,
            action=f"job.{event_type.value}",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            decision=decision,
            context={
                "responsibility": responsibility.value,
                "previous_user_id": previous_user_id,
                "new_user_id": target_user_id,
            },
        )
        self.session.flush()
        return record

    def delegate(
        self,
        *,
        actor: User,
        job: Job,
        responsibility: ResponsibilityType,
        delegate_user_id: str,
        valid_from: datetime,
        valid_until: datetime,
        reason: str,
        now: datetime | None = None,
    ) -> JobDelegation:
        current_time = self._time(now)
        self._aware(valid_from, "valid_from")
        self._aware(valid_until, "valid_until")
        if valid_until <= valid_from:
            raise WorkflowValidationError("Delegation end must be later than its start.")
        if not reason.strip():
            raise WorkflowValidationError("A delegation reason is required.")
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_UPDATE,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        self._require(decision, actor, "job.delegation.denied", current_time, job)
        responsibility_record = self._responsibility(job.id, responsibility)
        if responsibility_record is None or responsibility_record.user_id is None:
            raise WorkflowValidationError("The responsibility must be assigned before delegation.")
        delegate = self.session.get(User, delegate_user_id)
        self._validate_candidate(delegate, job, responsibility, current_time)
        if (
            responsibility is ResponsibilityType.CHECKER
            and job.prepared_by_user_id == delegate_user_id
        ):
            raise WorkflowValidationError("The current preparer cannot receive Checker delegation.")
        delegation = JobDelegation(
            job_id=job.id,
            responsibility=responsibility,
            delegator_user_id=responsibility_record.user_id,
            delegate_user_id=delegate_user_id,
            valid_from=valid_from,
            valid_until=valid_until,
            created_by_user_id=actor.id,
            reason=reason.strip(),
        )
        self.session.add(delegation)
        self.session.add(
            JobResponsibilityEvent(
                job_id=job.id,
                responsibility=responsibility,
                event_type=ResponsibilityEventType.DELEGATED,
                previous_user_id=responsibility_record.user_id,
                new_user_id=delegate_user_id,
                actor_user_id=actor.id,
                occurred_at=current_time,
                reason=reason.strip(),
            )
        )
        self.audit.record(
            actor=actor,
            action="job.delegated",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            decision=decision,
            context={
                "responsibility": responsibility.value,
                "delegate_user_id": delegate_user_id,
                "valid_from": valid_from.isoformat(),
                "valid_until": valid_until.isoformat(),
            },
        )
        self.session.flush()
        return delegation

    def revoke_delegation(
        self,
        *,
        actor: User,
        delegation: JobDelegation,
        reason: str,
        now: datetime | None = None,
    ) -> JobDelegation:
        current_time = self._time(now)
        job = self.session.get(Job, delegation.job_id)
        if job is None:
            raise WorkflowValidationError("The delegation has no job.")
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_UPDATE,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        self._require(decision, actor, "job.delegation_revoke.denied", current_time, job)
        if delegation.revoked_at is not None:
            raise WorkflowConflictError("The delegation is already revoked.")
        if not reason.strip():
            raise WorkflowValidationError("A delegation revocation reason is required.")
        delegation.revoked_at = current_time
        self.session.add(
            JobResponsibilityEvent(
                job_id=job.id,
                responsibility=delegation.responsibility,
                event_type=ResponsibilityEventType.DELEGATION_REVOKED,
                previous_user_id=delegation.delegate_user_id,
                new_user_id=None,
                actor_user_id=actor.id,
                occurred_at=current_time,
                reason=reason.strip(),
            )
        )
        self.audit.record(
            actor=actor,
            action="job.delegation_revoked",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            decision=decision,
            context={"delegation_id": delegation.id},
        )
        self.session.flush()
        return delegation

    def suggestions(
        self,
        *,
        actor: User,
        job: Job,
        limit_per_role: int = 5,
        now: datetime | None = None,
    ) -> dict[ResponsibilityType, list[AssignmentSuggestion]]:
        current_time = self._time(now)
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_UPDATE,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        self._require(decision, actor, "job.suggestions.denied", current_time, job)
        if not 1 <= limit_per_role <= 20:
            raise WorkflowValidationError("Suggestion limit must be between 1 and 20.")
        result: dict[ResponsibilityType, list[AssignmentSuggestion]] = {}
        selected_maker_ids: set[str] = set()
        for responsibility in ResponsibilityType:
            excluded = selected_maker_ids if responsibility is ResponsibilityType.CHECKER else set()
            candidates = self._eligible_candidates(
                job, responsibility, current_time, limit_per_role, excluded
            )
            result[responsibility] = candidates
            if responsibility is ResponsibilityType.MAKER and candidates:
                selected_maker_ids = {candidates[0].user_id}
        return result

    def cancel(
        self,
        *,
        actor: User,
        job: Job,
        reason: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        if job.stage is JobStage.FILED:
            self._deny(
                actor,
                job,
                Permission.JOB_CANCEL,
                ReasonCode.INDEPENDENT_APPROVAL_REQUIRED,
                "Cancelling a filed job requires approval by a different Admin.",
                "job.cancel.denied",
                current_time,
            )
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_CANCEL,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        self._require(decision, actor, "job.cancel.denied", current_time, job)
        self._require_version(job, expected_version, Permission.JOB_CANCEL)
        if job.stage is JobStage.CANCELLED:
            self._stage_error(Permission.JOB_CANCEL, "The job is already cancelled.")
        if not reason.strip():
            raise WorkflowValidationError("A cancellation reason is required.")
        before = job_snapshot(job)
        job.stage = JobStage.CANCELLED
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.cancelled",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job

    def request_exception(
        self,
        *,
        actor: User,
        job: Job,
        action: ExceptionalAction,
        reason: str,
        now: datetime | None = None,
    ) -> ExceptionalTransitionRequest:
        current_time = self._time(now)
        permission = (
            Permission.JOB_CANCEL if action is ExceptionalAction.CANCEL else Permission.JOB_REOPEN
        )
        decision = self.authorization.authorize_admin(
            actor, permission, requested_scope=Scope.for_job(job), at=current_time
        )
        self._require(decision, actor, "job.exception.denied", current_time, job)
        if not reason.strip():
            raise WorkflowValidationError("An exceptional transition reason is required.")
        if action is ExceptionalAction.CANCEL and job.stage is not JobStage.FILED:
            raise WorkflowValidationError("Independent cancellation approval is for filed jobs.")
        if action is ExceptionalAction.REOPEN and job.stage not in {
            JobStage.FILED,
            JobStage.CANCELLED,
        }:
            raise WorkflowValidationError("Only filed or cancelled jobs can be reopened.")
        existing = self.session.scalar(
            select(ExceptionalTransitionRequest.id).where(
                ExceptionalTransitionRequest.job_id == job.id,
                ExceptionalTransitionRequest.action == action,
                ExceptionalTransitionRequest.status == ExceptionalRequestStatus.PENDING,
            )
        )
        if existing:
            raise WorkflowConflictError("An equivalent exceptional request is already pending.")
        request = ExceptionalTransitionRequest(
            job_id=job.id,
            action=action,
            status=ExceptionalRequestStatus.PENDING,
            requested_by_user_id=actor.id,
            requested_at=current_time,
            reason=reason.strip(),
        )
        self.session.add(request)
        self.audit.record(
            actor=actor,
            action=f"job.{action.value}_requested",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            decision=decision,
        )
        self.session.flush()
        return request

    def approve_exception(
        self,
        *,
        actor: User,
        request: ExceptionalTransitionRequest,
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        job = self.session.get(Job, request.job_id)
        if job is None:
            raise WorkflowValidationError("The exceptional request has no job.")
        permission = (
            Permission.JOB_CANCEL
            if request.action is ExceptionalAction.CANCEL
            else Permission.JOB_REOPEN
        )
        decision = self.authorization.authorize_admin(
            actor, permission, requested_scope=Scope.for_job(job), at=current_time
        )
        self._require(decision, actor, "job.exception_approval.denied", current_time, job)
        if actor.id == request.requested_by_user_id:
            self._deny(
                actor,
                job,
                permission,
                ReasonCode.SELF_APPROVAL_FORBIDDEN,
                "The requesting Admin cannot approve this exceptional transition.",
                "job.exception_approval.denied",
                current_time,
            )
        if request.status is not ExceptionalRequestStatus.PENDING:
            raise WorkflowConflictError("The exceptional request is no longer pending.")
        self._require_version(job, expected_version, permission)
        before = job_snapshot(job)
        if request.action is ExceptionalAction.CANCEL:
            if job.stage is not JobStage.FILED:
                self._stage_error(permission, "The filed job state changed before approval.")
            job.stage = JobStage.CANCELLED
        else:
            if job.stage not in {JobStage.FILED, JobStage.CANCELLED}:
                self._stage_error(permission, "The job can no longer be reopened.")
            job.stage = JobStage.REOPENED
            job.checked_by_user_id = None
            job.checked_at = None
            job.filed_by_user_id = None
            job.filed_at = None
        request.status = ExceptionalRequestStatus.EXECUTED
        request.decided_by_user_id = actor.id
        request.decided_at = current_time
        self.session.flush()
        self.audit.record(
            actor=actor,
            action=f"job.{request.action.value}_approved",
            reason=request.reason,
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
            context={
                "request_id": request.id,
                "requested_by_user_id": request.requested_by_user_id,
            },
        )
        self.session.flush()
        return job

    def set_availability(
        self,
        *,
        actor: User,
        employee: User,
        availability: EmployeeAvailability,
        reason: str,
        now: datetime | None = None,
    ) -> User:
        current_time = self._time(now)
        decision = self.authorization.authorize_admin(
            actor, Permission.JOB_UPDATE, requested_scope=Scope.global_scope(), at=current_time
        )
        self._require(decision, actor, "employee.availability.denied", current_time)
        if employee.kind is not UserKind.STAFF:
            raise WorkflowValidationError("Availability applies only to staff employees.")
        if not reason.strip():
            raise WorkflowValidationError("An availability change reason is required.")
        previous = employee.availability
        employee.availability = availability
        self.audit.record(
            actor=actor,
            action="employee.availability_changed",
            reason=reason.strip(),
            occurred_at=current_time,
            decision=decision,
            context={
                "employee_id": employee.id,
                "before": previous.value,
                "after": availability.value,
            },
        )
        self.session.flush()
        return employee

    def _require_responsibility(
        self,
        actor: User,
        job: Job,
        responsibility: ResponsibilityType,
        permission: Permission,
        at: datetime,
    ) -> None:
        if actor.availability is EmployeeAvailability.ABSENT:
            self._deny(
                actor,
                job,
                permission,
                ReasonCode.EMPLOYEE_ABSENT,
                "Absent employees cannot perform active workflow actions.",
                f"job.{responsibility.value}.denied",
                at,
            )
        record = self._responsibility(job.id, responsibility)
        if record is not None and record.user_id == actor.id:
            return
        delegated = self.session.scalar(
            select(JobDelegation.id).where(
                JobDelegation.job_id == job.id,
                JobDelegation.responsibility == responsibility,
                JobDelegation.delegate_user_id == actor.id,
                JobDelegation.valid_from <= at,
                JobDelegation.valid_until > at,
                or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > at),
            )
        )
        if delegated is not None:
            return
        self._deny(
            actor,
            job,
            permission,
            ReasonCode.MISSING_RESPONSIBILITY,
            "The actor is eligible but is not assigned or effectively delegated this job.",
            f"job.{responsibility.value}.denied",
            at,
        )

    def _validate_candidate(
        self,
        candidate: User | None,
        job: Job,
        responsibility: ResponsibilityType,
        at: datetime,
    ) -> None:
        if candidate is None or not candidate.is_active or candidate.kind is not UserKind.STAFF:
            raise WorkflowValidationError("The selected employee is not an active staff identity.")
        if candidate.availability is EmployeeAvailability.ABSENT:
            raise WorkflowValidationError("Absent employees cannot receive new assignments.")
        decision = self.authorization.authorize_job(
            candidate, RESPONSIBILITY_PERMISSION[responsibility], job, at=at
        )
        if not decision.allowed:
            raise WorkflowError(
                AuthorizationDecision(
                    allowed=False,
                    reason_code=ReasonCode.ASSIGNMENT_INELIGIBLE,
                    explanation=f"The employee is ineligible: {decision.explanation}",
                    permission=RESPONSIBILITY_PERMISSION[responsibility],
                    job_visible=decision.job_visible,
                )
            )

    def _eligible_candidates(
        self,
        job: Job,
        responsibility: ResponsibilityType,
        at: datetime,
        limit: int,
        excluded: set[str],
    ) -> list[AssignmentSuggestion]:
        workload = (
            select(
                JobResponsibility.user_id.label("user_id"),
                func.count(JobResponsibility.id).label("pending"),
            )
            .join(Job, Job.id == JobResponsibility.job_id)
            .where(
                JobResponsibility.user_id.is_not(None),
                Job.stage.in_(OPEN_STAGES),
            )
            .group_by(JobResponsibility.user_id)
            .subquery()
        )
        assignment_effective = and_(
            RoleAssignment.valid_from <= at,
            or_(RoleAssignment.valid_until.is_(None), RoleAssignment.valid_until > at),
            or_(RoleAssignment.revoked_at.is_(None), RoleAssignment.revoked_at > at),
            or_(RoleAssignment.all_clients.is_(True), RoleAssignment.client_id == job.client_id),
            or_(RoleAssignment.all_branches.is_(True), RoleAssignment.branch_id == job.branch_id),
            or_(RoleAssignment.all_directions.is_(True), RoleAssignment.direction == job.direction),
            or_(RoleAssignment.all_modes.is_(True), RoleAssignment.mode == job.mode),
        )
        pending = func.coalesce(workload.c.pending, 0)
        statement = (
            select(User.id, User.display_name, pending.label("pending"))
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .join(RolePermission, RolePermission.role_id == RoleAssignment.role_id)
            .outerjoin(workload, workload.c.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.kind == UserKind.STAFF,
                User.availability == EmployeeAvailability.AVAILABLE,
                RolePermission.permission == RESPONSIBILITY_PERMISSION[responsibility],
                assignment_effective,
            )
            .group_by(User.id, User.display_name, workload.c.pending)
            .order_by(
                case((workload.c.pending.is_(None), 0), else_=workload.c.pending),
                User.display_name,
                User.id,
            )
            .limit(limit + len(excluded))
        )
        rows = self.session.execute(statement).all()
        return [
            AssignmentSuggestion(responsibility, user_id, name, int(pending_count))
            for user_id, name, pending_count in rows
            if user_id not in excluded
        ][:limit]

    def _responsibility(
        self, job_id: str, responsibility: ResponsibilityType
    ) -> JobResponsibility | None:
        return self.session.scalar(
            select(JobResponsibility).where(
                JobResponsibility.job_id == job_id,
                JobResponsibility.responsibility == responsibility,
            )
        )

    def _require(
        self,
        decision: AuthorizationDecision,
        actor: User,
        action: str,
        at: datetime,
        job: Job | None = None,
    ) -> None:
        if not decision.allowed:
            self.audit.record(
                actor=actor,
                action=action,
                reason=decision.explanation,
                occurred_at=at,
                job=job,
                decision=decision,
            )
            self.session.flush()
            raise WorkflowError(decision)

    def _deny(
        self,
        actor: User,
        job: Job,
        permission: Permission,
        code: ReasonCode,
        explanation: str,
        action: str,
        at: datetime,
    ) -> None:
        decision = AuthorizationDecision(
            allowed=False,
            reason_code=code,
            explanation=explanation,
            permission=permission,
            job_visible=True,
        )
        self._require(decision, actor, action, at, job)

    @staticmethod
    def _require_version(job: Job, expected: int, permission: Permission) -> None:
        if expected != job.version:
            raise WorkflowError(
                AuthorizationDecision(
                    allowed=False,
                    reason_code=ReasonCode.STALE_VERSION,
                    explanation="The job changed since it was opened. Reload and try again.",
                    permission=permission,
                    job_visible=True,
                )
            )

    @staticmethod
    def _stage_error(permission: Permission, explanation: str) -> None:
        raise WorkflowError(
            AuthorizationDecision(
                allowed=False,
                reason_code=ReasonCode.INVALID_STAGE,
                explanation=explanation,
                permission=permission,
                job_visible=True,
            )
        )

    @staticmethod
    def _scope(client_id: str, branch_id: str, direction: JobDirection, mode: JobMode) -> Scope:
        return Scope(
            all_clients=False,
            client_id=client_id,
            all_branches=False,
            branch_id=branch_id,
            all_directions=False,
            direction=direction,
            all_modes=False,
            mode=mode,
        )

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _time(value: datetime | None) -> datetime:
        result = value or datetime.now(UTC)
        WorkflowService._aware(result, "now")
        return result

    @staticmethod
    def _aware(value: datetime, field: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise WorkflowValidationError(f"{field} must include a UTC offset.")

    def update_job(
        self,
        *,
        actor: User,
        job: Job,
        expected_version: int,
        goods_description: str | None = None,
        container_reference: str | None = None,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        permission = (
            Permission.JOB_UPDATE if actor.kind is UserKind.SERVICE else Permission.JOB_PREPARE
        )
        decision = self.authorization.authorize_job(actor, permission, job, at=current_time)
        self._require(decision, actor, "job.update.denied", current_time, job)
        if actor.kind is not UserKind.SERVICE:
            self._require_responsibility(
                actor, job, ResponsibilityType.MAKER, permission, current_time
            )
        self._require_version(job, expected_version, permission)
        if job.stage in {JobStage.FILED, JobStage.CANCELLED}:
            self._stage_error(permission, "Filed or cancelled jobs cannot be edited normally.")
        before = job_snapshot(job)
        if goods_description is not None:
            job.goods_description = goods_description.strip()
        if container_reference is not None:
            job.container_reference = self._optional_text(container_reference)
        if job.stage is JobStage.CHECKED:
            job.stage = JobStage.PREPARED
            job.checklist_revision += 1
            job.prepared_by_user_id = actor.id
            job.prepared_at = current_time
            job.checked_by_user_id = None
            job.checked_at = None
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.updated",
            reason="Shipment fields updated.",
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job

    def prepare(
        self,
        *,
        actor: User,
        job: Job,
        checklist_data: dict[str, object],
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        decision = self.authorization.authorize_job(
            actor, Permission.JOB_PREPARE, job, at=current_time
        )
        self._require(decision, actor, "job.prepare.denied", current_time, job)
        self._require_responsibility(
            actor, job, ResponsibilityType.MAKER, Permission.JOB_PREPARE, current_time
        )
        self._require_version(job, expected_version, Permission.JOB_PREPARE)
        if job.stage not in {JobStage.CONFIRMED, JobStage.PREPARED, JobStage.REOPENED}:
            self._stage_error(
                Permission.JOB_PREPARE, "Only open preparation work can be submitted."
            )
        if not checklist_data:
            raise WorkflowValidationError("Checklist data is required.")
        before = job_snapshot(job)
        job.checklist_data = dict(checklist_data)
        job.checklist_revision += 1
        job.prepared_by_user_id = actor.id
        job.prepared_at = current_time
        job.checked_by_user_id = None
        job.checked_at = None
        job.stage = JobStage.PREPARED
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.prepared",
            reason="Checklist submitted for independent verification.",
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.session.flush()
        return job
