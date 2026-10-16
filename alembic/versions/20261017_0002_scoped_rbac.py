"""Add scoped RBAC, effective grants, and assignment history.

Revision ID: 20261017_0002
Revises: 20261017_0001
Create Date: 2026-10-17
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0002"
down_revision: str | None = "20261017_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_ROLES = (
    (
        "00000000-0000-4000-8000-000000000101",
        "maker",
        "Maker",
        "Prepares shipment jobs within an assigned scope.",
        ("job:view", "job:prepare"),
    ),
    (
        "00000000-0000-4000-8000-000000000102",
        "checker",
        "Checker",
        "Checks prepared shipment jobs within an assigned scope.",
        ("job:view", "job:check"),
    ),
    (
        "00000000-0000-4000-8000-000000000103",
        "filing-officer",
        "Filing Officer",
        "Files checked shipment jobs within an assigned scope.",
        ("job:view", "job:file"),
    ),
    (
        "00000000-0000-4000-8000-000000000104",
        "admin",
        "Admin",
        "Unified operational and access-management administrator.",
        (
            "job:view",
            "job:create",
            "job:update",
            "job:prepare",
            "job:check",
            "job:file",
            "job:cancel",
            "job:reopen",
            "client_history:view",
            "access:grant",
            "access:revoke",
            "role:manage",
        ),
    ),
    (
        "00000000-0000-4000-8000-000000000105",
        "client-viewer",
        "Client Viewer",
        "Views sanitized client shipment information.",
        ("job:view", "client_history:view"),
    ),
    (
        "00000000-0000-4000-8000-000000000106",
        "parser-service",
        "Parser Service",
        "Creates and updates permitted job fields for automated parsing.",
        ("job:view", "job:create", "job:update"),
    ),
)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_index(op.f("ix_roles_slug"), "roles", ["slug"], unique=True)

    op.create_table(
        "role_assignments",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=True),
        sa.Column("all_clients", sa.Boolean(), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=True),
        sa.Column("all_branches", sa.Boolean(), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("all_directions", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=True),
        sa.Column("all_modes", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("revoked_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("grant_reason", sa.Text(), nullable=False),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IS NULL OR direction IN ('import', 'export')",
            name=op.f("ck_role_assignments_assignment_direction"),
        ),
        sa.CheckConstraint(
            "mode IS NULL OR mode IN ('air', 'fcl', 'lcl')",
            name=op.f("ck_role_assignments_assignment_mode"),
        ),
        sa.CheckConstraint(
            "(all_branches AND branch_id IS NULL) OR (NOT all_branches AND branch_id IS NOT NULL)",
            name=op.f("ck_role_assignments_explicit_branch_scope"),
        ),
        sa.CheckConstraint(
            "(all_clients AND client_id IS NULL) OR (NOT all_clients AND client_id IS NOT NULL)",
            name=op.f("ck_role_assignments_explicit_client_scope"),
        ),
        sa.CheckConstraint(
            "(all_directions AND direction IS NULL) OR "
            "(NOT all_directions AND direction IS NOT NULL)",
            name=op.f("ck_role_assignments_explicit_direction_scope"),
        ),
        sa.CheckConstraint(
            "(all_modes AND mode IS NULL) OR (NOT all_modes AND mode IS NOT NULL)",
            name=op.f("ck_role_assignments_explicit_mode_scope"),
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name=op.f("ck_role_assignments_valid_effective_interval"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_role_assignments_version_positive")),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_role_assignments_branch_id_branches"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_role_assignments_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_role_assignments_granted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_role_assignments_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_assignments_role_id_roles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_role_assignments_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_assignments")),
    )
    op.create_index(
        op.f("ix_role_assignments_role_id"),
        "role_assignments",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        "ix_role_assignments_scope",
        "role_assignments",
        ["client_id", "branch_id", "direction", "mode"],
        unique=False,
    )
    op.create_index(
        "ix_role_assignments_user_effective",
        "role_assignments",
        ["user_id", "valid_from", "valid_until", "revoked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_assignments_user_id"),
        "role_assignments",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "permission IN ('job:view', 'job:create', 'job:update', 'job:prepare', "
            "'job:check', 'job:file', 'job:cancel', 'job:reopen', "
            "'client_history:view', 'access:grant', 'access:revoke', 'role:manage')",
            name=op.f("ck_role_permissions_permission"),
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission", name=op.f("pk_role_permissions")),
    )

    op.create_table(
        "role_assignment_events",
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('granted', 'revoked')",
            name=op.f("ck_role_assignment_events_assignment_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_role_assignment_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["role_assignments.id"],
            name=op.f("fk_role_assignment_events_assignment_id_role_assignments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_assignment_events")),
    )
    op.create_index(
        "ix_role_assignment_events_assignment_time",
        "role_assignment_events",
        ["assignment_id", "occurred_at", "id"],
        unique=False,
    )

    roles_table = sa.table(
        "roles",
        sa.column("id", sa.String),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.String),
        sa.column("permission", sa.String),
    )
    seeded_at = datetime(2026, 10, 17, tzinfo=UTC)
    op.bulk_insert(
        roles_table,
        [
            {
                "id": role_id,
                "slug": slug,
                "name": name,
                "description": description,
                "is_system": True,
                "created_at": seeded_at,
                "updated_at": seeded_at,
            }
            for role_id, slug, name, description, _ in SYSTEM_ROLES
        ],
    )
    op.bulk_insert(
        permissions_table,
        [
            {"role_id": role_id, "permission": permission}
            for role_id, _, _, _, permissions in SYSTEM_ROLES
            for permission in permissions
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_role_assignment_events_assignment_time",
        table_name="role_assignment_events",
    )
    op.drop_table("role_assignment_events")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_role_assignments_user_id"), table_name="role_assignments")
    op.drop_index("ix_role_assignments_user_effective", table_name="role_assignments")
    op.drop_index("ix_role_assignments_scope", table_name="role_assignments")
    op.drop_index(op.f("ix_role_assignments_role_id"), table_name="role_assignments")
    op.drop_table("role_assignments")
    op.drop_index(op.f("ix_roles_slug"), table_name="roles")
    op.drop_table("roles")
