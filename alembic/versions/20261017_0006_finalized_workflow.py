"""Add finalized workflow locks, correction routing, and edit requests.

Revision ID: 20261017_0006
Revises: 20261017_0005
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0006"
down_revision: str | None = "20261017_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(
            sa.Column("maker_edit_locked", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column(
                "maker_correction_required", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch.add_column(
            sa.Column(
                "checker_correction_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("last_return_category", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("last_return_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("last_maker_justification", sa.Text(), nullable=True))
        batch.add_column(sa.Column("last_checker_justification", sa.Text(), nullable=True))
        batch.create_check_constraint(
            "filing_return_category",
            "last_return_category IN ('maker_fault', 'checker_fault', 'both')",
        )

    op.create_table(
        "job_edit_requests",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied', 'consumed')",
            name=op.f("ck_job_edit_requests_edit_request_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_job_edit_requests_decided_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_edit_requests_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_job_edit_requests_requested_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_edit_requests")),
    )
    op.create_index(
        "ix_job_edit_requests_job_status",
        "job_edit_requests",
        ["job_id", "status", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_edit_requests_job_status", table_name="job_edit_requests")
    op.drop_table("job_edit_requests")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint(op.f("ck_jobs_filing_return_category"), type_="check")
        batch.drop_column("last_checker_justification")
        batch.drop_column("last_maker_justification")
        batch.drop_column("last_return_reason")
        batch.drop_column("last_return_category")
        batch.drop_column("checker_correction_required")
        batch.drop_column("maker_correction_required")
        batch.drop_column("maker_edit_locked")
