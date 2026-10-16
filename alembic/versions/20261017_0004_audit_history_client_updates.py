"""Add immutable job versions and historical policy evidence.

Revision ID: 20261017_0004
Revises: 20261017_0003
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0004"
down_revision: str | None = "20261017_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("affected_job_version", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("denied", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "job_versions",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_job_versions_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_versions_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_versions")),
        sa.UniqueConstraint("job_id", "version_number", name="one_job_version"),
    )
    op.create_index(
        "ix_job_versions_job_time",
        "job_versions",
        ["job_id", "recorded_at", "version_number"],
    )

    op.create_table(
        "user_availability_events",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("previous_availability", sa.String(length=16), nullable=False),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "previous_availability IN ('available', 'busy', 'absent')",
            name=op.f("ck_user_availability_events_previous_employee_availability"),
        ),
        sa.CheckConstraint(
            "availability IN ('available', 'busy', 'absent')",
            name=op.f("ck_user_availability_events_availability_event_value"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_user_availability_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_availability_events_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_availability_events")),
    )
    op.create_index(
        "ix_user_availability_events_user_time",
        "user_availability_events",
        ["user_id", "effective_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_availability_events_user_time",
        table_name="user_availability_events",
    )
    op.drop_table("user_availability_events")
    op.drop_index("ix_job_versions_job_time", table_name="job_versions")
    op.drop_table("job_versions")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_column("denied")
        batch.drop_column("affected_job_version")
