from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nfpl_access_control.main import create_app
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


def test_configured_frontend_origin_receives_cors_headers() -> None:
    with TestClient(create_app(cors_allowed_origins=("https://nfpl.vercel.app",))) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://nfpl.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://nfpl.vercel.app"
