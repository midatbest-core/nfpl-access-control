"""Employee self-service and protected Admin directory endpoints."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.models import AccountStatus
from nfpl_access_control.schemas.employees import (
    AccountActionRequest,
    AvailabilityUpdateRequest,
    EmployeePageResponse,
    EmployeeResponse,
)
from nfpl_access_control.services.employees import (
    EmployeeConflictError,
    EmployeeManagementError,
    EmployeeManagementService,
    EmployeeNotFoundError,
    EmployeeValidationError,
)

router = APIRouter(tags=["employees"])


def _handle(error: Exception, session: DatabaseSession) -> None:
    if isinstance(error, EmployeeManagementError):
        session.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "reason_code": error.decision.reason_code,
                "explanation": error.decision.explanation,
            },
        ) from error
    session.rollback()
    if isinstance(error, EmployeeConflictError | IntegrityError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/employees/me", response_model=EmployeeResponse)
def my_profile(actor: CurrentActor, session: DatabaseSession) -> EmployeeResponse:
    try:
        return EmployeeResponse.from_record(EmployeeManagementService(session).get_self(actor))
    except EmployeeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/employees/me/availability", response_model=EmployeeResponse)
def my_availability(
    request: AvailabilityUpdateRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    try:
        EmployeeManagementService(session).set_own_availability(
            actor=actor,
            availability=request.availability,
            reason=request.reason,
        )
        response = EmployeeResponse.from_record(EmployeeManagementService(session).get_self(actor))
        session.commit()
        return response
    except (EmployeeValidationError, EmployeeConflictError, IntegrityError) as error:
        _handle(error, session)


@router.get("/admin/employees", response_model=EmployeePageResponse)
def list_employees(
    actor: CurrentActor,
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
) -> EmployeePageResponse:
    try:
        result = EmployeeManagementService(session).list_employees(
            actor=actor,
            page=page,
            limit=limit,
            search=search,
        )
        return EmployeePageResponse.from_page(result)
    except (EmployeeManagementError, EmployeeValidationError) as error:
        _handle(error, session)


@router.get("/admin/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: str,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    try:
        record = EmployeeManagementService(session).get_employee(
            actor=actor, employee_id=employee_id
        )
        return EmployeeResponse.from_record(record)
    except EmployeeManagementError as error:
        _handle(error, session)
    except EmployeeValidationError as error:
        session.rollback()
        raise HTTPException(status_code=404, detail="Employee not found") from error


def _transition(
    employee_id: str,
    target: AccountStatus,
    expected_source: AccountStatus,
    request: AccountActionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    try:
        updated = EmployeeManagementService(session).transition_account_by_id(
            actor=actor,
            employee_id=employee_id,
            target=target,
            expected_source=expected_source,
            reason=request.reason,
        )
        response = EmployeeResponse.from_record(
            EmployeeManagementService(session).get_employee(actor=actor, employee_id=updated.id)
        )
        session.commit()
        return response
    except EmployeeNotFoundError as error:
        session.rollback()
        raise HTTPException(status_code=404, detail="Employee not found") from error
    except (
        EmployeeManagementError,
        EmployeeValidationError,
        EmployeeConflictError,
        IntegrityError,
    ) as error:
        _handle(error, session)


@router.post("/admin/employees/{employee_id}/approve", response_model=EmployeeResponse)
def approve_employee(
    employee_id: str,
    request: AccountActionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    return _transition(
        employee_id,
        AccountStatus.ACTIVE,
        AccountStatus.PENDING,
        request,
        actor,
        session,
    )


@router.post("/admin/employees/{employee_id}/reject", response_model=EmployeeResponse)
def reject_employee(
    employee_id: str,
    request: AccountActionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    return _transition(
        employee_id,
        AccountStatus.DISABLED,
        AccountStatus.PENDING,
        request,
        actor,
        session,
    )


@router.post("/admin/employees/{employee_id}/activate", response_model=EmployeeResponse)
def activate_employee(
    employee_id: str,
    request: AccountActionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    return _transition(
        employee_id,
        AccountStatus.ACTIVE,
        AccountStatus.DISABLED,
        request,
        actor,
        session,
    )


@router.post("/admin/employees/{employee_id}/deactivate", response_model=EmployeeResponse)
def deactivate_employee(
    employee_id: str,
    request: AccountActionRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> EmployeeResponse:
    return _transition(
        employee_id,
        AccountStatus.DISABLED,
        AccountStatus.ACTIVE,
        request,
        actor,
        session,
    )
