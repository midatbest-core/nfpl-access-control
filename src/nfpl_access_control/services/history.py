"""Immutable shipment history and point-in-time authorization reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nfpl_access_control.models import (
    AbsenceNomination,
    AbsenceNominationStatus,
    AccountStateEvent,
    AccountStatus,
    EmployeeAvailability,
    JobDelegation,
    JobDirection,
    JobMode,
    JobResponsibilityEvent,
    JobStage,
    JobVersion,
    Permission,
    ResponsibilityEventType,
    ResponsibilityType,
    RoleAssignment,
    RolePermission,
    User,
    UserAvailabilityEvent,
)

PERMISSION_RESPONSIBILITY = {
    Permission.JOB_PREPARE: ResponsibilityType.MAKER,
    Permission.JOB_CHECK: ResponsibilityType.CHECKER,
    Permission.JOB_FILE: ResponsibilityType.FILING_OFFICER,
}


@dataclass(frozen=True, slots=True)
class VersionDiff:
    field: str
    before: object
    after: object


@dataclass(frozen=True, slots=True)
class HistoricalCandidate:
    user_id: str
    display_name: str
    explanation: str


@dataclass(frozen=True, slots=True)
class ActualHistoryEvent:
    actor_user_id: str
    action: str
    occurred_at: datetime
    version_number: int


@dataclass(frozen=True, slots=True)
class OperationalHistoryItem:
    version_number: int
    occurred_at: datetime
    actor_user_id: str
    action: str
    reason: str
    stage: JobStage
    changed_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HistoricalEligibilityResult:
    evaluated_at: datetime
    permission: Permission
    complete: bool
    limitations: tuple[str, ...]
    candidates: tuple[HistoricalCandidate, ...]
    actual_events_at_timestamp: tuple[ActualHistoryEvent, ...]
    job_version: int | None


class HistoryValidationError(ValueError):
    pass


class HistoryService:
    def __init__(self, session: Session):
        self.session = session

    def list_versions(
        self,
        job_id: str,
        *,
        before_version: int | None = None,
        limit: int = 50,
    ) -> list[JobVersion]:
        if not 1 <= limit <= 100:
            raise HistoryValidationError("History limit must be between 1 and 100.")
        statement = select(JobVersion).where(JobVersion.job_id == job_id)
        if before_version is not None:
            statement = statement.where(JobVersion.version_number < before_version)
        return list(
            self.session.scalars(statement.order_by(JobVersion.version_number.desc()).limit(limit))
        )

    def version(self, job_id: str, version_number: int) -> JobVersion | None:
        return self.session.scalar(
            select(JobVersion).where(
                JobVersion.job_id == job_id,
                JobVersion.version_number == version_number,
            )
        )

    def state_at(self, job_id: str, at: datetime) -> JobVersion | None:
        self._aware(at)
        return self.session.scalar(
            select(JobVersion)
            .where(JobVersion.job_id == job_id, JobVersion.recorded_at <= at)
            .order_by(JobVersion.recorded_at.desc(), JobVersion.version_number.desc())
            .limit(1)
        )

    def diff(
        self,
        job_id: str,
        from_version: int,
        to_version: int,
    ) -> list[VersionDiff]:
        earlier = self.version(job_id, from_version)
        later = self.version(job_id, to_version)
        if earlier is None or later is None:
            raise HistoryValidationError("Both requested job versions must exist.")
        fields = sorted(set(earlier.snapshot) | set(later.snapshot))
        return [
            VersionDiff(field, earlier.snapshot.get(field), later.snapshot.get(field))
            for field in fields
            if earlier.snapshot.get(field) != later.snapshot.get(field)
        ]

    def changes_for_field(self, job_id: str, field: str) -> list[JobVersion]:
        versions = list(
            self.session.scalars(
                select(JobVersion)
                .where(JobVersion.job_id == job_id)
                .order_by(JobVersion.version_number)
            )
        )
        changed: list[JobVersion] = []
        sentinel = object()
        previous: object = sentinel
        for version in versions:
            value = version.snapshot.get(field, sentinel)
            if previous is not sentinel and value != previous:
                changed.append(version)
            previous = value
        return changed

    def operational_history(
        self,
        job_id: str,
        *,
        before_version: int | None = None,
        limit: int = 50,
    ) -> list[OperationalHistoryItem]:
        if not 1 <= limit <= 100:
            raise HistoryValidationError("History limit must be between 1 and 100.")
        statement = select(JobVersion).where(JobVersion.job_id == job_id)
        if before_version is not None:
            statement = statement.where(JobVersion.version_number < before_version)
        versions = list(
            self.session.scalars(
                statement.order_by(JobVersion.version_number.desc()).limit(limit + 1)
            )
        )
        result: list[OperationalHistoryItem] = []
        for index, version in enumerate(versions[:limit]):
            previous = versions[index + 1] if index + 1 < len(versions) else None
            fields = set(version.snapshot)
            if previous is not None:
                fields.update(previous.snapshot)
                changed = tuple(
                    sorted(
                        field
                        for field in fields
                        if version.snapshot.get(field) != previous.snapshot.get(field)
                    )
                )
            else:
                changed = tuple(sorted(fields))
            try:
                stage = JobStage(str(version.snapshot["stage"]))
            except (KeyError, ValueError) as error:
                raise HistoryValidationError(
                    "The operational history contains invalid stage data."
                ) from error
            result.append(
                OperationalHistoryItem(
                    version_number=version.version_number,
                    occurred_at=version.recorded_at,
                    actor_user_id=version.actor_user_id,
                    action=version.action,
                    reason=version.reason,
                    stage=stage,
                    changed_fields=changed,
                )
            )
        return result

    def historical_eligibility(
        self,
        *,
        job_id: str,
        permission: Permission,
        at: datetime,
    ) -> HistoricalEligibilityResult:
        self._aware(at)
        version = self.state_at(job_id, at)
        if version is None:
            return HistoricalEligibilityResult(
                evaluated_at=at,
                permission=permission,
                complete=False,
                limitations=("No trustworthy job version exists at or before this timestamp.",),
                candidates=(),
                actual_events_at_timestamp=(),
                job_version=None,
            )
        limitations: list[str] = []
        try:
            snapshot = version.snapshot
            client_id = str(snapshot["client_id"])
            branch_id = str(snapshot["branch_id"])
            direction = JobDirection(str(snapshot["direction"]))
            mode = JobMode(str(snapshot["mode"]))
            stage = JobStage(str(snapshot["stage"]))
        except (KeyError, TypeError, ValueError):
            return HistoricalEligibilityResult(
                evaluated_at=at,
                permission=permission,
                complete=False,
                limitations=("The historical job snapshot has incomplete policy scope data.",),
                candidates=(),
                actual_events_at_timestamp=self._actual_events(job_id, at),
                job_version=version.version_number,
            )

        users = self._permission_candidates(
            permission,
            at,
            client_id=client_id,
            branch_id=branch_id,
            direction=direction,
            mode=mode,
        )
        visible_ids = {
            user.id
            for user in self._permission_candidates(
                Permission.JOB_VIEW,
                at,
                client_id=client_id,
                branch_id=branch_id,
                direction=direction,
                mode=mode,
            )
        }
        users = [user for user in users if user.id in visible_ids]
        if permission in PERMISSION_RESPONSIBILITY:
            users, responsibility_complete = self._apply_historical_responsibility(
                users,
                job_id,
                PERMISSION_RESPONSIBILITY[permission],
                at,
            )
            if not responsibility_complete:
                limitations.append(
                    "Responsibility history is incomplete at the requested timestamp."
                )
        users = self._apply_stage_and_separation(users, permission, stage, snapshot)
        users = self._apply_account_status(users, at)
        users = self._apply_availability(users, at)
        candidates = tuple(
            HistoricalCandidate(
                user_id=user.id,
                display_name=user.display_name,
                explanation=(
                    "Effective scoped permission, visibility, responsibility, "
                    "availability, job state, and separation rules allowed this action."
                ),
            )
            for user in sorted(users, key=lambda item: (item.display_name, item.id))
        )
        return HistoricalEligibilityResult(
            evaluated_at=at,
            permission=permission,
            complete=not limitations,
            limitations=tuple(limitations),
            candidates=candidates,
            actual_events_at_timestamp=self._actual_events(job_id, at),
            job_version=version.version_number,
        )

    def _permission_candidates(
        self,
        permission: Permission,
        at: datetime,
        *,
        client_id: str,
        branch_id: str,
        direction: JobDirection,
        mode: JobMode,
    ) -> list[User]:
        return list(
            self.session.scalars(
                select(User)
                .join(RoleAssignment, RoleAssignment.user_id == User.id)
                .join(RolePermission, RolePermission.role_id == RoleAssignment.role_id)
                .where(
                    User.created_at <= at,
                    RolePermission.permission == permission,
                    RoleAssignment.valid_from <= at,
                    or_(RoleAssignment.valid_until.is_(None), RoleAssignment.valid_until > at),
                    or_(RoleAssignment.revoked_at.is_(None), RoleAssignment.revoked_at > at),
                    or_(
                        RoleAssignment.all_clients.is_(True),
                        RoleAssignment.client_id == client_id,
                    ),
                    or_(
                        RoleAssignment.all_branches.is_(True),
                        RoleAssignment.branch_id == branch_id,
                    ),
                    or_(
                        RoleAssignment.all_directions.is_(True),
                        RoleAssignment.direction == direction,
                    ),
                    or_(RoleAssignment.all_modes.is_(True), RoleAssignment.mode == mode),
                )
                .distinct()
            )
        )

    def _apply_historical_responsibility(
        self,
        users: list[User],
        job_id: str,
        responsibility: ResponsibilityType,
        at: datetime,
    ) -> tuple[list[User], bool]:
        events = list(
            self.session.scalars(
                select(JobResponsibilityEvent)
                .where(
                    JobResponsibilityEvent.job_id == job_id,
                    JobResponsibilityEvent.responsibility == responsibility,
                    JobResponsibilityEvent.occurred_at <= at,
                    JobResponsibilityEvent.event_type.in_(
                        (
                            ResponsibilityEventType.ASSIGNED,
                            ResponsibilityEventType.REASSIGNED,
                            ResponsibilityEventType.UNASSIGNED,
                        )
                    ),
                )
                .order_by(
                    JobResponsibilityEvent.occurred_at.desc(),
                    JobResponsibilityEvent.id.desc(),
                )
            )
        )
        responsible_ids: set[str] = set()
        complete = bool(events)
        if events and events[0].new_user_id is not None:
            responsible_ids.add(events[0].new_user_id)
        responsible_ids.update(
            self.session.scalars(
                select(JobDelegation.delegate_user_id).where(
                    JobDelegation.job_id == job_id,
                    JobDelegation.responsibility == responsibility,
                    JobDelegation.valid_from <= at,
                    JobDelegation.valid_until > at,
                    or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > at),
                )
            )
        )
        return [user for user in users if user.id in responsible_ids], complete

    def _apply_availability(self, users: list[User], at: datetime) -> list[User]:
        if not users:
            return []
        user_ids = [user.id for user in users]
        events = list(
            self.session.scalars(
                select(UserAvailabilityEvent)
                .where(UserAvailabilityEvent.user_id.in_(user_ids))
                .order_by(
                    UserAvailabilityEvent.user_id,
                    UserAvailabilityEvent.effective_at,
                    UserAvailabilityEvent.id,
                )
            )
        )
        by_user: dict[str, list[UserAvailabilityEvent]] = {}
        for event in events:
            by_user.setdefault(event.user_id, []).append(event)

        absent_by_nomination = set(
            self.session.scalars(
                select(AbsenceNomination.requester_user_id).where(
                    AbsenceNomination.requester_user_id.in_(user_ids),
                    AbsenceNomination.status.in_(
                        (AbsenceNominationStatus.APPROVED, AbsenceNominationStatus.REVOKED)
                    ),
                    AbsenceNomination.decided_at <= at,
                    AbsenceNomination.valid_from <= at,
                    AbsenceNomination.valid_until > at,
                    or_(
                        AbsenceNomination.revoked_at.is_(None),
                        AbsenceNomination.revoked_at > at,
                    ),
                )
            )
        )
        available: list[User] = []
        for user in users:
            history = by_user.get(user.id, [])
            past = [event for event in history if event.effective_at <= at]
            if past:
                value = past[-1].availability
            elif history:
                value = history[0].previous_availability
            else:
                value = user.availability
            if value is not EmployeeAvailability.ABSENT and user.id not in absent_by_nomination:
                available.append(user)
        return available

    def _apply_account_status(self, users: list[User], at: datetime) -> list[User]:
        if not users:
            return []
        user_ids = [user.id for user in users]
        events = list(
            self.session.scalars(
                select(AccountStateEvent)
                .where(AccountStateEvent.user_id.in_(user_ids))
                .order_by(
                    AccountStateEvent.user_id,
                    AccountStateEvent.effective_at,
                    AccountStateEvent.id,
                )
            )
        )
        by_user: dict[str, list[AccountStateEvent]] = {}
        for event in events:
            by_user.setdefault(event.user_id, []).append(event)
        active: list[User] = []
        for user in users:
            history = by_user.get(user.id, [])
            past = [event for event in history if event.effective_at <= at]
            if past:
                status = past[-1].status
            elif history:
                status = history[0].previous_status
            else:
                status = AccountStatus.ACTIVE if user.is_active else AccountStatus.DISABLED
            if status is AccountStatus.ACTIVE:
                active.append(user)
        return active

    @staticmethod
    def _apply_stage_and_separation(
        users: list[User],
        permission: Permission,
        stage: JobStage,
        snapshot: dict[str, object],
    ) -> list[User]:
        valid_stages = {
            Permission.JOB_PREPARE: {
                JobStage.CONFIRMED,
                JobStage.REOPENED,
            },
            Permission.JOB_UPDATE: {
                JobStage.CONFIRMED,
                JobStage.PREPARED,
                JobStage.CHECKED,
                JobStage.REOPENED,
            },
            Permission.JOB_CHECK: {JobStage.PREPARED},
            Permission.JOB_FILE: {JobStage.CHECKED},
        }
        allowed_stages = valid_stages.get(permission)
        if allowed_stages is not None and stage not in allowed_stages:
            return []
        if permission in {Permission.JOB_PREPARE, Permission.JOB_UPDATE} and snapshot.get(
            "maker_edit_locked", False
        ):
            return []
        if permission is Permission.JOB_CHECK:
            preparer_id = snapshot.get("prepared_by_user_id")
            if not preparer_id:
                return []
            return [user for user in users if user.id != preparer_id]
        if permission is Permission.JOB_FILE and not snapshot.get("checked_by_user_id"):
            return []
        return users

    def _actual_events(self, job_id: str, at: datetime) -> tuple[ActualHistoryEvent, ...]:
        versions = self.session.scalars(
            select(JobVersion)
            .where(JobVersion.job_id == job_id, JobVersion.recorded_at == at)
            .order_by(JobVersion.version_number)
        )
        return tuple(
            ActualHistoryEvent(
                actor_user_id=version.actor_user_id,
                action=version.action,
                occurred_at=version.recorded_at,
                version_number=version.version_number,
            )
            for version in versions
        )

    @staticmethod
    def _aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise HistoryValidationError("Historical timestamps must include a UTC offset.")
