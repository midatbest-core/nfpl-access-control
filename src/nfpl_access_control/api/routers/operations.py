"""Phase 5C absence, notifications, work queue, and Admin dashboard APIs."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.models import (
    AbsenceNomination,
    AbsenceNominationJob,
    Job,
)
from nfpl_access_control.schemas.operations import (
    AbsenceNominationCreate,
    AbsenceNominationResponse,
    AbsenceOutcomeResponse,
    AbsenceOverrideRequest,
    AdminJobResponse,
    DashboardOverviewResponse,
    NotificationResponse,
    UrgentRequestResponse,
    VersionedDecision,
    VersionedReason,
    WorkQueuePage,
    WorkQueueResponse,
)
from nfpl_access_control.services.absence import (
    AbsenceConflictError,
    AbsenceError,
    AbsenceService,
    AbsenceValidationError,
)
from nfpl_access_control.services.dashboard import DashboardAccessError, DashboardService
from nfpl_access_control.services.notifications import (
    NotificationAccessError,
    NotificationService,
    NotificationValidationError,
)
from nfpl_access_control.services.work_queue import WorkQueueService

router = APIRouter(tags=["operations"])


def _handle(error: Exception, session: DatabaseSession) -> None:
    if isinstance(error, (AbsenceError, DashboardAccessError)):
        session.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "reason_code": error.decision.reason_code,
                "explanation": error.decision.explanation,
            },
        ) from error
    session.rollback()
    if isinstance(error, (AbsenceConflictError, StaleDataError, IntegrityError)):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, NotificationAccessError):
        raise HTTPException(
            status_code=404, detail="Notification not found or not visible"
        ) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/absence-nominations",
    response_model=AbsenceNominationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_absence_nomination(
    request: AbsenceNominationCreate,
    actor: CurrentActor,
    session: DatabaseSession,
) -> AbsenceNominationResponse:
    try:
        record = AbsenceService(session).nominate(actor=actor, **request.model_dump())
        response = AbsenceNominationResponse.model_validate(record)
        session.commit()
        return response
    except (AbsenceValidationError, AbsenceConflictError, IntegrityError) as error:
        _handle(error, session)


@router.get("/absence-nominations", response_model=list[AbsenceNominationResponse])
def own_absence_nominations(
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AbsenceNominationResponse]:
    records = session.scalars(
        select(AbsenceNomination)
        .where(AbsenceNomination.requester_user_id == actor.id)
        .order_by(AbsenceNomination.requested_at.desc())
        .limit(limit)
    )
    return [AbsenceNominationResponse.model_validate(item) for item in records]


@router.post(
    "/admin/absence-nominations/{nomination_id}/decision",
    response_model=AbsenceNominationResponse,
)
def decide_absence_nomination(
    nomination_id: str,
    request: VersionedDecision,
    actor: CurrentActor,
    session: DatabaseSession,
) -> AbsenceNominationResponse:
    try:
        DashboardService(session).overview(actor=actor)
    except DashboardAccessError as error:
        _handle(error, session)
    nomination = session.get(AbsenceNomination, nomination_id)
    if nomination is None:
        raise HTTPException(status_code=404, detail="Nomination not found")
    try:
        record = AbsenceService(session).decide(
            actor=actor, nomination=nomination, **request.model_dump()
        )
        response = AbsenceNominationResponse.model_validate(record)
        session.commit()
        return response
    except (
        AbsenceError,
        AbsenceValidationError,
        AbsenceConflictError,
        IntegrityError,
        StaleDataError,
    ) as error:
        _handle(error, session)


@router.post(
    "/admin/absence-nominations/{nomination_id}/revoke",
    response_model=AbsenceNominationResponse,
)
def revoke_absence_nomination(
    nomination_id: str,
    request: VersionedReason,
    actor: CurrentActor,
    session: DatabaseSession,
) -> AbsenceNominationResponse:
    try:
        DashboardService(session).overview(actor=actor)
    except DashboardAccessError as error:
        _handle(error, session)
    nomination = session.get(AbsenceNomination, nomination_id)
    if nomination is None:
        raise HTTPException(status_code=404, detail="Nomination not found")
    try:
        record = AbsenceService(session).revoke(
            actor=actor, nomination=nomination, **request.model_dump()
        )
        response = AbsenceNominationResponse.model_validate(record)
        session.commit()
        return response
    except (AbsenceError, AbsenceValidationError, AbsenceConflictError, StaleDataError) as error:
        _handle(error, session)


@router.get(
    "/admin/absence-nominations/{nomination_id}/outcomes",
    response_model=list[AbsenceOutcomeResponse],
)
def absence_outcomes(
    nomination_id: str, actor: CurrentActor, session: DatabaseSession
) -> list[AbsenceOutcomeResponse]:
    try:
        DashboardService(session).overview(actor=actor)
    except DashboardAccessError as error:
        _handle(error, session)
    records = session.scalars(
        select(AbsenceNominationJob).where(AbsenceNominationJob.nomination_id == nomination_id)
    )
    return [AbsenceOutcomeResponse.model_validate(item) for item in records]


@router.post(
    "/admin/absence-outcomes/{outcome_id}/override",
    response_model=AbsenceOutcomeResponse,
)
def override_absence_outcome(
    outcome_id: str,
    request: AbsenceOverrideRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> AbsenceOutcomeResponse:
    try:
        DashboardService(session).overview(actor=actor)
    except DashboardAccessError as error:
        _handle(error, session)
    outcome = session.get(AbsenceNominationJob, outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="Absence outcome not found")
    try:
        record = AbsenceService(session).override_job(
            actor=actor, outcome=outcome, **request.model_dump()
        )
        response = AbsenceOutcomeResponse.model_validate(record)
        session.commit()
        return response
    except (AbsenceError, AbsenceValidationError, AbsenceConflictError, IntegrityError) as error:
        _handle(error, session)


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    unread_only: bool = False,
) -> list[NotificationResponse]:
    records = NotificationService(session).list_for_actor(
        actor=actor, limit=limit, before=before, unread_only=unread_only
    )
    return [NotificationResponse.model_validate(item) for item in records]


@router.get("/notifications/unread-count")
def unread_notification_count(actor: CurrentActor, session: DatabaseSession) -> dict[str, int]:
    return {"count": NotificationService(session).unread_count(actor=actor)}


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str, actor: CurrentActor, session: DatabaseSession
) -> NotificationResponse:
    try:
        record = NotificationService(session).mark_read(
            actor=actor, notification_id=notification_id
        )
        response = NotificationResponse.model_validate(record)
        session.commit()
        return response
    except (NotificationAccessError, NotificationValidationError) as error:
        _handle(error, session)


@router.get("/my-work", response_model=WorkQueuePage)
def my_work(
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> WorkQueuePage:
    service = WorkQueueService(session)
    try:
        items, next_cursor = service.page(actor=actor, limit=limit, cursor=cursor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return WorkQueuePage(
        items=[WorkQueueResponse.model_validate(item) for item in items],
        count=service.count(actor=actor),
        limit=limit,
        next_cursor=next_cursor,
    )


@router.get("/admin/dashboard/overview", response_model=DashboardOverviewResponse)
def admin_overview(actor: CurrentActor, session: DatabaseSession) -> DashboardOverviewResponse:
    try:
        item = DashboardService(session).overview(actor=actor)
        return DashboardOverviewResponse.model_validate(item)
    except DashboardAccessError as error:
        _handle(error, session)


@router.get("/admin/dashboard/urgent-requests", response_model=list[UrgentRequestResponse])
def urgent_requests(
    actor: CurrentActor,
    session: DatabaseSession,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[UrgentRequestResponse]:
    try:
        items = DashboardService(session).urgent_requests(actor=actor, limit=limit)
        return [UrgentRequestResponse.model_validate(item) for item in items]
    except DashboardAccessError as error:
        _handle(error, session)


@router.get("/admin/jobs", response_model=list[AdminJobResponse])
def admin_jobs(
    actor: CurrentActor,
    session: DatabaseSession,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AdminJobResponse]:
    try:
        rows = DashboardService(session).list_jobs(
            actor=actor, search=search, limit=limit, offset=offset
        )
    except DashboardAccessError as error:
        _handle(error, session)
    return [
        AdminJobResponse(
            id=job.id,
            reference=job.reference,
            client_id=job.client_id,
            branch_id=job.branch_id,
            stage=job.stage,
            maker_user_id=maker,
            checker_user_id=checker,
            filing_officer_user_id=filer,
            created_at=job.created_at,
            updated_at=job.updated_at,
            archived_at=job.archived_at,
            version=job.version,
        )
        for job, maker, checker, filer in rows
    ]


@router.post("/admin/jobs/{job_id}/archive", response_model=AdminJobResponse)
def archive_job(
    job_id: str,
    request: VersionedReason,
    actor: CurrentActor,
    session: DatabaseSession,
) -> AdminJobResponse:
    try:
        DashboardService(session).overview(actor=actor)
    except DashboardAccessError as error:
        _handle(error, session)
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        job = DashboardService(session).archive(actor=actor, job=job, **request.model_dump())
        response = AdminJobResponse(
            id=job.id,
            reference=job.reference,
            client_id=job.client_id,
            branch_id=job.branch_id,
            stage=job.stage,
            maker_user_id=None,
            checker_user_id=None,
            filing_officer_user_id=None,
            created_at=job.created_at,
            updated_at=job.updated_at,
            archived_at=job.archived_at,
            version=job.version,
        )
        session.commit()
        return response
    except (DashboardAccessError, ValueError, StaleDataError) as error:
        _handle(error, session)
