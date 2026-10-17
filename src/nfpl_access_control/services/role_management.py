"""Transactional building blocks for roles, grants, and revocations."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import (
    AuthorizationDecision,
    AuthorizationEngine,
    ReasonCode,
    Scope,
)
from nfpl_access_control.authorization.roles import (
    ADMIN_ROLE,
    CONFIGURABLE_ROLE_PERMISSIONS,
)
from nfpl_access_control.models import (
    AccountStatus,
    AssignmentEventType,
    Permission,
    Role,
    RoleAssignment,
    RoleAssignmentEvent,
    RolePermission,
    User,
)
from nfpl_access_control.services.audit import AuditService

ROLE_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


class RoleManagementError(Exception):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.explanation)
        self.decision = decision


class RoleManagementValidationError(ValueError):
    pass


class RoleManagementConflictError(RuntimeError):
    pass


class RoleManagementService:
    """Mutates RBAC state in the caller's open database transaction."""

    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)

    def create_role(
        self,
        *,
        actor: User,
        slug: str,
        name: str,
        description: str,
        permissions: set[Permission],
    ) -> Role:
        current_time = datetime.now(UTC)
        decision = self.authorization.authorize_admin(
            actor,
            Permission.ROLE_MANAGE,
            requested_scope=Scope.global_scope(),
            at=current_time,
        )
        self._require_allowed(decision, actor, "role.create.denied", current_time)
        normalized_slug = slug.strip().lower()
        if not ROLE_SLUG_PATTERN.fullmatch(normalized_slug):
            raise RoleManagementValidationError(
                "Role slug must be 3-64 lowercase letters, digits, or hyphens."
            )
        if not name.strip():
            raise RoleManagementValidationError("Role name is required.")
        if not permissions:
            raise RoleManagementValidationError("At least one permission is required.")
        unsafe = permissions - CONFIGURABLE_ROLE_PERMISSIONS
        if unsafe:
            raise RoleManagementValidationError(
                "Configurable roles cannot contain access-management permissions."
            )
        if self.session.scalar(select(Role.id).where(Role.slug == normalized_slug)):
            raise RoleManagementConflictError("A role with this slug already exists.")

        role = Role(
            slug=normalized_slug,
            name=name.strip(),
            description=description.strip(),
            is_system=False,
            permissions=[
                RolePermission(permission=permission) for permission in sorted(permissions, key=str)
            ],
        )
        self.session.add(role)
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="role.created",
            reason="Configurable role created.",
            occurred_at=current_time,
            decision=decision,
            after={
                "role_id": role.id,
                "slug": role.slug,
                "permissions": sorted(item.permission.value for item in role.permissions),
            },
        )
        self.session.flush()
        return role

    def grant_role(
        self,
        *,
        actor: User,
        target_user_id: str,
        role_slug: str,
        scope: Scope,
        reason: str,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        now: datetime | None = None,
    ) -> RoleAssignment:
        current_time = now or datetime.now(UTC)
        self._require_aware(current_time, "now")
        starts_at = valid_from or current_time
        self._require_aware(starts_at, "valid_from")
        if valid_until is not None:
            self._require_aware(valid_until, "valid_until")
            if valid_until <= starts_at:
                raise RoleManagementValidationError("valid_until must be later than valid_from.")
        if not scope.is_valid():
            raise RoleManagementValidationError(
                "Every scope dimension must explicitly select all or one value."
            )
        if not reason.strip():
            raise RoleManagementValidationError("A grant reason is required.")
        if actor.id == target_user_id:
            self._deny(
                actor,
                AuthorizationDecision(
                    allowed=False,
                    reason_code=ReasonCode.SELF_ESCALATION_FORBIDDEN,
                    explanation="Administrators cannot grant roles to themselves.",
                    permission=Permission.ACCESS_GRANT,
                ),
                "role.grant.denied",
                current_time,
                {"target_user_id": target_user_id, "role_slug": role_slug},
            )

        admin_decision = self.authorization.authorize_admin(
            actor,
            Permission.ACCESS_GRANT,
            requested_scope=scope,
            at=current_time,
        )
        self._require_allowed(
            admin_decision,
            actor,
            "role.grant.denied",
            current_time,
            {"target_user_id": target_user_id, "role_slug": role_slug},
        )

        target = self.session.get(User, target_user_id)
        if (
            target is None
            or not target.is_active
            or target.account_status is not AccountStatus.ACTIVE
        ):
            raise RoleManagementValidationError("The target user does not exist or is inactive.")
        role = self.session.scalar(select(Role).where(Role.slug == role_slug))
        if role is None:
            raise RoleManagementValidationError("The requested role does not exist.")
        if role.slug == ADMIN_ROLE:
            self._deny(
                actor,
                AuthorizationDecision(
                    allowed=False,
                    reason_code=ReasonCode.SENSITIVE_APPROVAL_REQUIRED,
                    explanation=(
                        "Admin grants require the independent sensitive-access approval flow."
                    ),
                    permission=Permission.ACCESS_GRANT,
                ),
                "role.grant.denied",
                current_time,
                {"target_user_id": target_user_id, "role_slug": role_slug},
            )

        duplicate = self.session.scalar(
            select(RoleAssignment.id).where(
                RoleAssignment.user_id == target_user_id,
                RoleAssignment.role_id == role.id,
                RoleAssignment.client_id == scope.client_id,
                RoleAssignment.all_clients == scope.all_clients,
                RoleAssignment.branch_id == scope.branch_id,
                RoleAssignment.all_branches == scope.all_branches,
                RoleAssignment.direction == scope.direction,
                RoleAssignment.all_directions == scope.all_directions,
                RoleAssignment.mode == scope.mode,
                RoleAssignment.all_modes == scope.all_modes,
                RoleAssignment.revoked_at.is_(None),
                or_(
                    RoleAssignment.valid_until.is_(None),
                    RoleAssignment.valid_until > current_time,
                ),
            )
        )
        if duplicate is not None:
            raise RoleManagementConflictError(
                "An overlapping identical role assignment already exists."
            )

        assignment = RoleAssignment(
            user_id=target.id,
            role_id=role.id,
            client_id=scope.client_id,
            all_clients=scope.all_clients,
            branch_id=scope.branch_id,
            all_branches=scope.all_branches,
            direction=scope.direction,
            all_directions=scope.all_directions,
            mode=scope.mode,
            all_modes=scope.all_modes,
            valid_from=starts_at,
            valid_until=valid_until,
            granted_by_user_id=actor.id,
            grant_reason=reason.strip(),
        )
        assignment.events.append(
            RoleAssignmentEvent(
                event_type=AssignmentEventType.GRANTED,
                actor_user_id=actor.id,
                occurred_at=current_time,
                reason=reason.strip(),
            )
        )
        self.session.add(assignment)
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="role.granted",
            reason=reason.strip(),
            occurred_at=current_time,
            decision=admin_decision,
            after=self._assignment_snapshot(assignment),
        )
        self.session.flush()
        return assignment

    def revoke_role(
        self,
        *,
        actor: User,
        assignment_id: str,
        reason: str,
        now: datetime | None = None,
    ) -> RoleAssignment:
        current_time = now or datetime.now(UTC)
        self._require_aware(current_time, "now")
        if not reason.strip():
            raise RoleManagementValidationError("A revocation reason is required.")
        assignment = self.session.get(RoleAssignment, assignment_id)
        if assignment is None:
            raise RoleManagementValidationError("The role assignment does not exist.")
        if assignment.revoked_at is not None:
            raise RoleManagementConflictError("The role assignment is already revoked.")

        scope = Scope(
            all_clients=assignment.all_clients,
            client_id=assignment.client_id,
            all_branches=assignment.all_branches,
            branch_id=assignment.branch_id,
            all_directions=assignment.all_directions,
            direction=assignment.direction,
            all_modes=assignment.all_modes,
            mode=assignment.mode,
        )
        decision = self.authorization.authorize_admin(
            actor,
            Permission.ACCESS_REVOKE,
            requested_scope=scope,
            at=current_time,
        )
        self._require_allowed(
            decision,
            actor,
            "role.revoke.denied",
            current_time,
            {"assignment_id": assignment.id},
        )

        before = self._assignment_snapshot(assignment)
        assignment.revoked_at = current_time
        assignment.revoked_by_user_id = actor.id
        assignment.revoke_reason = reason.strip()
        assignment.events.append(
            RoleAssignmentEvent(
                event_type=AssignmentEventType.REVOKED,
                actor_user_id=actor.id,
                occurred_at=current_time,
                reason=reason.strip(),
            )
        )
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="role.revoked",
            reason=reason.strip(),
            occurred_at=current_time,
            decision=decision,
            before=before,
            after=self._assignment_snapshot(assignment),
        )
        self.session.flush()
        return assignment

    def _require_allowed(
        self,
        decision: AuthorizationDecision,
        actor: User,
        action: str,
        occurred_at: datetime,
        context: dict[str, object] | None = None,
    ) -> None:
        if not decision.allowed:
            self._deny(actor, decision, action, occurred_at, context)

    def _deny(
        self,
        actor: User,
        decision: AuthorizationDecision,
        action: str,
        occurred_at: datetime,
        context: dict[str, object] | None = None,
    ) -> None:
        self.audit.record(
            actor=actor,
            action=action,
            reason=decision.explanation,
            occurred_at=occurred_at,
            decision=decision,
            context=context,
        )
        self.session.flush()
        raise RoleManagementError(decision)

    @staticmethod
    def _assignment_snapshot(assignment: RoleAssignment) -> dict[str, object]:
        return {
            "assignment_id": assignment.id,
            "user_id": assignment.user_id,
            "role_id": assignment.role_id,
            "client_id": assignment.client_id,
            "all_clients": assignment.all_clients,
            "branch_id": assignment.branch_id,
            "all_branches": assignment.all_branches,
            "direction": assignment.direction.value if assignment.direction else None,
            "all_directions": assignment.all_directions,
            "mode": assignment.mode.value if assignment.mode else None,
            "all_modes": assignment.all_modes,
            "valid_from": assignment.valid_from.isoformat(),
            "valid_until": (assignment.valid_until.isoformat() if assignment.valid_until else None),
            "revoked_at": (assignment.revoked_at.isoformat() if assignment.revoked_at else None),
            "version": assignment.version,
        }

    @staticmethod
    def _require_aware(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise RoleManagementValidationError(f"{field_name} must include a UTC offset.")
