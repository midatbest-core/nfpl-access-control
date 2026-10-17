from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization.roles import ADMIN_ROLE, MAKER_ROLE
from nfpl_access_control.models import Branch, Client, Role, RoleAssignment, User
from tests.conftest import TEST_TOKEN


def test_authenticated_admin_creates_job_and_unknown_protected_field_is_rejected(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    now = datetime.now(UTC)
    branch = Branch(code="API-WF-BR", name="API Workflow Branch")
    client = Client(code="API-WF-CL", name="API Workflow Client")
    role = session.scalar(select(Role).where(Role.slug == ADMIN_ROLE))
    maker_role = session.scalar(select(Role).where(Role.slug == MAKER_ROLE))
    assert role is not None and maker_role is not None
    session.add_all([branch, client])
    session.flush()
    session.add(
        RoleAssignment(
            user_id=active_user.id,
            role_id=role.id,
            client_id=None,
            all_clients=True,
            branch_id=None,
            all_branches=True,
            direction=None,
            all_directions=True,
            mode=None,
            all_modes=True,
            valid_from=now - timedelta(minutes=1),
            valid_until=None,
            granted_by_user_id=active_user.id,
            grant_reason="trusted test bootstrap",
        )
    )
    session.add(
        RoleAssignment(
            user_id=active_user.id,
            role_id=maker_role.id,
            client_id=None,
            all_clients=True,
            branch_id=None,
            all_branches=True,
            direction=None,
            all_directions=True,
            mode=None,
            all_modes=True,
            valid_from=now - timedelta(minutes=1),
            valid_until=None,
            granted_by_user_id=active_user.id,
            grant_reason="trusted Maker API test grant",
        )
    )
    session.commit()
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}

    created = api_client.post(
        "/v1/jobs",
        headers=headers,
        json={
            "reference": "API-WF-001",
            "client_id": client.id,
            "branch_id": branch.id,
            "direction": "import",
            "mode": "air",
            "goods_description": "API shipment",
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["stage"] == "confirmed"
    assigned = api_client.put(
        f"/v1/admin/jobs/{payload['id']}/assignment",
        headers=headers,
        json={
            "responsibility": "maker",
            "target_user_id": active_user.id,
            "reason": "Maker API detail test",
        },
    )
    assert assigned.status_code == 200
    responsibilities = api_client.get(
        f"/v1/jobs/{payload['id']}/responsibilities",
        headers=headers,
    )
    assert responsibilities.status_code == 200
    assert responsibilities.json() == [
        {
            "responsibility": "maker",
            "user_id": active_user.id,
            "display_name": active_user.display_name,
            "current_actor_responsible": True,
            "via_delegation": False,
        }
    ]
    rejected = api_client.patch(
        f"/v1/jobs/{payload['id']}",
        headers=headers,
        json={
            "expected_version": payload["version"],
            "goods_description": "attempt",
            "stage": "filed",
        },
    )
    assert rejected.status_code == 422
    unchanged = api_client.get(f"/v1/jobs/{payload['id']}", headers=headers)
    assert unchanged.status_code == 200
    assert unchanged.json()["stage"] == "confirmed"
