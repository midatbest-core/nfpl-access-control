"""Create Phase 1 identity, organization, and job tables.

Revision ID: 20261017_0001
Revises: None
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
    )
    op.create_index(op.f("ix_branches_code"), "branches", ["code"], unique=True)

    op.create_table(
        "clients",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    op.create_index(op.f("ix_clients_code"), "clients", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('staff', 'client', 'service')", name=op.f("ck_users_user_kind")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "api_credentials",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_api_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_credentials")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_credentials_token_hash")),
    )
    op.create_index(
        "ix_api_credentials_active_lookup",
        "api_credentials",
        ["token_hash", "revoked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_api_credentials_user_id"), "api_credentials", ["user_id"], unique=False
    )

    op.create_table(
        "jobs",
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("assignee_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction IN ('import', 'export')", name=op.f("ck_jobs_job_direction")),
        sa.CheckConstraint("mode IN ('air', 'fcl', 'lcl')", name=op.f("ck_jobs_job_mode")),
        sa.CheckConstraint(
            "stage IN ('confirmed', 'prepared', 'checked', 'filed', 'cancelled', 'reopened')",
            name=op.f("ck_jobs_job_stage"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_jobs_version_positive")),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_jobs_assignee_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_jobs_branch_id_branches"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_jobs_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_assignee_id"), "jobs", ["assignee_id"], unique=False)
    op.create_index(
        "ix_jobs_assignee_stage_id", "jobs", ["assignee_id", "stage", "id"], unique=False
    )
    op.create_index(op.f("ix_jobs_reference"), "jobs", ["reference"], unique=True)
    op.create_index(
        "ix_jobs_scope_stage_id",
        "jobs",
        ["client_id", "branch_id", "stage", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_scope_stage_id", table_name="jobs")
    op.drop_index(op.f("ix_jobs_reference"), table_name="jobs")
    op.drop_index("ix_jobs_assignee_stage_id", table_name="jobs")
    op.drop_index(op.f("ix_jobs_assignee_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_api_credentials_user_id"), table_name="api_credentials")
    op.drop_index("ix_api_credentials_active_lookup", table_name="api_credentials")
    op.drop_table("api_credentials")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_clients_code"), table_name="clients")
    op.drop_table("clients")
    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.drop_table("branches")
