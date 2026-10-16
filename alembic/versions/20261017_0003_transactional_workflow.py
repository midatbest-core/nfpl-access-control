"""Add transactional workflow, responsibilities, delegation, and audit.

Revision ID: 20261017_0003
Revises: 20261017_0002
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0003"
down_revision: str | None = "20261017_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("branch_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column(
                "availability",
                sa.String(length=16),
                nullable=False,
                server_default="available",
            )
        )
        batch.create_check_constraint(
            "employee_availability",
            "availability IN ('available', 'busy', 'absent')",
        )
        batch.create_foreign_key(
            op.f("fk_users_branch_id_branches"),
            "branches",
            ["branch_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(op.f("ix_users_branch_id"), ["branch_id"])

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(
            sa.Column("goods_description", sa.Text(), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("container_reference", sa.String(length=100), nullable=True))
        batch.add_column(
            sa.Column("checklist_data", sa.JSON(), nullable=False, server_default="{}")
        )
        batch.add_column(
            sa.Column("checklist_revision", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("prepared_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("checked_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("filed_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True))
        for column in ("prepared_by_user_id", "checked_by_user_id", "filed_by_user_id"):
            batch.create_foreign_key(
                op.f(f"fk_jobs_{column}_users"),
                "users",
                [column],
                ["id"],
                ondelete="RESTRICT",
            )

    op.create_table(
        "job_responsibilities",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("responsibility", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "responsibility IN ('maker', 'checker', 'filing_officer')",
            name=op.f("ck_job_responsibilities_responsibility_type"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name=op.f("fk_job_responsibilities_assigned_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_responsibilities_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_job_responsibilities_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_responsibilities")),
        sa.UniqueConstraint(
            "job_id",
            "responsibility",
            name="one_job_responsibility",
        ),
    )
    op.create_index(
        "ix_job_responsibilities_user_type",
        "job_responsibilities",
        ["user_id", "responsibility", "job_id"],
    )

    op.create_table(
        "job_responsibility_events",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("responsibility", sa.String(length=24), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("previous_user_id", sa.String(length=36), nullable=True),
        sa.Column("new_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "responsibility IN ('maker', 'checker', 'filing_officer')",
            name=op.f("ck_job_responsibility_events_responsibility_event_role"),
        ),
        sa.CheckConstraint(
            "event_type IN "
            "('assigned', 'reassigned', 'unassigned', 'delegated', 'delegation_revoked')",
            name=op.f("ck_job_responsibility_events_responsibility_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_job_responsibility_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_responsibility_events_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["new_user_id"],
            ["users.id"],
            name=op.f("fk_job_responsibility_events_new_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_user_id"],
            ["users.id"],
            name=op.f("fk_job_responsibility_events_previous_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_responsibility_events")),
    )
    op.create_index(
        "ix_job_responsibility_events_job_time",
        "job_responsibility_events",
        ["job_id", "occurred_at", "id"],
    )

    op.create_table(
        "job_delegations",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("responsibility", sa.String(length=24), nullable=False),
        sa.Column("delegator_user_id", sa.String(length=36), nullable=False),
        sa.Column("delegate_user_id", sa.String(length=36), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "responsibility IN ('maker', 'checker', 'filing_officer')",
            name=op.f("ck_job_delegations_delegation_responsibility_type"),
        ),
        sa.CheckConstraint(
            "valid_until > valid_from",
            name=op.f("ck_job_delegations_valid_delegation_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_job_delegations_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["delegate_user_id"],
            ["users.id"],
            name=op.f("fk_job_delegations_delegate_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["delegator_user_id"],
            ["users.id"],
            name=op.f("fk_job_delegations_delegator_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_delegations_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_delegations")),
    )
    op.create_index(
        "ix_job_delegations_effective",
        "job_delegations",
        [
            "job_id",
            "responsibility",
            "delegate_user_id",
            "valid_from",
            "valid_until",
            "revoked_at",
        ],
    )

    op.create_table(
        "exceptional_transition_requests",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "action IN ('cancel', 'reopen')",
            name=op.f("ck_exceptional_transition_requests_exceptional_action"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied', 'executed')",
            name=op.f("ck_exceptional_transition_requests_exceptional_request_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_exceptional_transition_requests_decided_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_exceptional_transition_requests_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_exceptional_transition_requests_requested_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exceptional_transition_requests")),
    )
    op.create_index(
        "ix_exception_requests_job_status",
        "exceptional_transition_requests",
        ["job_id", "status", "requested_at"],
    )

    op.create_table(
        "audit_events",
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("authorization_context", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_audit_events_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_actor_time",
        "audit_events",
        ["actor_user_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_audit_events_job_time",
        "audit_events",
        ["job_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_job_time", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_time", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(
        "ix_exception_requests_job_status",
        table_name="exceptional_transition_requests",
    )
    op.drop_table("exceptional_transition_requests")
    op.drop_index("ix_job_delegations_effective", table_name="job_delegations")
    op.drop_table("job_delegations")
    op.drop_index(
        "ix_job_responsibility_events_job_time",
        table_name="job_responsibility_events",
    )
    op.drop_table("job_responsibility_events")
    op.drop_index(
        "ix_job_responsibilities_user_type",
        table_name="job_responsibilities",
    )
    op.drop_table("job_responsibilities")

    with op.batch_alter_table("jobs") as batch:
        for column in ("filed_by_user_id", "checked_by_user_id", "prepared_by_user_id"):
            batch.drop_constraint(op.f(f"fk_jobs_{column}_users"), type_="foreignkey")
        for column in (
            "filed_at",
            "filed_by_user_id",
            "checked_at",
            "checked_by_user_id",
            "prepared_at",
            "prepared_by_user_id",
            "checklist_revision",
            "checklist_data",
            "container_reference",
            "goods_description",
        ):
            batch.drop_column(column)

    with op.batch_alter_table("users") as batch:
        batch.drop_index(op.f("ix_users_branch_id"))
        batch.drop_constraint(op.f("fk_users_branch_id_branches"), type_="foreignkey")
        batch.drop_constraint(op.f("ck_users_employee_availability"), type_="check")
        batch.drop_column("availability")
        batch.drop_column("branch_id")
