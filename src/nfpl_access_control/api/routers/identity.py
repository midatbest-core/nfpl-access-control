"""Authenticated actor routes."""

from fastapi import APIRouter

from nfpl_access_control.api.dependencies import CurrentActor
from nfpl_access_control.schemas.identity import AuthenticatedUserResponse

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/me", response_model=AuthenticatedUserResponse)
def get_my_identity(actor: CurrentActor) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse.model_validate(actor)
