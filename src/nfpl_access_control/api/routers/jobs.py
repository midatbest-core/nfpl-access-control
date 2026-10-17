"""Authenticated shipment workflow endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.authorization import AuthorizationEngine
from nfpl_access_control.models import (
    ExceptionalTransitionRequest,
    Job,
    JobDelegation,
    JobEditRequest,
    JobResponsibility,
    Permission,
    User,
    UserKind,
)
from nfpl_access_control.schemas.workflow import (
    AssignmentRequest,
    AvailabilityRequest,
    CheckRequest,
    ClientJobDetailResponse,
    DelegationRequest,
    DelegationResponse,
    EditRequestCreate,
    EditRequestDecision,
    EditRequestResponse,
    ExceptionalTransitionCreateRequest,
    ExceptionalTransitionResponse,
    FilingReturnRequest,
    JobCreateRequest,
    JobResponse,
    JobResponsibilityDetailResponse,
    JobUpdateRequest,
    PrepareRequest,
    ReasonedVersionRequest,
    ReasonRequest,
    ResponsibilityResponse,
    SuggestionResponse,
    VersionRequest,
)
from nfpl_access_control.services.workflow import (
    WorkflowConflictError,
    WorkflowError,
    WorkflowService,
    WorkflowValidationError,
)

router = APIRouter(tags=["jobs"])


def _job_or_hidden(session: DatabaseSession, actor: CurrentActor, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or not visible")
    decision = AuthorizationEngine(session).authorize_job(actor, Permission.JOB_VIEW, job)
    if not decision.allowed:
        raise HTTPException(status_code=404, detail="Job not found or not visible")
    return job


def _handle(error: Exception, session: DatabaseSession) -> None:
    if isinstance(error, WorkflowError):
        # Authorization denials are append-only records and occur before mutation.
        session.commit()
        reason_code = error.decision.reason_code.value
        if reason_code in {"invalid_stage", "stale_version", "submission_locked"}:
            code = 409
        elif reason_code in {"invalid_checklist", "justification_required"}:
            code = 422
        else:
            code = 403
        raise HTTPException(
            status_code=code,
            detail={
                "reason_code": error.decision.reason_code,
                "explanation": error.decision.explanation,
            },
        ) from error
    session.rollback()
    if isinstance(error, WorkflowConflictError | StaleDataError | IntegrityError):
        raise HTTPException(
            status_code=409, detail="The operation conflicts with current state."
        ) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    request: JobCreateRequest, actor: CurrentActor, session: DatabaseSession
) -> JobResponse:
    try:
        job = WorkflowService(session).create_job(actor=actor, **request.model_dump())
        response = JobResponse.from_job(job)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, IntegrityError) as error:
        _handle(error, session)


@router.get("/jobs/{job_id}", response_model=JobResponse | ClientJobDetailResponse)
def get_job(
    job_id: str, actor: CurrentActor, session: DatabaseSession
) -> JobResponse | ClientJobDetailResponse:
    job = _job_or_hidden(session, actor, job_id)
    if actor.kind is UserKind.CLIENT:
        return ClientJobDetailResponse.from_job(job)
    return JobResponse.from_job(job)


@router.get(
    "/jobs/{job_id}/responsibilities",
    response_model=list[JobResponsibilityDetailResponse],
)
def get_job_responsibilities(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
) -> list[JobResponsibilityDetailResponse]:
    job = _job_or_hidden(session, actor, job_id)
    if actor.kind is not UserKind.STAFF:
        raise HTTPException(status_code=404, detail="Job not found or not visible")
    current_time = datetime.now(UTC)
    delegated = set(
        session.scalars(
            select(JobDelegation.responsibility).where(
                JobDelegation.job_id == job.id,
                JobDelegation.delegate_user_id == actor.id,
                JobDelegation.valid_from <= current_time,
                JobDelegation.valid_until > current_time,
                or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > current_time),
            )
        )
    )
    rows = session.execute(
        select(JobResponsibility, User)
        .outerjoin(User, User.id == JobResponsibility.user_id)
        .where(JobResponsibility.job_id == job.id)
        .order_by(JobResponsibility.responsibility)
    )
    return [
        JobResponsibilityDetailResponse(
            responsibility=record.responsibility,
            user_id=record.user_id,
            display_name=employee.display_name if employee is not None else None,
            current_actor_responsible=(
                record.user_id == actor.id or record.responsibility in delegated
            ),
            via_delegation=record.responsibility in delegated,
        )
        for record, employee in rows
    ]


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str, request: JobUpdateRequest, actor: CurrentActor, session: DatabaseSession
) -> JobResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        updated = WorkflowService(session).update_job(actor=actor, job=job, **request.model_dump())
        response = JobResponse.from_job(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, IntegrityError, StaleDataError) as error:
        _handle(error, session)


@router.post("/jobs/{job_id}/prepare", response_model=JobResponse)
def prepare_job(
    job_id: str, request: PrepareRequest, actor: CurrentActor, session: DatabaseSession
) -> JobResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        updated = WorkflowService(session).prepare(actor=actor, job=job, **request.model_dump())
        response = JobResponse.from_job(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, StaleDataError) as error:
        _handle(error, session)


@router.post("/jobs/{job_id}/check", response_model=JobResponse)
def check_job(
    job_id: str, request: CheckRequest, actor: CurrentActor, session: DatabaseSession
) -> JobResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        updated = WorkflowService(session).check(actor=actor, job=job, **request.model_dump())
        response = JobResponse.from_job(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, StaleDataError) as error:
        _handle(error, session)


@router.post("/jobs/{job_id}/file", response_model=JobResponse)
def file_job(
    job_id: str, request: VersionRequest, actor: CurrentActor, session: DatabaseSession
) -> JobResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        updated = WorkflowService(session).file(actor=actor, job=job, **request.model_dump())
        response = JobResponse.from_job(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, StaleDataError) as error:
        _handle(error, session)


@router.post("/jobs/{job_id}/return-for-correction", response_model=JobResponse)
def return_job_for_correction(
    job_id: str,
    request: FilingReturnRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> JobResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        updated = WorkflowService(session).return_for_correction(
            actor=actor, job=job, **request.model_dump()
        )
        response = JobResponse.from_job(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, StaleDataError) as error:
        _handle(error, session)


@router.post(
    "/jobs/{job_id}/edit-requests",
    response_model=EditRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_job_edit(
    job_id: str,
    request: EditRequestCreate,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EditRequestResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        record = WorkflowService(session).request_edit(actor=actor, job=job, reason=request.reason)
        response = EditRequestResponse.model_validate(record)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, WorkflowConflictError) as error:
        _handle(error, session)


@router.post("/admin/edit-requests/{request_id}/decision", response_model=JobResponse)
def decide_job_edit_request(
    request_id: str,
    request: EditRequestDecision,
    actor: CurrentActor,
    session: DatabaseSession,
) -> JobResponse:
    edit_request = session.get(JobEditRequest, request_id)
    if edit_request is None:
        raise HTTPException(status_code=404, detail="Edit request not found")
    try:
        job = WorkflowService(session).decide_edit_request(
            actor=actor, request=edit_request, **request.model_dump()
        )
        response = JobResponse.from_job(job)
        session.commit()
        return response
    except WorkflowError as error:
        if error.decision.reason_code.value in {
            "admin_required",
            "client_scope_mismatch",
            "branch_scope_mismatch",
            "direction_scope_mismatch",
            "mode_scope_mismatch",
            "missing_permission",
            "access_not_yet_effective",
            "access_expired",
            "access_revoked",
        }:
            session.commit()
            raise HTTPException(
                status_code=404, detail="Edit request not found or not visible"
            ) from error
        _handle(error, session)
    except (WorkflowValidationError, WorkflowConflictError, StaleDataError) as error:
        _handle(error, session)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(
    job_id: str,
    request: ReasonedVersionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> JobResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        updated = WorkflowService(session).cancel(actor=actor, job=job, **request.model_dump())
        response = JobResponse.from_job(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, StaleDataError) as error:
        _handle(error, session)


@router.put("/admin/jobs/{job_id}/assignment", response_model=ResponsibilityResponse)
def assign_job(
    job_id: str, request: AssignmentRequest, actor: CurrentActor, session: DatabaseSession
) -> ResponsibilityResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        record = WorkflowService(session).assign(actor=actor, job=job, **request.model_dump())
        response = ResponsibilityResponse.model_validate(record)
        session.commit()
        return response
    except (
        WorkflowError,
        WorkflowValidationError,
        WorkflowConflictError,
        IntegrityError,
        StaleDataError,
    ) as error:
        _handle(error, session)


@router.post(
    "/admin/jobs/{job_id}/delegations",
    response_model=DelegationResponse,
    status_code=status.HTTP_201_CREATED,
)
def delegate_job(
    job_id: str, request: DelegationRequest, actor: CurrentActor, session: DatabaseSession
) -> DelegationResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        record = WorkflowService(session).delegate(actor=actor, job=job, **request.model_dump())
        response = DelegationResponse.model_validate(record)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, IntegrityError) as error:
        _handle(error, session)


@router.post("/admin/delegations/{delegation_id}/revoke", response_model=DelegationResponse)
def revoke_delegation(
    delegation_id: str,
    request: ReasonRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> DelegationResponse:
    delegation = session.get(JobDelegation, delegation_id)
    if delegation is None:
        raise HTTPException(status_code=404, detail="Delegation not found")
    try:
        updated = WorkflowService(session).revoke_delegation(
            actor=actor, delegation=delegation, reason=request.reason
        )
        response = DelegationResponse.model_validate(updated)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, WorkflowConflictError) as error:
        _handle(error, session)


@router.get(
    "/admin/jobs/{job_id}/assignment-suggestions",
    response_model=dict[str, list[SuggestionResponse]],
)
def assignment_suggestions(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
    limit_per_role: int = Query(default=5, ge=1, le=20),
) -> dict[str, list[SuggestionResponse]]:
    job = _job_or_hidden(session, actor, job_id)
    try:
        suggestions = WorkflowService(session).suggestions(
            actor=actor, job=job, limit_per_role=limit_per_role
        )
        return {
            responsibility.value: [
                SuggestionResponse(
                    responsibility=item.responsibility,
                    user_id=item.user_id,
                    display_name=item.display_name,
                    pending_workload=item.pending_workload,
                )
                for item in items
            ]
            for responsibility, items in suggestions.items()
        }
    except (WorkflowError, WorkflowValidationError) as error:
        _handle(error, session)


@router.post(
    "/admin/jobs/{job_id}/exception-requests",
    response_model=ExceptionalTransitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_exception(
    job_id: str,
    request: ExceptionalTransitionCreateRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> ExceptionalTransitionResponse:
    job = _job_or_hidden(session, actor, job_id)
    try:
        record = WorkflowService(session).request_exception(
            actor=actor, job=job, **request.model_dump()
        )
        response = ExceptionalTransitionResponse.model_validate(record)
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError, WorkflowConflictError) as error:
        _handle(error, session)


@router.post("/admin/exception-requests/{request_id}/approve", response_model=JobResponse)
def approve_exception(
    request_id: str,
    request: VersionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> JobResponse:
    transition_request = session.get(ExceptionalTransitionRequest, request_id)
    if transition_request is None:
        raise HTTPException(status_code=404, detail="Exceptional request not found")
    try:
        job = WorkflowService(session).approve_exception(
            actor=actor,
            request=transition_request,
            expected_version=request.expected_version,
        )
        response = JobResponse.from_job(job)
        session.commit()
        return response
    except (
        WorkflowError,
        WorkflowValidationError,
        WorkflowConflictError,
        StaleDataError,
    ) as error:
        _handle(error, session)


@router.patch("/admin/employees/{employee_id}/availability")
def set_employee_availability(
    employee_id: str,
    request: AvailabilityRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> dict[str, str]:
    employee = session.get(User, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        updated = WorkflowService(session).set_availability(
            actor=actor, employee=employee, **request.model_dump()
        )
        response = {"employee_id": updated.id, "availability": updated.availability.value}
        session.commit()
        return response
    except (WorkflowError, WorkflowValidationError) as error:
        _handle(error, session)
