"""Role definitions, explicit multidimensional scopes, and grant history."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nfpl_access_control.db.base import Base
from nfpl_access_control.models.base import (
    TimestampMixin,
    UtcDateTime,
    UuidPrimaryKeyMixin,
)
from nfpl_access_control.models.enums import (
    AssignmentEventType,
    JobDirection,
    JobMode,
    Permission,
)


class Role(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    permissions = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )
    assignments = relationship("RoleAssignment", back_populates="role")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission: Mapped[Permission] = mapped_column(
        Enum(
            Permission,
            native_enum=False,
            create_constraint=True,
            name="permission",
            length=32,
            values_callable=lambda values: [value.value for value in values],
        ),
        primary_key=True,
    )

    role = relationship("Role", back_populates="permissions")


class RoleAssignment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        CheckConstraint(
            "(all_clients AND client_id IS NULL) OR (NOT all_clients AND client_id IS NOT NULL)",
            name="explicit_client_scope",
        ),
        CheckConstraint(
            "(all_branches AND branch_id IS NULL) OR (NOT all_branches AND branch_id IS NOT NULL)",
            name="explicit_branch_scope",
        ),
        CheckConstraint(
            "(all_directions AND direction IS NULL) OR "
            "(NOT all_directions AND direction IS NOT NULL)",
            name="explicit_direction_scope",
        ),
        CheckConstraint(
            "(all_modes AND mode IS NULL) OR (NOT all_modes AND mode IS NOT NULL)",
            name="explicit_mode_scope",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="valid_effective_interval",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index(
            "ix_role_assignments_user_effective",
            "user_id",
            "valid_from",
            "valid_until",
            "revoked_at",
        ),
        Index(
            "ix_role_assignments_scope",
            "client_id",
            "branch_id",
            "direction",
            "mode",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True
    )
    all_clients: Mapped[bool] = mapped_column(Boolean, nullable=False)
    branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    all_branches: Mapped[bool] = mapped_column(Boolean, nullable=False)
    direction: Mapped[JobDirection | None] = mapped_column(
        Enum(
            JobDirection,
            native_enum=False,
            create_constraint=True,
            name="assignment_direction",
            length=10,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=True,
    )
    all_directions: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mode: Mapped[JobMode | None] = mapped_column(
        Enum(
            JobMode,
            native_enum=False,
            create_constraint=True,
            name="assignment_mode",
            length=10,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=True,
    )
    all_modes: Mapped[bool] = mapped_column(Boolean, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    granted_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revoked_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    grant_reason: Mapped[str] = mapped_column(Text, nullable=False)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    role = relationship("Role", back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_user_id])
    client = relationship("Client")
    branch = relationship("Branch")
    events = relationship(
        "RoleAssignmentEvent",
        back_populates="assignment",
        order_by="RoleAssignmentEvent.occurred_at",
    )

    __mapper_args__ = {"version_id_col": version}


class RoleAssignmentEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "role_assignment_events"
    __table_args__ = (
        Index(
            "ix_role_assignment_events_assignment_time",
            "assignment_id",
            "occurred_at",
            "id",
        ),
    )

    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("role_assignments.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[AssignmentEventType] = mapped_column(
        Enum(
            AssignmentEventType,
            native_enum=False,
            create_constraint=True,
            name="assignment_event_type",
            length=16,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    assignment = relationship("RoleAssignment", back_populates="events")
    actor = relationship("User")
