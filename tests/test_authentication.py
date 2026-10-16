from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from nfpl_access_control.models import ApiCredential, User
from nfpl_access_control.services.authentication import authenticate_api_token
from tests.conftest import TEST_TOKEN


def test_valid_token_authenticates_active_user(session: Session, active_user: User) -> None:
    actor = authenticate_api_token(session, TEST_TOKEN)

    assert actor is not None
    assert actor.id == active_user.id


@pytest.mark.parametrize("credential_state", ["revoked", "expired"])
def test_revoked_or_expired_token_fails_closed(
    session: Session, active_user: User, credential_state: str
) -> None:
    credential = active_user.credentials[0]
    now = datetime.now(UTC)
    if credential_state == "revoked":
        credential.revoked_at = now
    else:
        credential.expires_at = now - timedelta(seconds=1)
    session.commit()

    assert authenticate_api_token(session, TEST_TOKEN, now=now) is None


def test_expiration_boundary_is_denied(session: Session, active_user: User) -> None:
    now = datetime.now(UTC)
    active_user.credentials[0].expires_at = now
    session.commit()

    assert authenticate_api_token(session, TEST_TOKEN, now=now) is None


def test_inactive_user_cannot_authenticate(session: Session, active_user: User) -> None:
    active_user.is_active = False
    session.commit()

    assert authenticate_api_token(session, TEST_TOKEN) is None


def test_plaintext_token_is_not_stored(session: Session, active_user: User) -> None:
    credential = session.get(ApiCredential, active_user.credentials[0].id)

    assert credential is not None
    assert credential.token_hash != TEST_TOKEN
    assert len(credential.token_hash) == 64
