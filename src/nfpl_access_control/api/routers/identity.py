"""Authenticated actor routes."""

from fastapi import APIRouter

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.schemas.employees import EmployeeResponse
from nfpl_access_control.services.employees import EmployeeManagementService

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/me", response_model=EmployeeResponse)
def get_my_identity(actor: CurrentActor, session: DatabaseSession) -> EmployeeResponse:
    return EmployeeResponse.from_record(EmployeeManagementService(session).get_self(actor))
