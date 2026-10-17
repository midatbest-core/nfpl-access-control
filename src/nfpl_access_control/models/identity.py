"""Authenticated identities and revocable API credentials."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import TimestampMixin, UtcDateTime, UuidPrimaryKeyMixin
from nfpl_access_control.models.enums import AccountStatus, EmployeeAvailability, UserKind


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="normalized_email"),
        Index("ix_users_kind_status_name", "kind", "account_status", "display_name", "id"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[UserKind] = mapped_column(
        Enum(
            UserKind,
            native_enum=False,
            create_constraint=True,
            name="user_kind",
            length=20,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            native_enum=False,
            create_constraint=True,
            name="account_status",
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )
    branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    availability: Mapped[EmployeeAvailability] = mapped_column(
        Enum(
            EmployeeAvailability,
            native_enum=False,
            create_constraint=True,
            name="employee_availability",
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=EmployeeAvailability.AVAILABLE,
    )

    credentials = relationship("ApiCredential", back_populates="user", cascade="all, delete-orphan")
    password_credential = relationship(
        "PasswordCredential",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    assigned_jobs = relationship("Job", back_populates="assignee", foreign_keys="Job.assignee_id")
    role_assignments = relationship(
        "RoleAssignment",
        foreign_keys="RoleAssignment.user_id",
        viewonly=True,
    )
    branch = relationship("Branch")


class ApiCredential(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_credentials"
    __table_args__ = (Index("ix_api_credentials_active_lookup", "token_hash", "revoked_at"),)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)

    user = relationship("User", back_populates="credentials")


class PasswordCredential(TimestampMixin, Base):
    __tablename__ = "password_credentials"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)

    user = relationship("User", back_populates="password_credential")


class AccountStateEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_state_events"
    __table_args__ = (Index("ix_account_state_events_user_time", "user_id", "effective_at", "id"),)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[AccountStatus | None] = mapped_column(
        Enum(
            AccountStatus,
            native_enum=False,
            create_constraint=True,
            name="previous_account_status",
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=True,
    )
    status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            native_enum=False,
            create_constraint=True,
            name="account_state_event_status",
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    effective_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class AdminBootstrap(Base):
    __tablename__ = "admin_bootstraps"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)


@event.listens_for(AccountStateEvent, "before_update")
@event.listens_for(AccountStateEvent, "before_delete")
@event.listens_for(AdminBootstrap, "before_update")
@event.listens_for(AdminBootstrap, "before_delete")
def _prevent_identity_history_mutation(*_args: object) -> None:
    raise RuntimeError("Identity history records are append-only.")
