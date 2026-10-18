"""Phase 5C absence, notification, queue, and dashboard contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from nfpl_access_control.models import (
    AbsenceJobOutcome,
    AbsenceNominationStatus,
    JobDirection,
    JobMode,
    JobStage,
    ResponsibilityType,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AbsenceNominationCreate(StrictRequest):
    nominee_user_id: str
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    reason: str = Field(min_length=1, max_length=1000)


class VersionedDecision(StrictRequest):
    expected_version: int = Field(ge=1)
    approved: bool
    reason: str = Field(min_length=1, max_length=1000)


class VersionedReason(StrictRequest):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class AbsenceOverrideRequest(StrictRequest):
    replacement_user_id: str
    reason: str = Field(min_length=1, max_length=1000)


class ClientQueryCreate(StrictRequest):
    category: Literal["delay", "cancellation", "reopening", "missing_update", "other"]
    explanation: str = Field(min_length=1, max_length=1000)


class AdminAttentionCreate(StrictRequest):
    explanation: str = Field(min_length=1, max_length=1000)


class AbsenceNominationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requester_user_id: str
    nominee_user_id: str
    valid_from: datetime
    valid_until: datetime
    reason: str
    status: AbsenceNominationStatus
    requested_at: datetime
    decided_by_user_id: str | None
    decided_at: datetime | None
    decision_reason: str | None
    version: int


class AbsenceOutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nomination_id: str
    job_id: str
    responsibility: ResponsibilityType
    nominee_user_id: str
    outcome: AbsenceJobOutcome
    reason: str
    delegation_id: str | None


class AbsenceCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    display_name: str
    eligible_assignment_count: int
    total_assignment_count: int


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str | None
    job_reference: str | None
    event_type: str
    message: str
    target_path: str
    created_at: datetime
    read_at: datetime | None


class MarkAllReadResponse(BaseModel):
    updated: int


class AttentionReceiptResponse(BaseModel):
    audit_event_id: str
    delivered: int


class WorkQueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    reference: str
    client_id: str
    client_name: str
    branch_id: str
    branch_name: str
    direction: JobDirection
    mode: JobMode
    stage: JobStage
    responsibility: ResponsibilityType
    next_action: str
    feedback: str | None
    assigned_at: datetime
    priority: int
    version: int
    is_delegated: bool


class WorkQueuePage(BaseModel):
    items: list[WorkQueueResponse]
    count: int
    limit: int
    next_cursor: str | None


class DashboardOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_jobs: int
    jobs_by_stage: dict[str, int]
    total_employees: int
    employees_by_availability: dict[str, int]
    pending_requests: int
    reassignment_required_jobs: int


class UrgentRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_type: str
    request_id: str
    requested_at: datetime
    requester_user_id: str
    reason: str
    job_id: str | None
    version: int


class ReferenceRecordResponse(BaseModel):
    id: str
    code: str
    name: str


class AdminReferenceDataResponse(BaseModel):
    clients: list[ReferenceRecordResponse]
    branches: list[ReferenceRecordResponse]


class AdminJobResponse(BaseModel):
    id: str
    reference: str
    client_id: str
    client_name: str
    branch_id: str
    branch_name: str
    stage: JobStage
    maker_user_id: str | None
    checker_user_id: str | None
    filing_officer_user_id: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    version: int


class AttentionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    reference: str
    client_name: str
    branch_name: str
    stage: JobStage
    version: int
    reasons: list[str]


class AttentionJobPage(BaseModel):
    items: list[AttentionJobResponse]
    next_cursor: str | None
