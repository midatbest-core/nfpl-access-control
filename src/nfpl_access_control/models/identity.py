"""Authenticated identities and revocable API credentials."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import TimestampMixin, UtcDateTime, UuidPrimaryKeyMixin
from nfpl_access_control.models.enums import EmployeeAvailability, UserKind


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

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
    assigned_jobs = relationship("Job", back_populates="assignee", foreign_keys="Job.assignee_id")
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
