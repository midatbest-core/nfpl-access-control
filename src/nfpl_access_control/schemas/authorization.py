"""Authorization decision API contracts."""

from __future__ import annotations

from pydantic import BaseModel

from nfpl_access_control.authorization import AuthorizationDecision, ReasonCode
from nfpl_access_control.models import Permission


class AuthorizationRequest(BaseModel):
    permission: Permission


class AuthorizationDecisionResponse(BaseModel):
    allowed: bool
    reason_code: ReasonCode
    explanation: str
    permission: Permission

    @classmethod
    def from_decision(cls, decision: AuthorizationDecision) -> AuthorizationDecisionResponse:
        return cls(
            allowed=decision.allowed,
            reason_code=decision.reason_code,
            explanation=decision.explanation,
            permission=decision.permission,
        )
