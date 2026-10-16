"""Role and scoped-assignment API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from nfpl_access_control.authorization import Scope
from nfpl_access_control.models import JobDirection, JobMode, Permission, Role


class ScopeRequest(BaseModel):
    all_clients: bool
    client_id: str | None = None
    all_branches: bool
    branch_id: str | None = None
    all_directions: bool
    direction: JobDirection | None = None
    all_modes: bool
    mode: JobMode | None = None

    @model_validator(mode="after")
    def validate_explicit_dimensions(self) -> ScopeRequest:
        if not self.to_domain().is_valid():
            raise ValueError("each dimension must explicitly select all or one specific value")
        return self

    def to_domain(self) -> Scope:
        return Scope(
            all_clients=self.all_clients,
            client_id=self.client_id,
            all_branches=self.all_branches,
            branch_id=self.branch_id,
            all_directions=self.all_directions,
            direction=self.direction,
            all_modes=self.all_modes,
            mode=self.mode,
        )


class RoleCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    permissions: set[Permission] = Field(min_length=1)


class RoleResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    is_system: bool
    permissions: list[Permission]

    @classmethod
    def from_role(cls, role: Role) -> RoleResponse:
        return cls(
            id=role.id,
            slug=role.slug,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permissions=sorted((item.permission for item in role.permissions), key=str),
        )


class RoleAssignmentCreateRequest(BaseModel):
    target_user_id: str
    role_slug: str
    scope: ScopeRequest
    reason: str = Field(min_length=1, max_length=1000)
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None


class RoleAssignmentRevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class RoleAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    role_id: str
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None
    version: int
    all_clients: bool
    client_id: str | None
    all_branches: bool
    branch_id: str | None
    all_directions: bool
    direction: JobDirection | None
    all_modes: bool
    mode: JobMode | None
