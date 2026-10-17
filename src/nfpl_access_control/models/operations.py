"""Absence-management and in-app notification persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import UtcDateTime, UuidPrimaryKeyMixin, utc_now
from nfpl_access_control.models.enums import (
    AbsenceJobOutcome,
    AbsenceNominationStatus,
    ResponsibilityType,
)


def enum_column(enum_type: type, name: str, length: int) -> Enum:
    return Enum(
        enum_type,
        native_enum=False,
        create_constraint=True,
        name=name,
        length=length,
        values_callable=lambda values: [value.value for value in values],
    )


class AbsenceNomination(UuidPrimaryKeyMixin, Base):
    __tablename__ = "absence_nominations"
    __table_args__ = (
        Index("ix_absence_nominations_status_time", "status", "requested_at", "id"),
        Index(
            "ix_absence_nominations_employee_interval",
            "requester_user_id",
            "valid_from",
            "valid_until",
            "status",
        ),
    )

    requester_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    nominee_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AbsenceNominationStatus] = mapped_column(
        enum_column(AbsenceNominationStatus, "absence_nomination_status", 16), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    decided_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    outcomes = relationship("AbsenceNominationJob", back_populates="nomination")
    __mapper_args__ = {"version_id_col": version}


class AbsenceNominationJob(UuidPrimaryKeyMixin, Base):
    __tablename__ = "absence_nomination_jobs"
    __table_args__ = (
        UniqueConstraint(
            "nomination_id", "job_id", "responsibility", name="one_absence_job_outcome"
        ),
        Index("ix_absence_nomination_jobs_outcome", "outcome", "job_id", "id"),
    )

    nomination_id: Mapped[str] = mapped_column(
        ForeignKey("absence_nominations.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    responsibility: Mapped[ResponsibilityType] = mapped_column(
        enum_column(ResponsibilityType, "absence_responsibility_type", 24), nullable=False
    )
    nominee_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    outcome: Mapped[AbsenceJobOutcome] = mapped_column(
        enum_column(AbsenceJobOutcome, "absence_job_outcome", 16), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    delegation_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_delegations.id", ondelete="RESTRICT"), nullable=True
    )

    nomination = relationship("AbsenceNomination", back_populates="outcomes")


class Notification(UuidPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="notification_dedupe_key"),
        Index(
            "ix_notifications_recipient_unread_time",
            "recipient_user_id",
            "read_at",
            "created_at",
            "id",
        ),
        Index("ix_notifications_job_recipient", "job_id", "recipient_user_id", "created_at"),
    )

    recipient_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=True
    )
    job_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    target_path: Mapped[str] = mapped_column(String(300), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    is_client_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
