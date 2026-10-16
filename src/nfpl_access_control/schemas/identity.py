"""Identity API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from nfpl_access_control.models.enums import UserKind


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    kind: UserKind
    created_at: datetime
