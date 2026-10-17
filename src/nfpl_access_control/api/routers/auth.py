"""Public employee registration/login and authenticated logout."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError

from nfpl_access_control.api.dependencies import (
    CurrentActor,
    DatabaseSession,
    bearer_scheme,
)
from nfpl_access_control.schemas.employees import (
    LoginRequest,
    LoginResponse,
    RegistrationRequest,
    RegistrationResponse,
)
from nfpl_access_control.services.authentication import (
    AuthenticationError,
    EmployeeAuthenticationService,
    RegistrationConflictError,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegistrationRequest,
    session: DatabaseSession,
) -> RegistrationResponse:
    try:
        user = EmployeeAuthenticationService(session).register(
            display_name=request.name,
            email=request.email,
            password=request.password,
            branch_id=request.branch_id,
        )
        response = RegistrationResponse.from_user(user)
        session.commit()
        return response
    except RegistrationConflictError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except AuthenticationError as error:
        session.rollback()
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Registration conflicts with existing data."
        ) from error


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, session: DatabaseSession) -> LoginResponse:
    try:
        result = EmployeeAuthenticationService(session).login(
            email=request.email,
            password=request.password,
        )
        response = LoginResponse(access_token=result.token, expires_at=result.expires_at)
        session.commit()
        return response
    except AuthenticationError as error:
        session.commit()
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    actor: CurrentActor,
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> None:
    try:
        EmployeeAuthenticationService(session).logout(
            actor=actor,
            token=credentials.credentials,
        )
        session.commit()
    except AuthenticationError as error:
        session.rollback()
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
