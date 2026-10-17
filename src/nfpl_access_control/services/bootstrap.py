"""Trusted, one-time first-Admin bootstrap operation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization.roles import ADMIN_ROLE
from nfpl_access_control.core.security import hash_password
from nfpl_access_control.models import (
    AccountStateEvent,
    AccountStatus,
    AdminBootstrap,
    AssignmentEventType,
    Branch,
    PasswordCredential,
    Role,
    RoleAssignment,
    RoleAssignmentEvent,
    User,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService
from nfpl_access_control.services.authentication import (
    EMAIL_PATTERN,
    AuthenticationError,
    normalize_email,
    validate_password_strength,
)

BOOTSTRAP_KEY = "first_admin"


class BootstrapError(RuntimeError):
    pass


def bootstrap_first_admin(
    session: Session,
    *,
    display_name: str,
    email: str,
    password: str,
    branch_code: str,
    branch_name: str,
    now: datetime | None = None,
) -> User:
    current_time = now or datetime.now(UTC)
    try:
        validate_password_strength(password)
    except AuthenticationError as error:
        raise BootstrapError(str(error)) from error
    if session.get(AdminBootstrap, BOOTSTRAP_KEY) is not None:
        raise BootstrapError("The first-Admin bootstrap has already been used.")
    admin_role = session.scalar(select(Role).where(Role.slug == ADMIN_ROLE))
    if admin_role is None:
        raise BootstrapError("System roles are not installed; run migrations first.")
    if session.scalar(
        select(RoleAssignment.id).join(RoleAssignment.role).where(Role.slug == ADMIN_ROLE)
    ):
        raise BootstrapError("An Admin assignment already exists; bootstrap is unavailable.")
    normalized_email = normalize_email(email)
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise BootstrapError("A valid email address is required.")
    if session.scalar(select(User.id).where(User.email == normalized_email)):
        raise BootstrapError("The bootstrap email is already registered.")
    if not display_name.strip() or not branch_code.strip() or not branch_name.strip():
        raise BootstrapError("Name, branch code, and branch name are required.")

    branch = session.scalar(select(Branch).where(Branch.code == branch_code.strip().upper()))
    if branch is None:
        branch = Branch(code=branch_code.strip().upper(), name=branch_name.strip())
        session.add(branch)
        session.flush()
    elif branch.name != branch_name.strip():
        raise BootstrapError("The existing branch code has a different name.")

    user = User(
        email=normalized_email,
        display_name=display_name.strip(),
        kind=UserKind.STAFF,
        branch_id=branch.id,
        account_status=AccountStatus.ACTIVE,
        is_active=True,
    )
    user.password_credential = PasswordCredential(password_hash=hash_password(password))
    session.add(user)
    session.flush()
    assignment = RoleAssignment(
        user_id=user.id,
        role_id=admin_role.id,
        client_id=None,
        all_clients=True,
        branch_id=None,
        all_branches=True,
        direction=None,
        all_directions=True,
        mode=None,
        all_modes=True,
        valid_from=current_time,
        valid_until=None,
        granted_by_user_id=user.id,
        grant_reason="Trusted one-time first-Admin bootstrap.",
    )
    assignment.events.append(
        RoleAssignmentEvent(
            event_type=AssignmentEventType.GRANTED,
            actor_user_id=user.id,
            occurred_at=current_time,
            reason="Trusted one-time first-Admin bootstrap.",
        )
    )
    session.add_all(
        [
            assignment,
            AccountStateEvent(
                user_id=user.id,
                previous_status=None,
                status=AccountStatus.ACTIVE,
                effective_at=current_time,
                actor_user_id=user.id,
                reason="Trusted one-time first-Admin bootstrap.",
            ),
            AdminBootstrap(key=BOOTSTRAP_KEY, user_id=user.id, occurred_at=current_time),
        ]
    )
    session.flush()
    AuditService(session).record(
        actor=user,
        action="admin.bootstrap",
        reason="Trusted one-time first-Admin bootstrap.",
        occurred_at=current_time,
        context={"employee_id": user.id, "role_assignment_id": assignment.id},
    )
    session.flush()
    return user
