"""Admin-only role and role-assignment mutations."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.schemas.rbac import (
    RoleAssignmentCreateRequest,
    RoleAssignmentResponse,
    RoleAssignmentRevokeRequest,
    RoleCreateRequest,
    RoleResponse,
)
from nfpl_access_control.services.role_management import (
    RoleManagementConflictError,
    RoleManagementError,
    RoleManagementService,
    RoleManagementValidationError,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _raise_management_error(error: Exception, session: DatabaseSession) -> None:
    session.rollback()
    if isinstance(error, RoleManagementError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "reason_code": error.decision.reason_code,
                "explanation": error.decision.explanation,
            },
        ) from error
    if isinstance(error, RoleManagementConflictError | StaleDataError | IntegrityError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The access change conflicts with current state.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    ) from error


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    request: RoleCreateRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> RoleResponse:
    try:
        role = RoleManagementService(session).create_role(
            actor=actor,
            slug=request.slug,
            name=request.name,
            description=request.description,
            permissions=request.permissions,
        )
        response = RoleResponse.from_role(role)
        session.commit()
        return response
    except (
        RoleManagementError,
        RoleManagementValidationError,
        RoleManagementConflictError,
        IntegrityError,
    ) as error:
        _raise_management_error(error, session)


@router.post(
    "/role-assignments",
    response_model=RoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_role(
    request: RoleAssignmentCreateRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> RoleAssignmentResponse:
    try:
        assignment = RoleManagementService(session).grant_role(
            actor=actor,
            target_user_id=request.target_user_id,
            role_slug=request.role_slug,
            scope=request.scope.to_domain(),
            reason=request.reason,
            valid_from=request.valid_from,
            valid_until=request.valid_until,
        )
        response = RoleAssignmentResponse.model_validate(assignment)
        session.commit()
        return response
    except (
        RoleManagementError,
        RoleManagementValidationError,
        RoleManagementConflictError,
        IntegrityError,
    ) as error:
        _raise_management_error(error, session)


@router.post(
    "/role-assignments/{assignment_id}/revoke",
    response_model=RoleAssignmentResponse,
)
def revoke_role(
    assignment_id: str,
    request: RoleAssignmentRevokeRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> RoleAssignmentResponse:
    try:
        assignment = RoleManagementService(session).revoke_role(
            actor=actor,
            assignment_id=assignment_id,
            reason=request.reason,
        )
        response = RoleAssignmentResponse.model_validate(assignment)
        session.commit()
        return response
    except (
        RoleManagementError,
        RoleManagementValidationError,
        RoleManagementConflictError,
        IntegrityError,
        StaleDataError,
    ) as error:
        _raise_management_error(error, session)
