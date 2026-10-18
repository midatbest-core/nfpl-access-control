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
    AbsenceNomination,
    AbsenceNominationStatus,
    AccountStatus,
    ChecklistItemStatus,
    EditRequestStatus,
    EmployeeAvailability,
    ExceptionalAction,
    ExceptionalRequestStatus,
    ExceptionalTransitionRequest,
    FilingReturnCategory,
    Job,
    JobDelegation,
    JobDirection,
    JobEditRequest,
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
    UserAvailabilityEvent,
    UserKind,
)
from nfpl_access_control.services.absence import has_effective_absence
from nfpl_access_control.services.audit import AuditService, job_snapshot
from nfpl_access_control.services.notifications import NotificationService

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

CHECKLIST_TEMPLATES: dict[JobMode, tuple[tuple[str, str], ...]] = {
    JobMode.AIR: (
        ("commercial_invoice", "Commercial invoice matches shipment details"),
        ("packing_list", "Packing list is present and consistent"),
        ("air_waybill", "Air waybill details are verified"),
    ),
    JobMode.FCL: (
        ("commercial_invoice", "Commercial invoice matches shipment details"),
        ("packing_list", "Packing list is present and consistent"),
        ("bill_of_lading", "Bill of lading details are verified"),
        ("container_reference", "Container and seal references are verified"),
    ),
    JobMode.LCL: (
        ("commercial_invoice", "Commercial invoice matches shipment details"),
        ("packing_list", "Packing list is present and consistent"),
        ("house_bill_of_lading", "House bill of lading is verified"),
        ("consolidation_reference", "Consolidation reference is verified"),
    ),
}


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
        self.notifications = NotificationService(session)

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
        approved: bool | None,
        reason: str,
        expected_version: int,
        checklist_items: list[dict[str, object]] | None = None,
        justification: str = "",
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
        self._require_version(
            actor, job, expected_version, Permission.JOB_CHECK, current_time, "job.check.denied"
        )
        if job.stage is not JobStage.PREPARED:
            self._stage_error(
                actor,
                job,
                Permission.JOB_CHECK,
                "Only prepared jobs can be checked.",
                "job.check.denied",
                current_time,
            )
        if job.prepared_by_user_id is None:
            self._stage_error(
                actor,
                job,
                Permission.JOB_CHECK,
                "The current revision has no recorded preparer.",
                "job.check.denied",
                current_time,
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
        decisions = self._checklist_decisions(
            actor=actor,
            job=job,
            checklist_items=checklist_items,
            legacy_approved=approved,
            at=current_time,
        )
        has_incomplete = any(
            item["status"] == ChecklistItemStatus.INCOMPLETE.value for item in decisions
        )
        derived_approval = not has_incomplete
        if approved is not None and checklist_items is not None and approved != derived_approval:
            self._checklist_error(
                actor,
                job,
                "The approval flag conflicts with the checklist item decisions.",
                current_time,
            )
        if has_incomplete and not reason.strip():
            self._checklist_error(
                actor,
                job,
                "Actionable feedback is required when a checklist item is incomplete.",
                current_time,
            )
        if job.checker_correction_required and not justification.strip():
            self._deny(
                actor,
                job,
                Permission.JOB_CHECK,
                ReasonCode.JUSTIFICATION_REQUIRED,
                "A justification is required when reconsidering or reapproving a checklist.",
                "job.check.denied",
                current_time,
            )
        before = job_snapshot(job)
        job.checklist_data = {
            "revision": job.checklist_revision,
            "mode": job.mode.value,
            "direction": job.direction.value,
            "items": decisions,
        }
        job.last_checker_justification = justification.strip() or reason.strip() or None
        if derived_approval:
            job.stage = JobStage.CHECKED
            job.checked_by_user_id = actor.id
            job.checked_at = current_time
            action = "job.rechecked" if job.checker_correction_required else "job.checked"
            job.checker_correction_required = False
            job.last_return_category = None
            job.last_return_reason = None
        else:
            job.stage = JobStage.CONFIRMED
            job.checked_by_user_id = None
            job.checked_at = None
            job.maker_edit_locked = False
            job.maker_correction_required = True
            job.checker_correction_required = False
            job.last_return_category = FilingReturnCategory.MAKER_FAULT
            job.last_return_reason = reason.strip()
            action = "job.check_rejected" if checklist_items is None else "job.checklist_returned"
        self.session.flush()
        self.audit.record(
            actor=actor,
            action=action,
            reason=(reason.strip() or justification.strip() or "Checklist independently verified."),
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        target = ResponsibilityType.FILING_OFFICER if derived_approval else ResponsibilityType.MAKER
        self.notifications.notify_responsibility(
            actor=actor,
            job=job,
            responsibility=target,
            event_type=("checker_approved" if derived_approval else "checker_returned"),
            message=(
                "A checked shipment is ready for filing."
                if derived_approval
                else "A shipment was returned with correction feedback."
            ),
            event_key=f"job:{job.id}:{action}:{job.version}",
            now=current_time,
        )
        if derived_approval:
            self.notifications.notify_client_viewers(
                actor=actor,
                job=job,
                event_type="shipment_checked",
                message="Shipment verification is complete.",
                event_key=f"job:{job.id}:client:checked:{job.version}",
                now=current_time,
            )
        self.session.flush()
        return job

    def return_for_correction(
        self,
        *,
        actor: User,
        job: Job,
        category: FilingReturnCategory,
        reason: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        decision = self.authorization.authorize_job(
            actor, Permission.JOB_FILE, job, at=current_time
        )
        self._require(decision, actor, "job.filing_return.denied", current_time, job)
        self._require_responsibility(
            actor, job, ResponsibilityType.FILING_OFFICER, Permission.JOB_FILE, current_time
        )
        self._require_version(
            actor,
            job,
            expected_version,
            Permission.JOB_FILE,
            current_time,
            "job.filing_return.denied",
        )
        if job.stage is not JobStage.CHECKED or job.checked_by_user_id is None:
            self._stage_error(
                actor,
                job,
                Permission.JOB_FILE,
                "Only an independently checked job can be returned by Filing.",
                "job.filing_return.denied",
                current_time,
            )
        if not reason.strip():
            self._deny(
                actor,
                job,
                Permission.JOB_FILE,
                ReasonCode.JUSTIFICATION_REQUIRED,
                "A written explanation is required when returning a job.",
                "job.filing_return.denied",
                current_time,
            )
        before = job_snapshot(job)
        job.last_return_category = category
        job.last_return_reason = reason.strip()
        job.checked_by_user_id = None
        job.checked_at = None
        job.filed_by_user_id = None
        job.filed_at = None
        if category is FilingReturnCategory.CHECKER_FAULT:
            job.stage = JobStage.PREPARED
            job.maker_edit_locked = True
            job.maker_correction_required = False
            job.checker_correction_required = True
        else:
            job.stage = JobStage.CONFIRMED
            job.maker_edit_locked = False
            job.maker_correction_required = True
            job.checker_correction_required = True
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.returned_for_correction",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
            context={"return_category": category.value},
        )
        targets = (
            (ResponsibilityType.CHECKER,)
            if category is FilingReturnCategory.CHECKER_FAULT
            else (
                (ResponsibilityType.MAKER, ResponsibilityType.CHECKER)
                if category is FilingReturnCategory.BOTH
                else (ResponsibilityType.MAKER,)
            )
        )
        for target in targets:
            self.notifications.notify_responsibility(
                actor=actor,
                job=job,
                responsibility=target,
                event_type="filing_returned",
                message=f"Filing returned this shipment for {category.value.replace('_', ' ')}.",
                event_key=f"job:{job.id}:filing-return:{job.version}:{target.value}",
                now=current_time,
            )
        self.session.flush()
        return job

    def request_edit(
        self,
        *,
        actor: User,
        job: Job,
        reason: str,
        now: datetime | None = None,
    ) -> JobEditRequest:
        current_time = self._time(now)
        decision = self.authorization.authorize_job(
            actor, Permission.JOB_PREPARE, job, at=current_time
        )
        self._require(decision, actor, "job.edit_request.denied", current_time, job)
        self._require_responsibility(
            actor, job, ResponsibilityType.MAKER, Permission.JOB_PREPARE, current_time
        )
        # Serialize competing requests for the same job on PostgreSQL. SQLite
        # safely ignores FOR UPDATE while retaining its single-writer behavior.
        self.session.execute(select(Job.id).where(Job.id == job.id).with_for_update()).scalar_one()
        if not reason.strip():
            self._deny(
                actor,
                job,
                Permission.JOB_PREPARE,
                ReasonCode.JUSTIFICATION_REQUIRED,
                "An edit request requires a written justification.",
                "job.edit_request.denied",
                current_time,
            )
        if not job.maker_edit_locked or job.stage not in {JobStage.PREPARED, JobStage.CHECKED}:
            self._stage_error(
                actor,
                job,
                Permission.JOB_PREPARE,
                "An edit request is only available for a submitted, locked job.",
                "job.edit_request.denied",
                current_time,
            )
        pending = self.session.scalar(
            select(JobEditRequest.id).where(
                JobEditRequest.job_id == job.id,
                JobEditRequest.status == EditRequestStatus.PENDING,
            )
        )
        if pending is not None:
            raise WorkflowConflictError("A job-specific edit request is already pending.")
        request = JobEditRequest(
            job_id=job.id,
            status=EditRequestStatus.PENDING,
            requested_by_user_id=actor.id,
            requested_at=current_time,
            reason=reason.strip(),
        )
        self.session.add(request)
        self.audit.record(
            actor=actor,
            action="job.edit_requested",
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            decision=decision,
        )
        self.session.flush()
        return request

    def decide_edit_request(
        self,
        *,
        actor: User,
        request: JobEditRequest,
        approved: bool,
        reason: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> Job:
        current_time = self._time(now)
        locked_request = self.session.scalar(
            select(JobEditRequest).where(JobEditRequest.id == request.id).with_for_update()
        )
        if locked_request is None:
            raise WorkflowValidationError("The edit request no longer exists.")
        request = locked_request
        job = self.session.get(Job, request.job_id)
        if job is None:
            raise WorkflowValidationError("The edit request has no job.")
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_UPDATE,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        self._require(decision, actor, "job.edit_request_decision.denied", current_time, job)
        if actor.id == request.requested_by_user_id:
            self._deny(
                actor,
                job,
                Permission.JOB_UPDATE,
                ReasonCode.SELF_APPROVAL_FORBIDDEN,
                "The employee requesting an edit cannot approve their own request.",
                "job.edit_request_decision.denied",
                current_time,
            )
        if request.status is not EditRequestStatus.PENDING:
            raise WorkflowConflictError("The edit request is no longer pending.")
        if not reason.strip():
            self._deny(
                actor,
                job,
                Permission.JOB_UPDATE,
                ReasonCode.JUSTIFICATION_REQUIRED,
                "An Admin decision requires a written reason.",
                "job.edit_request_decision.denied",
                current_time,
            )
        self._require_version(
            actor,
            job,
            expected_version,
            Permission.JOB_UPDATE,
            current_time,
            "job.edit_request_decision.denied",
        )
        if job.stage in {JobStage.FILED, JobStage.CANCELLED}:
            self._stage_error(
                actor,
                job,
                Permission.JOB_UPDATE,
                "Filed or cancelled jobs require the exceptional transition process.",
                "job.edit_request_decision.denied",
                current_time,
            )
        request.status = EditRequestStatus.APPROVED if approved else EditRequestStatus.DENIED
        request.decided_by_user_id = actor.id
        request.decided_at = current_time
        request.decision_reason = reason.strip()
        before = job_snapshot(job)
        after: dict[str, object] | None = None
        if approved:
            job.stage = JobStage.CONFIRMED
            job.maker_edit_locked = False
            job.maker_correction_required = True
            job.checker_correction_required = True
            job.checked_by_user_id = None
            job.checked_at = None
            job.last_return_reason = reason.strip()
            self.session.flush()
            after = job_snapshot(job)
        self.audit.record(
            actor=actor,
            action=("job.edit_request_approved" if approved else "job.edit_request_denied"),
            reason=reason.strip(),
            occurred_at=current_time,
            job=job,
            before=before if approved else None,
            after=after,
            decision=decision,
            context={
                "edit_request_id": request.id,
                "requested_by_user_id": request.requested_by_user_id,
            },
        )
        self.notifications.create(
            actor=actor,
            recipient_user_id=request.requested_by_user_id,
            event_type=("edit_request_approved" if approved else "edit_request_denied"),
            message=(
                "Your shipment edit request was approved."
                if approved
                else "Your shipment edit request was denied."
            ),
            target_path=f"/v1/jobs/{job.id}",
            dedupe_key=f"edit-request:{request.id}:decision",
            job=job,
            now=current_time,
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
        self._require_version(
            actor, job, expected_version, Permission.JOB_FILE, current_time, "job.file.denied"
        )
        if job.stage is not JobStage.CHECKED or job.checked_by_user_id is None:
            self._stage_error(
                actor,
                job,
                Permission.JOB_FILE,
                "Only independently checked jobs can be filed.",
                "job.file.denied",
                current_time,
            )
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
        self.notifications.notify_client_viewers(
            actor=actor,
            job=job,
            event_type="shipment_filed",
            message="Shipment filing is complete.",
            event_key=f"job:{job.id}:client:filed:{job.version}",
            now=current_time,
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
        # Persist the responsibility first so notification dedupe keys use its
        # stable identifier rather than a pre-flush None value.
        self.session.flush()
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
        if target_user_id is not None and target_user_id != previous_user_id:
            self.notifications.create(
                actor=actor,
                recipient_user_id=target_user_id,
                event_type="job_assigned",
                message=f"A {responsibility.value} job was assigned to you.",
                target_path=f"/v1/jobs/{job.id}",
                dedupe_key=f"assignment:{record.id}:{record.version}:{target_user_id}",
                job=job,
                now=current_time,
            )
        if previous_user_id is not None and previous_user_id != target_user_id:
            self.notifications.create(
                actor=actor,
                recipient_user_id=previous_user_id,
                event_type="responsibility_revoked",
                message="A job responsibility was removed from your work queue.",
                target_path="/v1/my-work",
                dedupe_key=f"assignment:{record.id}:{record.version}:revoked:{previous_user_id}",
                job=job,
                now=current_time,
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
        if valid_until <= valid_from or valid_until <= current_time:
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
        responsibility_record = self.session.scalar(
            select(JobResponsibility)
            .where(
                JobResponsibility.job_id == job.id,
                JobResponsibility.responsibility == responsibility,
            )
            .with_for_update()
        )
        if responsibility_record is None or responsibility_record.user_id is None:
            raise WorkflowValidationError("The responsibility must be assigned before delegation.")
        overlap = self.session.scalar(
            select(JobDelegation.id).where(
                JobDelegation.job_id == job.id,
                JobDelegation.responsibility == responsibility,
                JobDelegation.valid_from < valid_until,
                JobDelegation.valid_until > valid_from,
                JobDelegation.revoked_at.is_(None),
            )
        )
        if overlap is not None:
            raise WorkflowConflictError("An overlapping active delegation already exists.")
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
        self.session.flush()
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
        self.notifications.create(
            actor=actor,
            recipient_user_id=delegate_user_id,
            event_type="job_delegated",
            message=f"Temporary {responsibility.value} work was delegated to you.",
            target_path=f"/v1/jobs/{job.id}",
            dedupe_key=f"delegation:{delegation.id}:created",
            job=job,
            now=current_time,
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
        self.notifications.create(
            actor=actor,
            recipient_user_id=delegation.delegate_user_id,
            event_type="delegation_revoked",
            message="A temporary job delegation was revoked.",
            target_path="/v1/my-work",
            dedupe_key=f"delegation:{delegation.id}:revoked",
            job=job,
            now=current_time,
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
        assigned_maker = self._responsibility(job.id, ResponsibilityType.MAKER)
        selected_maker_ids = (
            {assigned_maker.user_id}
            if assigned_maker is not None and assigned_maker.user_id is not None
            else set()
        )
        for responsibility in ResponsibilityType:
            excluded = selected_maker_ids if responsibility is ResponsibilityType.CHECKER else set()
            candidates = self._eligible_candidates(
                job, responsibility, current_time, limit_per_role, excluded
            )
            result[responsibility] = candidates
            if responsibility is ResponsibilityType.MAKER and not selected_maker_ids and candidates:
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
        self._require_version(
            actor,
            job,
            expected_version,
            Permission.JOB_CANCEL,
            current_time,
            "job.cancel.denied",
        )
        if job.stage is JobStage.CANCELLED:
            self._stage_error(
                actor,
                job,
                Permission.JOB_CANCEL,
                "The job is already cancelled.",
                "job.cancel.denied",
                current_time,
            )
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
        self._require_version(
            actor,
            job,
            expected_version,
            permission,
            current_time,
            "job.exception_approval.denied",
        )
        before = job_snapshot(job)
        if request.action is ExceptionalAction.CANCEL:
            if job.stage is not JobStage.FILED:
                self._stage_error(
                    actor,
                    job,
                    permission,
                    "The filed job state changed before approval.",
                    "job.exception_approval.denied",
                    current_time,
                )
            job.stage = JobStage.CANCELLED
        else:
            if job.stage not in {JobStage.FILED, JobStage.CANCELLED}:
                self._stage_error(
                    actor,
                    job,
                    permission,
                    "The job can no longer be reopened.",
                    "job.exception_approval.denied",
                    current_time,
                )
            job.stage = JobStage.REOPENED
            job.checked_by_user_id = None
            job.checked_at = None
            job.filed_by_user_id = None
            job.filed_at = None
            job.maker_edit_locked = False
            job.maker_correction_required = True
            job.checker_correction_required = True
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
        self.session.add(
            UserAvailabilityEvent(
                user_id=employee.id,
                previous_availability=previous,
                availability=availability,
                effective_at=current_time,
                actor_user_id=actor.id,
                reason=reason.strip(),
            )
        )
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
        if has_effective_absence(self.session, actor, at):
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
        if (
            candidate is None
            or not candidate.is_active
            or candidate.account_status is not AccountStatus.ACTIVE
            or candidate.kind is not UserKind.STAFF
        ):
            raise WorkflowValidationError("The selected employee is not an active staff identity.")
        if has_effective_absence(self.session, candidate, at):
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
        effective_absence = (
            select(AbsenceNomination.id)
            .where(
                AbsenceNomination.requester_user_id == User.id,
                AbsenceNomination.status.in_(
                    (AbsenceNominationStatus.APPROVED, AbsenceNominationStatus.REVOKED)
                ),
                AbsenceNomination.decided_at <= at,
                AbsenceNomination.valid_from <= at,
                AbsenceNomination.valid_until > at,
                or_(
                    AbsenceNomination.revoked_at.is_(None),
                    AbsenceNomination.revoked_at > at,
                ),
            )
            .correlate(User)
        )
        statement = (
            select(User.id, User.display_name, pending.label("pending"))
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .join(RolePermission, RolePermission.role_id == RoleAssignment.role_id)
            .outerjoin(workload, workload.c.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.account_status == AccountStatus.ACTIVE,
                User.kind == UserKind.STAFF,
                User.availability == EmployeeAvailability.AVAILABLE,
                ~effective_absence.exists(),
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

    def _require_version(
        self,
        actor: User,
        job: Job,
        expected: int,
        permission: Permission,
        at: datetime,
        action: str,
    ) -> None:
        if expected != job.version:
            self._deny(
                actor,
                job,
                permission,
                ReasonCode.STALE_VERSION,
                "The job changed since it was opened. Reload and try again.",
                action,
                at,
            )

    def _stage_error(
        self,
        actor: User,
        job: Job,
        permission: Permission,
        explanation: str,
        action: str,
        at: datetime,
    ) -> None:
        self._deny(
            actor,
            job,
            permission,
            ReasonCode.INVALID_STAGE,
            explanation,
            action,
            at,
        )

    def _checklist_error(
        self,
        actor: User,
        job: Job,
        explanation: str,
        at: datetime,
    ) -> None:
        self._deny(
            actor,
            job,
            Permission.JOB_CHECK,
            ReasonCode.INVALID_CHECKLIST,
            explanation,
            "job.check.denied",
            at,
        )

    def _checklist_decisions(
        self,
        *,
        actor: User,
        job: Job,
        checklist_items: list[dict[str, object]] | None,
        legacy_approved: bool | None,
        at: datetime,
    ) -> list[dict[str, object]]:
        template = self._checklist_template(job)
        if checklist_items is None:
            if legacy_approved is None:
                self._checklist_error(actor, job, "Checklist item decisions are required.", at)
            return [
                {
                    **item,
                    "status": (
                        ChecklistItemStatus.COMPLETE.value
                        if legacy_approved or index
                        else ChecklistItemStatus.INCOMPLETE.value
                    ),
                    "justification": None,
                }
                for index, item in enumerate(template)
            ]
        submitted: dict[str, dict[str, object]] = {}
        for item in checklist_items:
            key = item.get("key")
            raw_status = item.get("status")
            justification = str(item.get("justification") or "").strip()
            if not isinstance(key, str) or key in submitted:
                self._checklist_error(actor, job, "Checklist item keys must be unique.", at)
            try:
                status = ChecklistItemStatus(str(raw_status))
            except ValueError:
                self._checklist_error(actor, job, "A checklist item has an invalid status.", at)
            if status is ChecklistItemStatus.NOT_APPLICABLE and not justification:
                self._checklist_error(
                    actor,
                    job,
                    "Not Applicable checklist items require a justification.",
                    at,
                )
            submitted[key] = {
                "status": status.value,
                "justification": justification or None,
            }
        template_keys = {str(item["key"]) for item in template}
        if set(submitted) != template_keys:
            self._checklist_error(
                actor,
                job,
                "Checklist decisions must include every generated item exactly once.",
                at,
            )
        return [{**item, **submitted[str(item["key"])]} for item in template]

    @staticmethod
    def _checklist_template(job: Job) -> list[dict[str, object]]:
        common = [
            {"key": key, "label": label, "required": True}
            for key, label in CHECKLIST_TEMPLATES[job.mode]
        ]
        direction_key = f"{job.direction.value}_requirements"
        direction_label = (
            "Import permits and arrival requirements are verified"
            if job.direction is JobDirection.IMPORT
            else "Export permits and departure requirements are verified"
        )
        return [*common, {"key": direction_key, "label": direction_label, "required": True}]

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
        self._require_version(
            actor, job, expected_version, permission, current_time, "job.update.denied"
        )
        if job.stage in {JobStage.FILED, JobStage.CANCELLED}:
            self._stage_error(
                actor,
                job,
                permission,
                "Filed or cancelled jobs cannot be edited normally.",
                "job.update.denied",
                current_time,
            )
        if job.maker_edit_locked:
            self._deny(
                actor,
                job,
                permission,
                ReasonCode.SUBMISSION_LOCKED,
                "The submitted revision is locked. An approved edit request or return is required.",
                "job.update.denied",
                current_time,
            )
        before = job_snapshot(job)
        if goods_description is not None:
            job.goods_description = goods_description.strip()
        if container_reference is not None:
            job.container_reference = self._optional_text(container_reference)
        if job.checked_by_user_id is not None:
            job.stage = JobStage.CONFIRMED
            job.checked_by_user_id = None
            job.checked_at = None
            job.checker_correction_required = True
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
        checklist_data: dict[str, object] | None,
        expected_version: int,
        justification: str = "",
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
        self._require_version(
            actor,
            job,
            expected_version,
            Permission.JOB_PREPARE,
            current_time,
            "job.prepare.denied",
        )
        if job.stage not in {JobStage.CONFIRMED, JobStage.REOPENED}:
            self._stage_error(
                actor,
                job,
                Permission.JOB_PREPARE,
                "Only open preparation work can be submitted.",
                "job.prepare.denied",
                current_time,
            )
        if job.maker_edit_locked:
            self._deny(
                actor,
                job,
                Permission.JOB_PREPARE,
                ReasonCode.SUBMISSION_LOCKED,
                "The current revision is already submitted and locked.",
                "job.prepare.denied",
                current_time,
            )
        is_correction = job.checklist_revision > 0 or job.maker_correction_required
        if is_correction and not justification.strip():
            self._deny(
                actor,
                job,
                Permission.JOB_PREPARE,
                ReasonCode.JUSTIFICATION_REQUIRED,
                "A justification is required for every correction resubmission.",
                "job.prepare.denied",
                current_time,
            )
        before = job_snapshot(job)
        job.checklist_revision += 1
        job.checklist_data = {
            "revision": job.checklist_revision,
            "mode": job.mode.value,
            "direction": job.direction.value,
            "items": [
                {**item, "status": None, "justification": None}
                for item in self._checklist_template(job)
            ],
        }
        job.prepared_by_user_id = actor.id
        job.prepared_at = current_time
        job.checked_by_user_id = None
        job.checked_at = None
        job.stage = JobStage.PREPARED
        job.maker_edit_locked = True
        job.maker_correction_required = False
        job.checker_correction_required = is_correction
        job.last_maker_justification = justification.strip() or None
        approved_requests = self.session.scalars(
            select(JobEditRequest).where(
                JobEditRequest.job_id == job.id,
                JobEditRequest.status == EditRequestStatus.APPROVED,
            )
        )
        for request in approved_requests:
            request.status = EditRequestStatus.CONSUMED
            request.consumed_at = current_time
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="job.prepared",
            reason=justification.strip() or "Shipment submitted for independent verification.",
            occurred_at=current_time,
            job=job,
            before=before,
            after=job_snapshot(job),
            decision=decision,
        )
        self.notifications.notify_responsibility(
            actor=actor,
            job=job,
            responsibility=ResponsibilityType.CHECKER,
            event_type=("maker_resubmitted" if is_correction else "maker_submitted"),
            message=(
                "Corrected shipment details require verification."
                if is_correction
                else "A prepared shipment requires verification."
            ),
            event_key=f"job:{job.id}:prepared:{job.version}",
            now=current_time,
        )
        self.session.flush()
        return job
