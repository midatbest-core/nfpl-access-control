"""Protected authorization explanation endpoint."""

from fastapi import APIRouter

from nfpl_access_control.api.dependencies import CurrentActor, DatabaseSession
from nfpl_access_control.authorization import (
    AuthorizationDecision,
    AuthorizationEngine,
    ReasonCode,
)
from nfpl_access_control.authorization.roles import JOB_PERMISSIONS
from nfpl_access_control.models import Job
from nfpl_access_control.schemas.authorization import (
    AuthorizationDecisionResponse,
    AuthorizationRequest,
)

router = APIRouter(prefix="/authorization", tags=["authorization"])


@router.post(
    "/jobs/{job_id}",
    response_model=AuthorizationDecisionResponse,
)
def explain_job_authorization(
    job_id: str,
    request: AuthorizationRequest,
    actor: CurrentActor,
    session: DatabaseSession,
) -> AuthorizationDecisionResponse:
    if request.permission not in JOB_PERMISSIONS:
        decision = AuthorizationDecision(
            allowed=False,
            reason_code=ReasonCode.MISSING_PERMISSION,
            explanation="The requested permission is not a job action.",
            permission=request.permission,
        )
        return AuthorizationDecisionResponse.from_decision(decision)

    job = session.get(Job, job_id)
    if job is None:
        decision = AuthorizationDecision(
            allowed=False,
            reason_code=ReasonCode.JOB_NOT_FOUND_OR_NOT_VISIBLE,
            explanation="The job does not exist or is not visible to this actor.",
            permission=request.permission,
        )
    else:
        decision = (
            AuthorizationEngine(session)
            .authorize_job(actor, request.permission, job)
            .for_public_job_response()
        )
    return AuthorizationDecisionResponse.from_decision(decision)
