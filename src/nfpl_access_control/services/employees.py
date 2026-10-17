"""Admin employee directory, account lifecycle, and self availability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from nfpl_access_control.authorization import AuthorizationDecision, AuthorizationEngine, Scope
from nfpl_access_control.models import (
    AccountStateEvent,
    AccountStatus,
    EmployeeAvailability,
    Job,
    JobResponsibility,
    JobStage,
    Permission,
    RoleAssignment,
    User,
    UserAvailabilityEvent,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService

OPEN_STAGES = (
    JobStage.CONFIRMED,
    JobStage.PREPARED,
    JobStage.CHECKED,
    JobStage.REOPENED,
)


class EmployeeManagementError(Exception):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.explanation)
        self.decision = decision


class EmployeeValidationError(ValueError):
    pass


class EmployeeNotFoundError(EmployeeValidationError):
    pass


class EmployeeConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EmployeeRecord:
    user: User
    pending_workload: int


@dataclass(frozen=True, slots=True)
class EmployeePage:
    items: tuple[EmployeeRecord, ...]
    total: int
    page: int
    limit: int


class EmployeeManagementService:
    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)

    def list_employees(
        self,
        *,
        actor: User,
        page: int,
        limit: int,
        search: str | None = None,
        now: datetime | None = None,
    ) -> EmployeePage:
        current_time = now or datetime.now(UTC)
        self._require_admin(actor, current_time, "employee.list.denied")
        if page < 1 or not 1 <= limit <= 100:
            raise EmployeeValidationError("Page must be positive and limit must be 1-100.")
        workload = self._workload_subquery()
        filters = [User.kind == UserKind.STAFF]
        normalized_search = (search or "").strip().lower()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            filters.append(
                or_(
                    func.lower(User.display_name).like(pattern),
                    func.lower(User.email).like(pattern),
                )
            )
        total = self.session.scalar(select(func.count(User.id)).where(*filters)) or 0
        pending = func.coalesce(workload.c.pending, 0)
        rows = self.session.execute(
            select(User, pending)
            .outerjoin(workload, workload.c.user_id == User.id)
            .options(
                selectinload(User.branch),
                selectinload(User.role_assignments).selectinload(RoleAssignment.role),
            )
            .where(*filters)
            .order_by(User.display_name, User.id)
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        return EmployeePage(
            items=tuple(EmployeeRecord(user, int(count)) for user, count in rows),
            total=int(total),
            page=page,
            limit=limit,
        )

    def get_self(self, actor: User) -> EmployeeRecord:
        user = self.session.scalar(
            select(User)
            .options(
                selectinload(User.branch),
                selectinload(User.role_assignments).selectinload(RoleAssignment.role),
            )
            .where(User.id == actor.id)
        )
        if user is None:
            raise EmployeeValidationError("The authenticated employee no longer exists.")
        return EmployeeRecord(user, self._pending_workload(user.id))

    def get_employee(
        self,
        *,
        actor: User,
        employee_id: str,
        now: datetime | None = None,
    ) -> EmployeeRecord:
        current_time = now or datetime.now(UTC)
        self._require_admin(actor, current_time, "employee.view.denied")
        user = self.session.scalar(
            select(User)
            .options(
                selectinload(User.branch),
                selectinload(User.role_assignments).selectinload(RoleAssignment.role),
            )
            .where(User.id == employee_id, User.kind == UserKind.STAFF)
        )
        if user is None:
            raise EmployeeNotFoundError("The employee does not exist.")
        return EmployeeRecord(user, self._pending_workload(user.id))

    def transition_account_by_id(
        self,
        *,
        actor: User,
        employee_id: str,
        target: AccountStatus,
        expected_source: AccountStatus,
        reason: str,
        now: datetime | None = None,
    ) -> User:
        current_time = now or datetime.now(UTC)
        decision = self._require_admin(
            actor,
            current_time,
            "employee.account_state.denied",
            {"employee_id": employee_id, "target": target.value},
        )
        employee = self.session.get(User, employee_id)
        if employee is None:
            raise EmployeeNotFoundError("The employee does not exist.")
        if employee.account_status is not expected_source:
            raise EmployeeConflictError(
                f"Account must be {expected_source.value} for this operation."
            )
        return self._apply_account_transition(
            actor=actor,
            employee=employee,
            target=target,
            reason=reason,
            current_time=current_time,
            decision=decision,
        )

    def transition_account(
        self,
        *,
        actor: User,
        employee: User,
        target: AccountStatus,
        reason: str,
        now: datetime | None = None,
    ) -> User:
        current_time = now or datetime.now(UTC)
        decision = self._require_admin(
            actor,
            current_time,
            "employee.account_state.denied",
            {"employee_id": employee.id, "target": target.value},
        )
        return self._apply_account_transition(
            actor=actor,
            employee=employee,
            target=target,
            reason=reason,
            current_time=current_time,
            decision=decision,
        )

    def _apply_account_transition(
        self,
        *,
        actor: User,
        employee: User,
        target: AccountStatus,
        reason: str,
        current_time: datetime,
        decision: AuthorizationDecision,
    ) -> User:
        if employee.kind is not UserKind.STAFF:
            raise EmployeeValidationError("Account management applies only to employees.")
        if actor.id == employee.id:
            raise EmployeeValidationError("Administrators cannot change their own account state.")
        if not reason.strip():
            raise EmployeeValidationError("An account-state reason is required.")
        previous = employee.account_status
        allowed = {
            AccountStatus.PENDING: {AccountStatus.ACTIVE, AccountStatus.DISABLED},
            AccountStatus.ACTIVE: {AccountStatus.DISABLED},
            AccountStatus.DISABLED: {AccountStatus.ACTIVE},
        }
        if target not in allowed[previous]:
            raise EmployeeConflictError(
                f"Account cannot transition from {previous.value} to {target.value}."
            )
        employee.account_status = target
        employee.is_active = target is AccountStatus.ACTIVE
        if target is AccountStatus.DISABLED:
            for credential in employee.credentials:
                if credential.revoked_at is None:
                    credential.revoked_at = current_time
        self.session.add(
            AccountStateEvent(
                user_id=employee.id,
                previous_status=previous,
                status=target,
                effective_at=current_time,
                actor_user_id=actor.id,
                reason=reason.strip(),
            )
        )
        self.audit.record(
            actor=actor,
            action=f"employee.{target.value}",
            reason=reason.strip(),
            occurred_at=current_time,
            decision=decision,
            context={
                "employee_id": employee.id,
                "before": previous.value,
                "after": target.value,
            },
        )
        self.session.flush()
        return employee

    def set_own_availability(
        self,
        *,
        actor: User,
        availability: EmployeeAvailability,
        reason: str,
        now: datetime | None = None,
    ) -> User:
        current_time = now or datetime.now(UTC)
        if actor.kind is not UserKind.STAFF:
            raise EmployeeValidationError("Availability applies only to employees.")
        if not reason.strip():
            raise EmployeeValidationError("An availability change reason is required.")
        if actor.availability is availability:
            raise EmployeeConflictError("Availability is already set to the requested value.")
        previous = actor.availability
        actor.availability = availability
        self.session.add(
            UserAvailabilityEvent(
                user_id=actor.id,
                previous_availability=previous,
                availability=availability,
                effective_at=current_time,
                actor_user_id=actor.id,
                reason=reason.strip(),
            )
        )
        self.audit.record(
            actor=actor,
            action="employee.availability_changed",
            reason=reason.strip(),
            occurred_at=current_time,
            context={
                "employee_id": actor.id,
                "before": previous.value,
                "after": availability.value,
                "self_service": True,
            },
        )
        self.session.flush()
        return actor

    def _require_admin(
        self,
        actor: User,
        at: datetime,
        action: str,
        context: dict[str, object] | None = None,
    ) -> AuthorizationDecision:
        decision = self.authorization.authorize_admin(
            actor,
            Permission.ROLE_MANAGE,
            requested_scope=Scope.global_scope(),
            at=at,
        )
        if not decision.allowed:
            self.audit.record(
                actor=actor,
                action=action,
                reason=decision.explanation,
                occurred_at=at,
                decision=decision,
                context=context,
            )
            self.session.flush()
            raise EmployeeManagementError(decision)
        return decision

    def _pending_workload(self, user_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count(JobResponsibility.id))
                .join(Job, Job.id == JobResponsibility.job_id)
                .where(
                    JobResponsibility.user_id == user_id,
                    Job.stage.in_(OPEN_STAGES),
                )
            )
            or 0
        )

    @staticmethod
    def _workload_subquery():
        return (
            select(
                JobResponsibility.user_id.label("user_id"),
                func.count(JobResponsibility.id).label("pending"),
            )
            .join(Job, Job.id == JobResponsibility.job_id)
            .where(
                JobResponsibility.user_id.is_not(None),
                Job.stage.in_(OPEN_STAGES),
            )
            .group_by(JobResponsibility.user_id)
            .subquery()
        )
