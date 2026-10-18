from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nfpl_access_control import main as main_module
from nfpl_access_control.core.config import Settings
from nfpl_access_control.models import User
from tests.conftest import TEST_TOKEN


def test_health_is_public(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_returns_actor_derived_from_bearer_token(
    api_client: TestClient, active_user: User
) -> None:
    response = api_client.get(
        "/v1/identity/me",
        headers={
            "Authorization": f"Bearer {TEST_TOKEN}",
            "X-User-Id": "attacker-controlled-id",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == active_user.id
    assert response.json()["email"] == active_user.email
    assert response.json()["kind"] == "staff"
    assert datetime.fromisoformat(response.json()["created_at"]).tzinfo is UTC


def test_me_rejects_missing_credential_without_identity_details(api_client: TestClient) -> None:
    response = api_client.get("/v1/identity/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid or expired authentication credential"}


def test_me_rejects_invalid_credential_with_same_generic_response(api_client: TestClient) -> None:
    response = api_client.get("/v1/identity/me", headers={"Authorization": "Bearer nfpl_invalid"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired authentication credential"}


def test_configured_local_frontend_login_preflight_receives_cors_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = "http://localhost:5173"
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(cors_allowed_origins=(origin,)),
    )
    with TestClient(main_module.create_app()) as client:
        response = client.options(
            "/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        denied = client.options(
            "/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
