"""Shipment job aggregate root."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import TimestampMixin, UtcDateTime, UuidPrimaryKeyMixin
from nfpl_access_control.models.enums import JobDirection, JobMode, JobStage


class Job(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_jobs_scope_stage_id", "client_id", "branch_id", "stage", "id"),
        Index("ix_jobs_assignee_stage_id", "assignee_id", "stage", "id"),
    )

    reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[str] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    direction: Mapped[JobDirection] = mapped_column(
        Enum(
            JobDirection,
            native_enum=False,
            create_constraint=True,
            name="job_direction",
            length=10,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    mode: Mapped[JobMode] = mapped_column(
        Enum(
            JobMode,
            native_enum=False,
            create_constraint=True,
            name="job_mode",
            length=10,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    stage: Mapped[JobStage] = mapped_column(
        Enum(
            JobStage,
            native_enum=False,
            create_constraint=True,
            name="job_stage",
            length=20,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=JobStage.CONFIRMED,
    )
    assignee_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    goods_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    container_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checklist_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    checklist_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prepared_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    prepared_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    checked_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    checked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    filed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    filed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)

    client = relationship("Client", back_populates="jobs")
    branch = relationship("Branch", back_populates="jobs")
    assignee = relationship("User", back_populates="assigned_jobs", foreign_keys=[assignee_id])
    responsibilities = relationship("JobResponsibility", back_populates="job")
    delegations = relationship("JobDelegation", back_populates="job")

    __mapper_args__ = {"version_id_col": version}
