"""Fail-closed scoped RBAC authorization engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import exists, false, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from nfpl_access_control.authorization.decisions import AuthorizationDecision, ReasonCode
from nfpl_access_control.authorization.roles import ADMIN_ROLE
from nfpl_access_control.models import (
    AccountStatus,
    Job,
    JobDirection,
    JobMode,
    Permission,
    Role,
    RoleAssignment,
    RolePermission,
    User,
)


@dataclass(frozen=True, slots=True)
class Scope:
    all_clients: bool
    client_id: str | None
    all_branches: bool
    branch_id: str | None
    all_directions: bool
    direction: JobDirection | None
    all_modes: bool
    mode: JobMode | None

    @classmethod
    def for_job(cls, job: Job) -> Scope:
        return cls(
            all_clients=False,
            client_id=job.client_id,
            all_branches=False,
            branch_id=job.branch_id,
            all_directions=False,
            direction=job.direction,
            all_modes=False,
            mode=job.mode,
        )

    @classmethod
    def global_scope(cls) -> Scope:
        return cls(
            all_clients=True,
            client_id=None,
            all_branches=True,
            branch_id=None,
            all_directions=True,
            direction=None,
            all_modes=True,
            mode=None,
        )

    def is_valid(self) -> bool:
        return all(
            (
                self.all_clients != (self.client_id is not None),
                self.all_branches != (self.branch_id is not None),
                self.all_directions != (self.direction is not None),
                self.all_modes != (self.mode is not None),
            )
        )


class AuthorizationEngine:
    def __init__(self, session: Session):
        self.session = session

    def authorize_job(
        self,
        actor: User | None,
        permission: Permission,
        job: Job,
        *,
        at: datetime | None = None,
    ) -> AuthorizationDecision:
        evaluation_time = at or datetime.now(UTC)
        base_denial = self._validate_actor_and_time(actor, permission, evaluation_time)
        if base_denial is not None:
            return AuthorizationDecision(
                allowed=base_denial.allowed,
                reason_code=base_denial.reason_code,
                explanation=base_denial.explanation,
                permission=base_denial.permission,
                job_visible=False,
            )
        assert actor is not None

        job_scope = Scope.for_job(job)
        if not job_scope.is_valid():
            return self._deny(
                permission,
                ReasonCode.POLICY_DATA_INVALID,
                "The job has incomplete or inconsistent authorization scope data.",
            )

        visibility = self._evaluate_permission(
            actor, Permission.JOB_VIEW, job_scope, evaluation_time
        )
        if permission is Permission.JOB_VIEW:
            return AuthorizationDecision(
                allowed=visibility.allowed,
                reason_code=visibility.reason_code,
                explanation=visibility.explanation,
                permission=visibility.permission,
                job_visible=visibility.allowed,
            )
        if not visibility.allowed:
            return AuthorizationDecision(
                allowed=False,
                reason_code=visibility.reason_code,
                explanation=visibility.explanation,
                permission=permission,
                job_visible=False,
            )
        action_decision = self._evaluate_permission(actor, permission, job_scope, evaluation_time)
        return AuthorizationDecision(
            allowed=action_decision.allowed,
            reason_code=action_decision.reason_code,
            explanation=action_decision.explanation,
            permission=action_decision.permission,
            job_visible=True,
        )

    def authorize_scope(
        self,
        actor: User | None,
        permission: Permission,
        scope: Scope,
        *,
        at: datetime | None = None,
    ) -> AuthorizationDecision:
        """Authorize an action such as creation before a Job row exists."""

        evaluation_time = at or datetime.now(UTC)
        base_denial = self._validate_actor_and_time(actor, permission, evaluation_time)
        if base_denial is not None:
            return base_denial
        if not scope.is_valid():
            return self._deny(
                permission,
                ReasonCode.POLICY_DATA_INVALID,
                "The requested scope is incomplete or inconsistent.",
            )
        assert actor is not None
        return self._evaluate_permission(actor, permission, scope, evaluation_time)

    @staticmethod
    def job_scope_predicate(
        actor: User | None,
        permission: Permission,
        *,
        at: datetime,
    ):
        """Return a correlated Job policy predicate for bounded list queries."""

        if (
            actor is None
            or not actor.is_active
            or actor.account_status is not AccountStatus.ACTIVE
            or at.tzinfo is None
            or at.utcoffset() is None
        ):
            return false()
        assignment = aliased(RoleAssignment)
        role_permission = aliased(RolePermission)
        return exists(
            select(1)
            .select_from(assignment)
            .join(role_permission, role_permission.role_id == assignment.role_id)
            .where(
                assignment.user_id == actor.id,
                role_permission.permission == permission,
                assignment.valid_from <= at,
                or_(assignment.valid_until.is_(None), assignment.valid_until > at),
                or_(assignment.revoked_at.is_(None), assignment.revoked_at > at),
                or_(assignment.all_clients.is_(True), assignment.client_id == Job.client_id),
                or_(assignment.all_branches.is_(True), assignment.branch_id == Job.branch_id),
                or_(
                    assignment.all_directions.is_(True),
                    assignment.direction == Job.direction,
                ),
                or_(assignment.all_modes.is_(True), assignment.mode == Job.mode),
            )
            .correlate(Job)
        )

    def authorize_admin(
        self,
        actor: User | None,
        permission: Permission,
        *,
        requested_scope: Scope | None = None,
        at: datetime | None = None,
    ) -> AuthorizationDecision:
        evaluation_time = at or datetime.now(UTC)
        base_denial = self._validate_actor_and_time(actor, permission, evaluation_time)
        if base_denial is not None:
            return base_denial
        assert actor is not None

        scope = requested_scope or Scope.global_scope()
        if not scope.is_valid():
            return self._deny(
                permission,
                ReasonCode.POLICY_DATA_INVALID,
                "The requested access scope is incomplete or inconsistent.",
            )
        try:
            assignments = list(
                self.session.scalars(
                    select(RoleAssignment)
                    .join(RoleAssignment.role)
                    .join(Role.permissions)
                    .where(
                        RoleAssignment.user_id == actor.id,
                        Role.slug == ADMIN_ROLE,
                        Role.is_system.is_(True),
                        RolePermission.permission == permission,
                    )
                )
            )
        except (SQLAlchemyError, LookupError, ValueError):
            return self._deny(
                permission,
                ReasonCode.POLICY_DATA_INVALID,
                "Authorization policy data could not be evaluated safely.",
            )

        effective = [
            assignment
            for assignment in assignments
            if self._assignment_status(assignment, evaluation_time) is ReasonCode.ALLOWED
        ]
        if not effective:
            status = self._best_inactive_status(assignments, evaluation_time)
            return self._deny(
                permission,
                status or ReasonCode.ADMIN_REQUIRED,
                self._status_explanation(status)
                if status
                else "An effective built-in Admin assignment is required.",
            )

        for assignment in effective:
            if self._assignment_encompasses_scope(assignment, scope):
                return self._allow(permission)
        return self._deny(
            permission,
            ReasonCode.ADMIN_REQUIRED,
            "The Admin assignment does not encompass the requested scope.",
        )

    def _evaluate_permission(
        self,
        actor: User,
        permission: Permission,
        scope: Scope,
        at: datetime,
    ) -> AuthorizationDecision:
        try:
            assignments = list(
                self.session.scalars(
                    select(RoleAssignment)
                    .join(RoleAssignment.role)
                    .join(Role.permissions)
                    .where(
                        RoleAssignment.user_id == actor.id,
                        RolePermission.permission == permission,
                    )
                )
            )
        except (SQLAlchemyError, LookupError, ValueError):
            return self._deny(
                permission,
                ReasonCode.POLICY_DATA_INVALID,
                "Authorization policy data could not be evaluated safely.",
            )

        if not assignments:
            return self._deny(
                permission,
                ReasonCode.MISSING_PERMISSION,
                "No role assignment grants the required permission.",
            )

        effective = [
            assignment
            for assignment in assignments
            if self._assignment_status(assignment, at) is ReasonCode.ALLOWED
        ]
        if not effective:
            status = self._best_inactive_status(assignments, at)
            return self._deny(
                permission,
                status or ReasonCode.MISSING_PERMISSION,
                self._status_explanation(status),
            )

        mismatch_codes: set[ReasonCode] = set()
        for assignment in effective:
            mismatch = self._scope_mismatch(assignment, scope)
            if mismatch is None:
                return self._allow(permission)
            mismatch_codes.add(mismatch)

        for code in (
            ReasonCode.CLIENT_SCOPE_MISMATCH,
            ReasonCode.BRANCH_SCOPE_MISMATCH,
            ReasonCode.DIRECTION_SCOPE_MISMATCH,
            ReasonCode.MODE_SCOPE_MISMATCH,
            ReasonCode.POLICY_DATA_INVALID,
        ):
            if code in mismatch_codes:
                return self._deny(permission, code, self._scope_explanation(code))
        return self._deny(
            permission,
            ReasonCode.POLICY_DATA_INVALID,
            "Authorization scope could not be evaluated safely.",
        )

    @staticmethod
    def _validate_actor_and_time(
        actor: User | None, permission: Permission, at: datetime
    ) -> AuthorizationDecision | None:
        if actor is None:
            return AuthorizationEngine._deny(
                permission,
                ReasonCode.AUTHENTICATION_REQUIRED,
                "An authenticated actor is required.",
            )
        if not actor.is_active or actor.account_status is not AccountStatus.ACTIVE:
            return AuthorizationEngine._deny(
                permission,
                ReasonCode.ACTOR_INACTIVE,
                "The authenticated actor is inactive.",
            )
        if at.tzinfo is None or at.utcoffset() is None:
            return AuthorizationEngine._deny(
                permission,
                ReasonCode.POLICY_DATA_INVALID,
                "Authorization timestamps must include a UTC offset.",
            )
        return None

    @staticmethod
    def _assignment_status(assignment: RoleAssignment, at: datetime) -> ReasonCode:
        if assignment.valid_from > at:
            return ReasonCode.ACCESS_NOT_YET_EFFECTIVE
        if assignment.revoked_at is not None and assignment.revoked_at <= at:
            return ReasonCode.ACCESS_REVOKED
        if assignment.valid_until is not None and assignment.valid_until <= at:
            return ReasonCode.ACCESS_EXPIRED
        return ReasonCode.ALLOWED

    def _best_inactive_status(
        self, assignments: list[RoleAssignment], at: datetime
    ) -> ReasonCode | None:
        statuses = {self._assignment_status(assignment, at) for assignment in assignments}
        for status in (
            ReasonCode.ACCESS_REVOKED,
            ReasonCode.ACCESS_EXPIRED,
            ReasonCode.ACCESS_NOT_YET_EFFECTIVE,
        ):
            if status in statuses:
                return status
        return None

    @staticmethod
    def _scope_mismatch(assignment: RoleAssignment, requested: Scope) -> ReasonCode | None:
        assignment_scope = Scope(
            all_clients=assignment.all_clients,
            client_id=assignment.client_id,
            all_branches=assignment.all_branches,
            branch_id=assignment.branch_id,
            all_directions=assignment.all_directions,
            direction=assignment.direction,
            all_modes=assignment.all_modes,
            mode=assignment.mode,
        )
        if not assignment_scope.is_valid() or not requested.is_valid():
            return ReasonCode.POLICY_DATA_INVALID
        if not assignment.all_clients and assignment.client_id != requested.client_id:
            return ReasonCode.CLIENT_SCOPE_MISMATCH
        if not assignment.all_branches and assignment.branch_id != requested.branch_id:
            return ReasonCode.BRANCH_SCOPE_MISMATCH
        if not assignment.all_directions and assignment.direction != requested.direction:
            return ReasonCode.DIRECTION_SCOPE_MISMATCH
        if not assignment.all_modes and assignment.mode != requested.mode:
            return ReasonCode.MODE_SCOPE_MISMATCH
        return None

    @staticmethod
    def _assignment_encompasses_scope(assignment: RoleAssignment, requested: Scope) -> bool:
        mismatch = AuthorizationEngine._scope_mismatch(assignment, requested)
        if mismatch is ReasonCode.POLICY_DATA_INVALID:
            return False
        dimensions = (
            assignment.all_clients
            or (not requested.all_clients and assignment.client_id == requested.client_id),
            assignment.all_branches
            or (not requested.all_branches and assignment.branch_id == requested.branch_id),
            assignment.all_directions
            or (not requested.all_directions and assignment.direction == requested.direction),
            assignment.all_modes or (not requested.all_modes and assignment.mode == requested.mode),
        )
        return all(dimensions)

    @staticmethod
    def _allow(permission: Permission) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=True,
            reason_code=ReasonCode.ALLOWED,
            explanation="The actor has an effective permission grant for this scope.",
            permission=permission,
        )

    @staticmethod
    def _deny(permission: Permission, code: ReasonCode, explanation: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            allowed=False,
            reason_code=code,
            explanation=explanation,
            permission=permission,
        )

    @staticmethod
    def _scope_explanation(code: ReasonCode) -> str:
        return {
            ReasonCode.CLIENT_SCOPE_MISMATCH: "The permission does not cover this client.",
            ReasonCode.BRANCH_SCOPE_MISMATCH: "The permission does not cover this branch.",
            ReasonCode.DIRECTION_SCOPE_MISMATCH: (
                "The permission does not cover this shipment direction."
            ),
            ReasonCode.MODE_SCOPE_MISMATCH: "The permission does not cover this shipment mode.",
            ReasonCode.POLICY_DATA_INVALID: (
                "Authorization scope data is incomplete or inconsistent."
            ),
        }.get(code, "The permission does not cover the requested scope.")

    @staticmethod
    def _status_explanation(status: ReasonCode | None) -> str:
        return {
            ReasonCode.ACCESS_REVOKED: "The relevant access grant has been revoked.",
            ReasonCode.ACCESS_EXPIRED: "The relevant access grant has expired.",
            ReasonCode.ACCESS_NOT_YET_EFFECTIVE: (
                "The relevant access grant is not yet effective."
            ),
        }.get(status, "No effective permission grant exists.")
