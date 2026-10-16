"""Structured authorization outcomes with safe public redaction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nfpl_access_control.models import Permission


class ReasonCode(StrEnum):
    ALLOWED = "allowed"
    AUTHENTICATION_REQUIRED = "authentication_required"
    ACTOR_INACTIVE = "actor_inactive"
    POLICY_DATA_INVALID = "policy_data_invalid"
    MISSING_PERMISSION = "missing_permission"
    MISSING_VISIBILITY = "missing_visibility"
    CLIENT_SCOPE_MISMATCH = "client_scope_mismatch"
    BRANCH_SCOPE_MISMATCH = "branch_scope_mismatch"
    DIRECTION_SCOPE_MISMATCH = "direction_scope_mismatch"
    MODE_SCOPE_MISMATCH = "mode_scope_mismatch"
    ACCESS_NOT_YET_EFFECTIVE = "access_not_yet_effective"
    ACCESS_EXPIRED = "access_expired"
    ACCESS_REVOKED = "access_revoked"
    ADMIN_REQUIRED = "admin_required"
    SELF_ESCALATION_FORBIDDEN = "self_escalation_forbidden"
    SENSITIVE_APPROVAL_REQUIRED = "sensitive_approval_required"
    JOB_NOT_FOUND_OR_NOT_VISIBLE = "job_not_found_or_not_visible"
    MISSING_RESPONSIBILITY = "missing_responsibility"
    EMPLOYEE_ABSENT = "employee_absent"
    INVALID_STAGE = "invalid_stage"
    STALE_VERSION = "stale_version"
    SELF_CHECK_FORBIDDEN = "self_check_forbidden"
    ASSIGNMENT_INELIGIBLE = "assignment_ineligible"
    DELEGATION_NOT_EFFECTIVE = "delegation_not_effective"
    INDEPENDENT_APPROVAL_REQUIRED = "independent_approval_required"
    SELF_APPROVAL_FORBIDDEN = "self_approval_forbidden"
    PROTECTED_FIELD = "protected_field"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason_code: ReasonCode
    explanation: str
    permission: Permission
    job_visible: bool | None = None

    def for_public_job_response(self) -> AuthorizationDecision:
        """Hide job existence and scope from actors without visibility."""

        if self.allowed:
            return self
        if self.job_visible is False or (
            self.permission is Permission.JOB_VIEW and not self.allowed
        ):
            return AuthorizationDecision(
                allowed=False,
                reason_code=ReasonCode.JOB_NOT_FOUND_OR_NOT_VISIBLE,
                explanation="The job does not exist or is not visible to this actor.",
                permission=self.permission,
                job_visible=False,
            )
        return self
