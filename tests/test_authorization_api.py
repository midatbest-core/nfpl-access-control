from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization.roles import ADMIN_ROLE, MAKER_ROLE
from nfpl_access_control.models import (
    Branch,
    Client,
    Job,
    JobDirection,
    JobMode,
    Role,
    RoleAssignment,
    User,
    UserKind,
)
from tests.conftest import TEST_TOKEN


def test_invisible_and_nonexistent_jobs_have_identical_public_denial(
    api_client: TestClient, session: Session
) -> None:
    client = Client(code="LEAK-C", name="Private Client")
    branch = Branch(code="LEAK-B", name="Private Branch")
    job = Job(
        reference="PRIVATE-JOB",
        client=client,
        branch=branch,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
    )
    session.add(job)
    session.commit()
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    payload = {"permission": "job:view"}

    hidden = api_client.post(f"/v1/authorization/jobs/{job.id}", headers=headers, json=payload)
    missing = api_client.post(
        "/v1/authorization/jobs/does-not-exist", headers=headers, json=payload
    )

    assert hidden.status_code == missing.status_code == 200
    assert hidden.json() == missing.json()
    assert hidden.json()["reason_code"] == "job_not_found_or_not_visible"
    assert "PRIVATE-JOB" not in hidden.text


def test_authorization_endpoint_requires_authenticated_actor(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/v1/authorization/jobs/anything",
        json={"permission": "job:view"},
    )

    assert response.status_code == 401


def test_admin_route_denies_authenticated_non_admin(api_client: TestClient) -> None:
    response = api_client.post(
        "/v1/admin/roles",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={
            "slug": "operations-reviewer",
            "name": "Operations Reviewer",
            "permissions": ["job:view"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason_code"] == "admin_required"


def test_global_admin_can_create_safe_role_through_authenticated_api(
    api_client: TestClient, session: Session, active_user: User
) -> None:
    admin_role = session.scalar(select(Role).where(Role.slug == ADMIN_ROLE))
    assert admin_role is not None
    session.add(
        RoleAssignment(
            user_id=active_user.id,
            role_id=admin_role.id,
            all_clients=True,
            client_id=None,
            all_branches=True,
            branch_id=None,
            all_directions=True,
            direction=None,
            all_modes=True,
            mode=None,
            valid_from=datetime.now(UTC) - timedelta(minutes=1),
            granted_by_user_id=active_user.id,
            grant_reason="trusted test bootstrap",
        )
    )
    session.commit()

    response = api_client.post(
        "/v1/admin/roles",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={
            "slug": "operations-reviewer",
            "name": "Operations Reviewer",
            "description": "A safe configurable role.",
            "permissions": ["job:view", "job:file"],
        },
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "operations-reviewer"
    assert set(response.json()["permissions"]) == {"job:view", "job:file"}


def test_duplicate_scoped_grant_returns_precise_conflict_explanation(
    api_client: TestClient, session: Session, active_user: User
) -> None:
    now = datetime.now(UTC)
    admin_role = session.scalar(select(Role).where(Role.slug == ADMIN_ROLE))
    maker_role = session.scalar(select(Role).where(Role.slug == MAKER_ROLE))
    assert admin_role is not None and maker_role is not None
    target = User(
        email="duplicate-grant@example.test",
        display_name="Duplicate Grant",
        kind=UserKind.STAFF,
    )
    session.add(target)
    session.flush()
    for user, role in ((active_user, admin_role), (target, maker_role)):
        session.add(
            RoleAssignment(
                user_id=user.id,
                role_id=role.id,
                all_clients=True,
                client_id=None,
                all_branches=True,
                branch_id=None,
                all_directions=True,
                direction=None,
                all_modes=True,
                mode=None,
                valid_from=now - timedelta(minutes=1),
                granted_by_user_id=active_user.id,
                grant_reason="trusted test setup",
            )
        )
    session.commit()

    response = api_client.post(
        "/v1/admin/role-assignments",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={
            "target_user_id": target.id,
            "role_slug": MAKER_ROLE,
            "reason": "Duplicate grant attempt",
            "scope": {
                "all_clients": True,
                "client_id": None,
                "all_branches": True,
                "branch_id": None,
                "all_directions": True,
                "direction": None,
                "all_modes": True,
                "mode": None,
            },
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An overlapping identical role assignment already exists."
