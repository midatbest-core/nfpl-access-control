"""Bearer credential authentication.

Authorization is intentionally not implemented here. Authentication establishes a
trustworthy actor; Phase 2 will decide what that actor may see or do.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.core.security import hash_api_token
from nfpl_access_control.models import ApiCredential, User


def _as_utc(value: datetime) -> datetime:
    """Normalize timestamps returned by SQLite without changing the instant."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def authenticate_api_token(
    session: Session, token: str, *, now: datetime | None = None
) -> User | None:
    """Resolve an active actor from a bearer token, failing closed on bad state."""

    if not token:
        return None

    credential = session.scalar(
        select(ApiCredential)
        .join(ApiCredential.user)
        .where(
            ApiCredential.token_hash == hash_api_token(token),
            ApiCredential.revoked_at.is_(None),
            User.is_active.is_(True),
        )
    )
    if credential is None:
        return None

    current_time = now or datetime.now(UTC)
    if credential.expires_at is not None and _as_utc(credential.expires_at) <= current_time:
        return None

    return credential.user
