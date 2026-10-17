"""Pydantic contracts for Phase 3 shipment workflow APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from nfpl_access_control.models import (
    ChecklistItemStatus,
    EditRequestStatus,
    EmployeeAvailability,
    ExceptionalAction,
    FilingReturnCategory,
    Job,
    JobDirection,
    JobMode,
    JobStage,
    ResponsibilityType,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobCreateRequest(StrictRequest):
    reference: str = Field(min_length=1, max_length=64)
    client_id: str
    branch_id: str
    direction: JobDirection
    mode: JobMode
    goods_description: str = Field(default="", max_length=5000)
    container_reference: str | None = Field(default=None, max_length=100)


class JobUpdateRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    goods_description: str | None = Field(default=None, max_length=5000)
    container_reference: str | None = Field(default=None, max_length=100)


class PrepareRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    checklist_data: dict[str, object] | None = None
    justification: str = Field(default="", max_length=1000)


class ChecklistItemDecisionRequest(StrictRequest):
    key: str = Field(min_length=1, max_length=64)
    status: ChecklistItemStatus
    justification: str | None = Field(default=None, max_length=1000)


class CheckRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    approved: bool | None = None
    reason: str = Field(default="", max_length=1000)
    checklist_items: list[ChecklistItemDecisionRequest] | None = None
    justification: str = Field(default="", max_length=1000)


class VersionRequest(StrictRequest):
    expected_version: int = Field(ge=1)


class ReasonedVersionRequest(VersionRequest):
    reason: str = Field(min_length=1, max_length=1000)


class FilingReturnRequest(ReasonedVersionRequest):
    category: FilingReturnCategory


class EditRequestCreate(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class EditRequestDecision(ReasonedVersionRequest):
    approved: bool


class AssignmentRequest(StrictRequest):
    responsibility: ResponsibilityType
    target_user_id: str | None
    reason: str = Field(min_length=1, max_length=1000)


class DelegationRequest(StrictRequest):
    responsibility: ResponsibilityType
    delegate_user_id: str
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    reason: str = Field(min_length=1, max_length=1000)


class ExceptionalTransitionCreateRequest(StrictRequest):
    action: ExceptionalAction
    reason: str = Field(min_length=1, max_length=1000)


class AvailabilityRequest(StrictRequest):
    availability: EmployeeAvailability
    reason: str = Field(min_length=1, max_length=1000)


class ReasonRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class JobResponse(BaseModel):
    id: str
    reference: str
    client_id: str
    branch_id: str
    direction: JobDirection
    mode: JobMode
    stage: JobStage
    goods_description: str
    container_reference: str | None
    checklist_data: dict[str, object]
    checklist_revision: int
    maker_edit_locked: bool
    maker_correction_required: bool
    checker_correction_required: bool
    last_return_category: FilingReturnCategory | None
    last_return_reason: str | None
    last_maker_justification: str | None
    last_checker_justification: str | None
    prepared_by_user_id: str | None
    checked_by_user_id: str | None
    filed_by_user_id: str | None
    version: int

    @classmethod
    def from_job(cls, job: Job) -> JobResponse:
        return cls.model_validate(job, from_attributes=True)


class ClientJobDetailResponse(BaseModel):
    id: str
    reference: str
    client_id: str
    direction: JobDirection
    mode: JobMode
    stage: JobStage
    version: int

    @classmethod
    def from_job(cls, job: Job) -> ClientJobDetailResponse:
        return cls.model_validate(job, from_attributes=True)


class ResponsibilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    responsibility: ResponsibilityType
    user_id: str | None
    assigned_at: datetime
    version: int


class DelegationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    responsibility: ResponsibilityType
    delegator_user_id: str
    delegate_user_id: str
    valid_from: datetime
    valid_until: datetime
    revoked_at: datetime | None


class SuggestionResponse(BaseModel):
    responsibility: ResponsibilityType
    user_id: str
    display_name: str
    pending_workload: int


class ExceptionalTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    action: ExceptionalAction
    status: str
    requested_by_user_id: str
    requested_at: datetime
    reason: str


class EditRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    status: EditRequestStatus
    requested_by_user_id: str
    requested_at: datetime
    reason: str
    decided_by_user_id: str | None
    decided_at: datetime | None
    decision_reason: str | None
