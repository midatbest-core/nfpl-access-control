"""Add employee accounts, password credentials, and account history.

Revision ID: 20261017_0005
Revises: 20261017_0004
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_0005"
down_revision: str | None = "20261017_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text("SELECT lower(email) FROM users GROUP BY lower(email) HAVING count(*) > 1 LIMIT 1")
    ).first()
    if duplicate is not None:
        raise RuntimeError("Cannot normalize employee emails: case-insensitive duplicates exist.")
    connection.execute(sa.text("UPDATE users SET email = lower(email) WHERE email <> lower(email)"))

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "account_status",
                sa.String(length=16),
                nullable=False,
                server_default="active",
            )
        )
        batch.create_check_constraint(
            op.f("ck_users_account_status"),
            "account_status IN ('pending', 'active', 'disabled')",
        )
        batch.create_check_constraint(
            op.f("ck_users_normalized_email"),
            "email = lower(email)",
        )
        batch.create_index(
            "ix_users_kind_status_name",
            ["kind", "account_status", "display_name", "id"],
            unique=False,
        )

    op.create_table(
        "password_credentials",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_password_credentials")),
    )

    op.create_table(
        "account_state_events",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "previous_status IN ('pending', 'active', 'disabled')",
            name=op.f("ck_account_state_events_previous_account_status"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'disabled')",
            name=op.f("ck_account_state_events_account_state_event_status"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_account_state_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_account_state_events_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_state_events")),
    )
    op.create_index(
        "ix_account_state_events_user_time",
        "account_state_events",
        ["user_id", "effective_at", "id"],
    )

    op.create_table(
        "admin_bootstraps",
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_admin_bootstraps_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_admin_bootstraps")),
        sa.UniqueConstraint("user_id", name=op.f("uq_admin_bootstraps_user_id")),
    )


def downgrade() -> None:
    op.drop_table("admin_bootstraps")
    op.drop_index("ix_account_state_events_user_time", table_name="account_state_events")
    op.drop_table("account_state_events")
    op.drop_table("password_credentials")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_kind_status_name")
        batch.drop_constraint(op.f("ck_users_normalized_email"), type_="check")
        batch.drop_constraint(op.f("ck_users_account_status"), type_="check")
        batch.drop_column("account_status")
