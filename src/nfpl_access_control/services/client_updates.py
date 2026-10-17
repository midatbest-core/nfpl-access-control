"""Sanitized, request-driven client shipment status and incremental updates."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationDecision, AuthorizationEngine
from nfpl_access_control.models import Job, JobStage, JobVersion, Permission, User, UserKind

SAFE_ACTIONS = {
    "job.created": "Shipment created",
    "job.updated": "Shipment details updated",
    "job.prepared": "Shipment prepared",
    "job.checked": "Shipment checked",
    "job.check_rejected": "Shipment returned for correction",
    "job.checklist_returned": "Shipment returned for correction",
    "job.returned_for_correction": "Shipment returned for correction",
    "job.edit_request_approved": "Shipment opened for correction",
    "job.rechecked": "Shipment checked",
    "job.filed": "Shipment filed",
    "job.cancelled": "Shipment cancelled",
    "job.cancel_approved": "Shipment cancelled",
    "job.reopen_approved": "Shipment reopened",
}
PROGRESS = {
    JobStage.CONFIRMED: 25,
    JobStage.PREPARED: 50,
    JobStage.CHECKED: 75,
    JobStage.FILED: 100,
    JobStage.CANCELLED: 0,
    JobStage.REOPENED: 25,
}


class ClientAccessError(Exception):
    def __init__(self, decision: AuthorizationDecision | None = None):
        super().__init__("The shipment does not exist or is not visible.")
        self.decision = decision


class ClientCursorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClientShipmentStatus:
    job_id: str
    reference: str
    stage: JobStage
    progress_percent: int
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class ClientShipmentUpdate:
    cursor: str
    job_id: str
    reference: str
    stage: JobStage
    progress_percent: int
    message: str
    occurred_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class ClientUpdatePage:
    items: tuple[ClientShipmentUpdate, ...]
    next_cursor: str | None


class ClientUpdateService:
    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)

    def status(self, *, actor: User, job: Job, at: datetime | None = None) -> ClientShipmentStatus:
        current_time = at or datetime.now(UTC)
        self._require_client_actor(actor)
        decision = self.authorization.authorize_job(
            actor, Permission.CLIENT_HISTORY_VIEW, job, at=current_time
        )
        if not decision.allowed:
            raise ClientAccessError(decision)
        return ClientShipmentStatus(
            job_id=job.id,
            reference=job.reference,
            stage=job.stage,
            progress_percent=PROGRESS[job.stage],
            updated_at=job.updated_at,
            version=job.version,
        )

    def history(
        self,
        *,
        actor: User,
        job: Job,
        before_version: int | None = None,
        limit: int = 50,
        at: datetime | None = None,
    ) -> list[ClientShipmentUpdate]:
        current_time = at or datetime.now(UTC)
        self._require_client_actor(actor)
        decision = self.authorization.authorize_job(
            actor, Permission.CLIENT_HISTORY_VIEW, job, at=current_time
        )
        if not decision.allowed:
            raise ClientAccessError(decision)
        if not 1 <= limit <= 100:
            raise ClientCursorError("History limit must be between 1 and 100.")
        statement = select(JobVersion).where(JobVersion.job_id == job.id)
        if before_version is not None:
            statement = statement.where(JobVersion.version_number < before_version)
        versions = self.session.scalars(
            statement.order_by(JobVersion.version_number.desc()).limit(limit)
        )
        return [self._safe_update(version) for version in versions]

    def updates(
        self,
        *,
        actor: User,
        cursor: str | None = None,
        limit: int = 50,
        at: datetime | None = None,
    ) -> ClientUpdatePage:
        current_time = at or datetime.now(UTC)
        self._require_client_actor(actor)
        if not 1 <= limit <= 100:
            raise ClientCursorError("Update limit must be between 1 and 100.")
        cursor_value = self._decode_cursor(cursor) if cursor else None
        statement = (
            select(JobVersion)
            .join(Job, Job.id == JobVersion.job_id)
            .where(
                AuthorizationEngine.job_scope_predicate(
                    actor, Permission.JOB_VIEW, at=current_time
                ),
                AuthorizationEngine.job_scope_predicate(
                    actor, Permission.CLIENT_HISTORY_VIEW, at=current_time
                ),
            )
        )
        if cursor_value is not None:
            occurred_at, version_id = cursor_value
            statement = statement.where(
                or_(
                    JobVersion.recorded_at > occurred_at,
                    and_(
                        JobVersion.recorded_at == occurred_at,
                        JobVersion.id > version_id,
                    ),
                )
            )
        rows = list(
            self.session.scalars(
                statement.order_by(JobVersion.recorded_at, JobVersion.id).limit(limit + 1)
            )
        )
        has_more = len(rows) > limit
        visible = rows[:limit]
        items = tuple(self._safe_update(version) for version in visible)
        next_cursor = items[-1].cursor if has_more and items else None
        return ClientUpdatePage(items=items, next_cursor=next_cursor)

    @staticmethod
    def _safe_update(version: JobVersion) -> ClientShipmentUpdate:
        try:
            stage = JobStage(str(version.snapshot["stage"]))
            reference = str(version.snapshot["reference"])
        except (KeyError, ValueError) as error:
            raise ClientCursorError("A client update contains invalid historical data.") from error
        return ClientShipmentUpdate(
            cursor=ClientUpdateService._encode_cursor(version.recorded_at, version.id),
            job_id=version.job_id,
            reference=reference,
            stage=stage,
            progress_percent=PROGRESS[stage],
            message=SAFE_ACTIONS.get(version.action, "Shipment status updated"),
            occurred_at=version.recorded_at,
            version=version.version_number,
        )

    @staticmethod
    def _require_client_actor(actor: User) -> None:
        if actor.kind is not UserKind.CLIENT:
            raise ClientAccessError()

    @staticmethod
    def _encode_cursor(occurred_at: datetime, version_id: str) -> str:
        raw = f"{occurred_at.isoformat()}|{version_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> tuple[datetime, str]:
        try:
            padded = value + "=" * (-len(value) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode()
            timestamp, version_id = decoded.rsplit("|", 1)
            occurred_at = datetime.fromisoformat(timestamp)
            if occurred_at.tzinfo is None or not version_id:
                raise ValueError
            return occurred_at, version_id
        except (binascii.Error, ValueError, UnicodeDecodeError) as error:
            raise ClientCursorError("The update cursor is invalid.") from error
