"""Protected internal history and sanitized Client Viewer endpoints."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.authorization import AuthorizationEngine, Scope
from nfpl_access_control.models import AuditEvent, Job, Permission
from nfpl_access_control.schemas.history import (
    AuditEventResponse,
    ClientStatusResponse,
    ClientUpdatePageResponse,
    ClientUpdateResponse,
    HistoricalEligibilityResponse,
    JobVersionResponse,
    OperationalHistoryResponse,
    VersionDiffResponse,
)
from nfpl_access_control.services.client_updates import (
    ClientAccessError,
    ClientCursorError,
    ClientUpdateService,
)
from nfpl_access_control.services.history import HistoryService, HistoryValidationError

router = APIRouter(tags=["history"])


def _job(session: DatabaseSession, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or not visible")
    return job


def _admin_job(session: DatabaseSession, actor: CurrentActor, job_id: str) -> Job:
    job = _job(session, job_id)
    decision = AuthorizationEngine(session).authorize_admin(
        actor, Permission.JOB_VIEW, requested_scope=Scope.for_job(job)
    )
    if not decision.allowed:
        raise HTTPException(status_code=404, detail="Job not found or not visible")
    return job


def _version_response(item) -> JobVersionResponse:
    return JobVersionResponse(
        id=item.id,
        job_id=item.job_id,
        version_number=item.version_number,
        recorded_at=item.recorded_at,
        actor_user_id=item.actor_user_id,
        action=item.action,
        reason=item.reason,
        snapshot=item.snapshot,
    )


@router.get(
    "/jobs/{job_id}/operational-history",
    response_model=list[OperationalHistoryResponse],
)
def operational_history(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
    before_version: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[OperationalHistoryResponse]:
    job = _job(session, job_id)
    decision = AuthorizationEngine(session).authorize_job(actor, Permission.JOB_FILE, job)
    if not decision.allowed:
        raise HTTPException(status_code=404, detail="Job not found or not visible")
    try:
        items = HistoryService(session).operational_history(
            job_id, before_version=before_version, limit=limit
        )
    except HistoryValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return [OperationalHistoryResponse.from_item(item) for item in items]


@router.get("/admin/jobs/{job_id}/versions", response_model=list[JobVersionResponse])
def list_versions(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
    before_version: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[JobVersionResponse]:
    _admin_job(session, actor, job_id)
    versions = HistoryService(session).list_versions(
        job_id, before_version=before_version, limit=limit
    )
    return [_version_response(item) for item in versions]


@router.get(
    "/admin/jobs/{job_id}/versions/{version_number}",
    response_model=JobVersionResponse,
)
def get_version(
    job_id: str,
    version_number: int,
    actor: CurrentActor,
    session: DatabaseSession,
) -> JobVersionResponse:
    _admin_job(session, actor, job_id)
    version = HistoryService(session).version(job_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Job version not found")
    return _version_response(version)


@router.get("/admin/jobs/{job_id}/state-at", response_model=JobVersionResponse)
def state_at(
    job_id: str,
    at: datetime,
    actor: CurrentActor,
    session: DatabaseSession,
) -> JobVersionResponse:
    _admin_job(session, actor, job_id)
    try:
        version = HistoryService(session).state_at(job_id, at)
    except HistoryValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if version is None:
        raise HTTPException(status_code=404, detail="No historical state is available")
    return _version_response(version)


@router.get("/admin/jobs/{job_id}/diff", response_model=list[VersionDiffResponse])
def diff_versions(
    job_id: str,
    from_version: int,
    to_version: int,
    actor: CurrentActor,
    session: DatabaseSession,
) -> list[VersionDiffResponse]:
    _admin_job(session, actor, job_id)
    try:
        changes = HistoryService(session).diff(job_id, from_version, to_version)
    except HistoryValidationError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return [VersionDiffResponse.from_diff(item) for item in changes]


@router.get("/admin/jobs/{job_id}/field-changes", response_model=list[JobVersionResponse])
def field_changes(
    job_id: str,
    field: str,
    actor: CurrentActor,
    session: DatabaseSession,
) -> list[JobVersionResponse]:
    _admin_job(session, actor, job_id)
    return [
        _version_response(item) for item in HistoryService(session).changes_for_field(job_id, field)
    ]


@router.get("/admin/jobs/{job_id}/audit", response_model=list[AuditEventResponse])
def job_audit(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AuditEventResponse]:
    _admin_job(session, actor, job_id)
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.job_id == job_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return [
        AuditEventResponse(
            id=item.id,
            job_id=item.job_id,
            actor_user_id=item.actor_user_id,
            action=item.action,
            occurred_at=item.occurred_at,
            reason=item.reason,
            before_state=item.before_state,
            after_state=item.after_state,
            authorization_context=item.authorization_context,
            affected_job_version=item.affected_job_version,
            denied=item.denied,
        )
        for item in events
    ]


@router.get(
    "/admin/jobs/{job_id}/historical-eligibility",
    response_model=HistoricalEligibilityResponse,
)
def historical_eligibility(
    job_id: str,
    permission: Permission,
    at: datetime,
    actor: CurrentActor,
    session: DatabaseSession,
) -> HistoricalEligibilityResponse:
    _admin_job(session, actor, job_id)
    try:
        result = HistoryService(session).historical_eligibility(
            job_id=job_id, permission=permission, at=at
        )
    except HistoryValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return HistoricalEligibilityResponse.from_result(result)


@router.get("/client/jobs/{job_id}/status", response_model=ClientStatusResponse)
def client_status(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
) -> ClientStatusResponse:
    job = _job(session, job_id)
    try:
        item = ClientUpdateService(session).status(actor=actor, job=job)
    except ClientAccessError as error:
        raise HTTPException(status_code=404, detail="Job not found or not visible") from error
    return ClientStatusResponse(
        job_id=item.job_id,
        reference=item.reference,
        stage=item.stage,
        progress_percent=item.progress_percent,
        updated_at=item.updated_at,
        version=item.version,
    )


@router.get(
    "/client/jobs/{job_id}/history",
    response_model=list[ClientUpdateResponse],
)
def client_history(
    job_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
    before_version: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ClientUpdateResponse]:
    job = _job(session, job_id)
    try:
        items = ClientUpdateService(session).history(
            actor=actor,
            job=job,
            before_version=before_version,
            limit=limit,
        )
    except ClientAccessError as error:
        raise HTTPException(status_code=404, detail="Job not found or not visible") from error
    return [ClientUpdateResponse.from_update(item) for item in items]


@router.get("/client/updates", response_model=ClientUpdatePageResponse)
def client_updates(
    actor: CurrentActor,
    session: DatabaseSession,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> ClientUpdatePageResponse:
    try:
        page = ClientUpdateService(session).updates(actor=actor, cursor=cursor, limit=limit)
    except ClientAccessError as error:
        raise HTTPException(status_code=403, detail="Client Viewer access required") from error
    except ClientCursorError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ClientUpdatePageResponse(
        items=[ClientUpdateResponse.from_update(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
