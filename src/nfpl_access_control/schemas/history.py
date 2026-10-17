"""Internal history and sanitized client update response contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from nfpl_access_control.models import JobStage, Permission
from nfpl_access_control.services.client_updates import (
    ClientShipmentStatus,
    ClientShipmentUpdate,
)
from nfpl_access_control.services.history import (
    HistoricalEligibilityResult,
    OperationalHistoryItem,
    VersionDiff,
)


class JobVersionResponse(BaseModel):
    id: str
    job_id: str
    version_number: int
    recorded_at: datetime
    actor_user_id: str
    action: str
    reason: str
    snapshot: dict[str, object]


class VersionDiffResponse(BaseModel):
    field: str
    before: object
    after: object

    @classmethod
    def from_diff(cls, item: VersionDiff) -> VersionDiffResponse:
        return cls(field=item.field, before=item.before, after=item.after)


class AuditEventResponse(BaseModel):
    id: str
    job_id: str | None
    actor_user_id: str
    action: str
    occurred_at: datetime
    reason: str
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    authorization_context: dict[str, object]
    affected_job_version: int | None
    denied: bool


class OperationalHistoryResponse(BaseModel):
    version_number: int
    occurred_at: datetime
    actor_user_id: str
    action: str
    reason: str
    stage: JobStage
    changed_fields: list[str]

    @classmethod
    def from_item(cls, item: OperationalHistoryItem) -> OperationalHistoryResponse:
        return cls(
            version_number=item.version_number,
            occurred_at=item.occurred_at,
            actor_user_id=item.actor_user_id,
            action=item.action,
            reason=item.reason,
            stage=item.stage,
            changed_fields=list(item.changed_fields),
        )


class HistoricalCandidateResponse(BaseModel):
    user_id: str
    display_name: str
    explanation: str


class ActualHistoryEventResponse(BaseModel):
    actor_user_id: str
    action: str
    occurred_at: datetime
    version_number: int


class HistoricalEligibilityResponse(BaseModel):
    evaluated_at: datetime
    permission: Permission
    complete: bool
    limitations: list[str]
    candidates: list[HistoricalCandidateResponse]
    actual_events_at_timestamp: list[ActualHistoryEventResponse]
    job_version: int | None

    @classmethod
    def from_result(cls, result: HistoricalEligibilityResult) -> HistoricalEligibilityResponse:
        return cls(
            evaluated_at=result.evaluated_at,
            permission=result.permission,
            complete=result.complete,
            limitations=list(result.limitations),
            candidates=[
                HistoricalCandidateResponse(
                    user_id=item.user_id,
                    display_name=item.display_name,
                    explanation=item.explanation,
                )
                for item in result.candidates
            ],
            actual_events_at_timestamp=[
                ActualHistoryEventResponse(
                    actor_user_id=item.actor_user_id,
                    action=item.action,
                    occurred_at=item.occurred_at,
                    version_number=item.version_number,
                )
                for item in result.actual_events_at_timestamp
            ],
            job_version=result.job_version,
        )


class ClientStatusResponse(BaseModel):
    job_id: str
    reference: str
    stage: JobStage
    progress_percent: int
    updated_at: datetime
    version: int

    @classmethod
    def from_status(cls, item: ClientShipmentStatus) -> ClientStatusResponse:
        return cls(
            job_id=item.job_id,
            reference=item.reference,
            stage=item.stage,
            progress_percent=item.progress_percent,
            updated_at=item.updated_at,
            version=item.version,
        )


class ClientUpdateResponse(BaseModel):
    cursor: str
    job_id: str
    reference: str
    stage: JobStage
    progress_percent: int
    message: str
    occurred_at: datetime
    version: int

    @classmethod
    def from_update(cls, item: ClientShipmentUpdate) -> ClientUpdateResponse:
        return cls(
            cursor=item.cursor,
            job_id=item.job_id,
            reference=item.reference,
            stage=item.stage,
            progress_percent=item.progress_percent,
            message=item.message,
            occurred_at=item.occurred_at,
            version=item.version,
        )


class ClientUpdatePageResponse(BaseModel):
    items: list[ClientUpdateResponse]
    next_cursor: str | None
