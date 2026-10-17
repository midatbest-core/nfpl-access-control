"""Employee registration, authentication, and directory contracts."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from nfpl_access_control.models import (
    AccountStatus,
    EmployeeAvailability,
    JobDirection,
    JobMode,
    User,
    UserKind,
)
from nfpl_access_control.services.employees import EmployeePage, EmployeeRecord

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistrationRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    branch_id: str = Field(min_length=1, max_length=36)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        result = " ".join(value.split())
        if not result:
            raise ValueError("name is required")
        return result

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        result = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(result):
            raise ValueError("a valid email address is required")
        return result


class LoginRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        result = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(result):
            raise ValueError("a valid email address is required")
        return result


class RegistrationResponse(BaseModel):
    id: str
    email: str
    display_name: str
    branch_id: str
    account_status: AccountStatus

    @classmethod
    def from_user(cls, user: User) -> RegistrationResponse:
        assert user.branch_id is not None
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            branch_id=user.branch_id,
            account_status=user.account_status,
        )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: AwareDatetime


class AccountActionRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class AvailabilityUpdateRequest(StrictRequest):
    availability: EmployeeAvailability
    reason: str = Field(min_length=1, max_length=1000)


class EmployeeRoleAssignmentResponse(BaseModel):
    id: str
    role_slug: str
    all_clients: bool
    client_id: str | None
    all_branches: bool
    branch_id: str | None
    all_directions: bool
    direction: JobDirection | None
    all_modes: bool
    mode: JobMode | None
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None


class EmployeeResponse(BaseModel):
    id: str
    email: str
    display_name: str
    kind: UserKind
    branch_id: str | None
    branch_name: str | None
    account_status: AccountStatus
    availability: EmployeeAvailability
    pending_workload: int
    roles: list[EmployeeRoleAssignmentResponse]
    created_at: datetime

    @classmethod
    def from_record(cls, record: EmployeeRecord) -> EmployeeResponse:
        user = record.user
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            kind=user.kind,
            branch_id=user.branch_id,
            branch_name=user.branch.name if user.branch else None,
            account_status=user.account_status,
            availability=user.availability,
            pending_workload=record.pending_workload,
            roles=[
                EmployeeRoleAssignmentResponse(
                    id=item.id,
                    role_slug=item.role.slug,
                    all_clients=item.all_clients,
                    client_id=item.client_id,
                    all_branches=item.all_branches,
                    branch_id=item.branch_id,
                    all_directions=item.all_directions,
                    direction=item.direction,
                    all_modes=item.all_modes,
                    mode=item.mode,
                    valid_from=item.valid_from,
                    valid_until=item.valid_until,
                    revoked_at=item.revoked_at,
                )
                for item in sorted(
                    user.role_assignments, key=lambda value: (value.role.slug, value.id)
                )
            ],
            created_at=user.created_at,
        )


class EmployeePageResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    limit: int

    @classmethod
    def from_page(cls, page: EmployeePage) -> EmployeePageResponse:
        return cls(
            items=[EmployeeResponse.from_record(item) for item in page.items],
            total=page.total,
            page=page.page,
            limit=page.limit,
        )
