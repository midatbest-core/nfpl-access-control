"""Add absence nominations, notifications, queue indexes, and job archival.

Revision ID: 20261017_0007
Revises: 20261017_0006
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0007"
down_revision: str | None = "20261017_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "absence_nominations",
        sa.Column("requester_user_id", sa.String(length=36), nullable=False),
        sa.Column("nominee_user_id", sa.String(length=36), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked')",
            name=op.f("ck_absence_nominations_absence_nomination_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_absence_nominations_decided_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["nominee_user_id"],
            ["users.id"],
            name=op.f("fk_absence_nominations_nominee_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"],
            ["users.id"],
            name=op.f("fk_absence_nominations_requester_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_absence_nominations")),
    )
    op.create_index(
        "ix_absence_nominations_status_time",
        "absence_nominations",
        ["status", "requested_at", "id"],
    )
    op.create_index(
        "ix_absence_nominations_employee_interval",
        "absence_nominations",
        ["requester_user_id", "valid_from", "valid_until", "status"],
    )

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("archived_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("archive_reason", sa.Text(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_jobs_archived_by_user_id_users"),
            "users",
            ["archived_by_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_jobs_archive_stage_updated", ["archived_at", "stage", "updated_at", "id"]
        )

    with op.batch_alter_table("job_delegations") as batch:
        batch.add_column(sa.Column("absence_nomination_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            op.f("fk_job_delegations_absence_nomination_id_absence_nominations"),
            "absence_nominations",
            ["absence_nomination_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            op.f("ix_job_delegations_absence_nomination_id"), ["absence_nomination_id"]
        )

    op.create_table(
        "absence_nomination_jobs",
        sa.Column("nomination_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("responsibility", sa.String(length=24), nullable=False),
        sa.Column("nominee_user_id", sa.String(length=36), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("delegation_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "responsibility IN ('maker', 'checker', 'filing_officer')",
            name=op.f("ck_absence_nomination_jobs_absence_responsibility_type"),
        ),
        sa.CheckConstraint(
            "outcome IN ('delegated', 'ineligible', 'conflict', 'overridden')",
            name=op.f("ck_absence_nomination_jobs_absence_job_outcome"),
        ),
        sa.ForeignKeyConstraint(
            ["delegation_id"],
            ["job_delegations.id"],
            name=op.f("fk_absence_nomination_jobs_delegation_id_job_delegations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_absence_nomination_jobs_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["nomination_id"],
            ["absence_nominations.id"],
            name=op.f("fk_absence_nomination_jobs_nomination_id_absence_nominations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["nominee_user_id"],
            ["users.id"],
            name=op.f("fk_absence_nomination_jobs_nominee_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_absence_nomination_jobs")),
        sa.UniqueConstraint(
            "nomination_id", "job_id", "responsibility", name="one_absence_job_outcome"
        ),
    )
    op.create_index(
        "ix_absence_nomination_jobs_outcome",
        "absence_nomination_jobs",
        ["outcome", "job_id", "id"],
    )

    op.create_table(
        "notifications",
        sa.Column("recipient_user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("job_reference", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("target_path", sa.String(length=300), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_client_safe", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_notifications_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            name=op.f("fk_notifications_recipient_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("dedupe_key", name="notification_dedupe_key"),
    )
    op.create_index(
        "ix_notifications_recipient_unread_time",
        "notifications",
        ["recipient_user_id", "read_at", "created_at", "id"],
    )
    op.create_index(
        "ix_notifications_job_recipient",
        "notifications",
        ["job_id", "recipient_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_job_recipient", table_name="notifications")
    op.drop_index("ix_notifications_recipient_unread_time", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_absence_nomination_jobs_outcome", table_name="absence_nomination_jobs")
    op.drop_table("absence_nomination_jobs")
    with op.batch_alter_table("job_delegations") as batch:
        batch.drop_index(op.f("ix_job_delegations_absence_nomination_id"))
        batch.drop_constraint(
            op.f("fk_job_delegations_absence_nomination_id_absence_nominations"),
            type_="foreignkey",
        )
        batch.drop_column("absence_nomination_id")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index("ix_jobs_archive_stage_updated")
        batch.drop_constraint(op.f("fk_jobs_archived_by_user_id_users"), type_="foreignkey")
        batch.drop_column("archive_reason")
        batch.drop_column("archived_by_user_id")
        batch.drop_column("archived_at")
    op.drop_index("ix_absence_nominations_employee_interval", table_name="absence_nominations")
    op.drop_index("ix_absence_nominations_status_time", table_name="absence_nominations")
    op.drop_table("absence_nominations")
