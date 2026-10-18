"""Workflow responsibility, delegation, exception, and audit persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import UtcDateTime, UuidPrimaryKeyMixin, utc_now
from nfpl_access_control.models.enums import (
    EditRequestStatus,
    EmployeeAvailability,
    ExceptionalAction,
    ExceptionalRequestStatus,
    ResponsibilityEventType,
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


class JobResponsibility(UuidPrimaryKeyMixin, Base):
    __tablename__ = "job_responsibilities"
    __table_args__ = (
        UniqueConstraint("job_id", "responsibility", name="one_job_responsibility"),
        Index("ix_job_responsibilities_user_type", "user_id", "responsibility", "job_id"),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    responsibility: Mapped[ResponsibilityType] = mapped_column(
        enum_column(ResponsibilityType, "responsibility_type", 24), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    assigned_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    job = relationship("Job", back_populates="responsibilities")
    user = relationship("User", foreign_keys=[user_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])

    __mapper_args__ = {"version_id_col": version}


class JobResponsibilityEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "job_responsibility_events"
    __table_args__ = (
        Index("ix_job_responsibility_events_job_time", "job_id", "occurred_at", "id"),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    responsibility: Mapped[ResponsibilityType] = mapped_column(
        enum_column(ResponsibilityType, "responsibility_event_role", 24), nullable=False
    )
    event_type: Mapped[ResponsibilityEventType] = mapped_column(
        enum_column(ResponsibilityEventType, "responsibility_event_type", 24), nullable=False
    )
    previous_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    new_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class JobDelegation(UuidPrimaryKeyMixin, Base):
    __tablename__ = "job_delegations"
    __table_args__ = (
        CheckConstraint("valid_until > valid_from", name="valid_delegation_interval"),
        Index(
            "ix_job_delegations_effective",
            "job_id",
            "responsibility",
            "delegate_user_id",
            "valid_from",
            "valid_until",
            "revoked_at",
        ),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    responsibility: Mapped[ResponsibilityType] = mapped_column(
        enum_column(ResponsibilityType, "delegation_responsibility_type", 24), nullable=False
    )
    delegator_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    delegate_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    absence_nomination_id: Mapped[str | None] = mapped_column(
        ForeignKey("absence_nominations.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    job = relationship("Job", back_populates="delegations")


class ExceptionalTransitionRequest(UuidPrimaryKeyMixin, Base):
    __tablename__ = "exceptional_transition_requests"
    __table_args__ = (
        Index("ix_exception_requests_job_status", "job_id", "status", "requested_at"),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[ExceptionalAction] = mapped_column(
        enum_column(ExceptionalAction, "exceptional_action", 16), nullable=False
    )
    status: Mapped[ExceptionalRequestStatus] = mapped_column(
        enum_column(ExceptionalRequestStatus, "exceptional_request_status", 16), nullable=False
    )
    requested_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)

    job = relationship("Job")


class JobEditRequest(UuidPrimaryKeyMixin, Base):
    __tablename__ = "job_edit_requests"
    __table_args__ = (Index("ix_job_edit_requests_job_status", "job_id", "status", "requested_at"),)

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[EditRequestStatus] = mapped_column(
        enum_column(EditRequestStatus, "edit_request_status", 16), nullable=False
    )
    requested_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)

    job = relationship("Job", back_populates="edit_requests")


class AuditEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_job_time", "job_id", "occurred_at", "id"),
        Index("ix_audit_events_actor_time", "actor_user_id", "occurred_at", "id"),
    )

    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=True
    )
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    authorization_context: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    affected_job_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class JobVersion(UuidPrimaryKeyMixin, Base):
    __tablename__ = "job_versions"
    __table_args__ = (
        UniqueConstraint("job_id", "version_number", name="one_job_version"),
        Index("ix_job_versions_job_time", "job_id", "recorded_at", "version_number"),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class UserAvailabilityEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "user_availability_events"
    __table_args__ = (
        Index("ix_user_availability_events_user_time", "user_id", "effective_at", "id"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    previous_availability: Mapped[EmployeeAvailability] = mapped_column(
        enum_column(EmployeeAvailability, "previous_employee_availability", 16),
        nullable=False,
    )
    availability: Mapped[EmployeeAvailability] = mapped_column(
        enum_column(EmployeeAvailability, "availability_event_value", 16),
        nullable=False,
    )
    effective_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
@event.listens_for(JobVersion, "before_update")
@event.listens_for(JobVersion, "before_delete")
@event.listens_for(UserAvailabilityEvent, "before_update")
@event.listens_for(UserAvailabilityEvent, "before_delete")
@event.listens_for(JobResponsibilityEvent, "before_update")
@event.listens_for(JobResponsibilityEvent, "before_delete")
def _prevent_history_mutation(*_args: object) -> None:
    raise RuntimeError("Historical records are append-only.")
