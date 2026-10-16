"""Predefined roles and the safe permission vocabulary for custom roles."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.models import Permission, Role, RolePermission

MAKER_ROLE = "maker"
CHECKER_ROLE = "checker"
FILING_OFFICER_ROLE = "filing-officer"
ADMIN_ROLE = "admin"
CLIENT_VIEWER_ROLE = "client-viewer"
PARSER_SERVICE_ROLE = "parser-service"


@dataclass(frozen=True, slots=True)
class SystemRoleDefinition:
    id: str
    slug: str
    name: str
    description: str
    permissions: frozenset[Permission]


SYSTEM_ROLES = (
    SystemRoleDefinition(
        id="00000000-0000-4000-8000-000000000101",
        slug=MAKER_ROLE,
        name="Maker",
        description="Prepares shipment jobs within an assigned scope.",
        permissions=frozenset({Permission.JOB_VIEW, Permission.JOB_PREPARE}),
    ),
    SystemRoleDefinition(
        id="00000000-0000-4000-8000-000000000102",
        slug=CHECKER_ROLE,
        name="Checker",
        description="Checks prepared shipment jobs within an assigned scope.",
        permissions=frozenset({Permission.JOB_VIEW, Permission.JOB_CHECK}),
    ),
    SystemRoleDefinition(
        id="00000000-0000-4000-8000-000000000103",
        slug=FILING_OFFICER_ROLE,
        name="Filing Officer",
        description="Files checked shipment jobs within an assigned scope.",
        permissions=frozenset({Permission.JOB_VIEW, Permission.JOB_FILE}),
    ),
    SystemRoleDefinition(
        id="00000000-0000-4000-8000-000000000104",
        slug=ADMIN_ROLE,
        name="Admin",
        description="Unified operational and access-management administrator.",
        permissions=frozenset(Permission),
    ),
    SystemRoleDefinition(
        id="00000000-0000-4000-8000-000000000105",
        slug=CLIENT_VIEWER_ROLE,
        name="Client Viewer",
        description="Views sanitized client shipment information.",
        permissions=frozenset({Permission.JOB_VIEW, Permission.CLIENT_HISTORY_VIEW}),
    ),
    SystemRoleDefinition(
        id="00000000-0000-4000-8000-000000000106",
        slug=PARSER_SERVICE_ROLE,
        name="Parser Service",
        description="Creates and updates permitted job fields for automated parsing.",
        permissions=frozenset({Permission.JOB_VIEW, Permission.JOB_CREATE, Permission.JOB_UPDATE}),
    ),
)

SYSTEM_ROLE_BY_SLUG = {definition.slug: definition for definition in SYSTEM_ROLES}

# Security-sensitive access management stays exclusive to the built-in Admin.
CONFIGURABLE_ROLE_PERMISSIONS = frozenset(
    permission
    for permission in Permission
    if permission
    not in {
        Permission.ACCESS_GRANT,
        Permission.ACCESS_REVOKE,
        Permission.ROLE_MANAGE,
    }
)

JOB_PERMISSIONS = frozenset(
    {
        Permission.JOB_VIEW,
        Permission.JOB_CREATE,
        Permission.JOB_UPDATE,
        Permission.JOB_PREPARE,
        Permission.JOB_CHECK,
        Permission.JOB_FILE,
        Permission.JOB_CANCEL,
        Permission.JOB_REOPEN,
    }
)


def install_system_roles(session: Session) -> None:
    """Idempotently install roles for tests/bootstrap and verify collisions."""

    for definition in SYSTEM_ROLES:
        role = session.scalar(select(Role).where(Role.slug == definition.slug))
        if role is None:
            role = Role(
                id=definition.id,
                slug=definition.slug,
                name=definition.name,
                description=definition.description,
                is_system=True,
            )
            role.permissions = [
                RolePermission(permission=permission)
                for permission in sorted(definition.permissions, key=str)
            ]
            session.add(role)
            continue
        if not role.is_system or role.id != definition.id:
            raise RuntimeError(f"system role collision for {definition.slug}")
