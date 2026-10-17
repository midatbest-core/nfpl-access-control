from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization.roles import CLIENT_VIEWER_ROLE, PARSER_SERVICE_ROLE
from nfpl_access_control.models import (
    Branch,
    Client,
    JobDirection,
    JobMode,
    Role,
    RoleAssignment,
    User,
    UserKind,
)
from nfpl_access_control.services.workflow import WorkflowService
from tests.conftest import TEST_TOKEN
from tests.test_workflow import NOW


def _grant_for_client(
    session: Session,
    *,
    user: User,
    role_slug: str,
    grantor: User,
    client_id: str | None,
) -> None:
    role = session.scalar(select(Role).where(Role.slug == role_slug))
    assert role is not None
    session.add(
        RoleAssignment(
            user_id=user.id,
            role_id=role.id,
            client_id=client_id,
            all_clients=client_id is None,
            branch_id=None,
            all_branches=True,
            direction=None,
            all_directions=True,
            mode=None,
            all_modes=True,
            valid_from=NOW - timedelta(days=1),
            valid_until=None,
            granted_by_user_id=grantor.id,
            grant_reason="client history test",
        )
    )
    session.flush()


def test_client_status_history_and_cursor_feed_are_isolated_and_sanitized(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    active_user.kind = UserKind.CLIENT
    active_user.created_at = NOW - timedelta(days=2)
    branch = Branch(code="CLIENT-HIST-BR", name="Client History Branch")
    client_a = Client(code="CLIENT-HIST-A", name="Client History A")
    client_b = Client(code="CLIENT-HIST-B", name="Client History B")
    parser = User(
        email="client-history-parser@example.test",
        display_name="Client History Parser",
        kind=UserKind.SERVICE,
        created_at=NOW - timedelta(days=2),
    )
    session.add_all([branch, client_a, client_b, parser])
    session.flush()
    _grant_for_client(
        session,
        user=active_user,
        role_slug=CLIENT_VIEWER_ROLE,
        grantor=parser,
        client_id=client_a.id,
    )
    _grant_for_client(
        session,
        user=parser,
        role_slug=PARSER_SERVICE_ROLE,
        grantor=parser,
        client_id=None,
    )
    service = WorkflowService(session)
    visible = service.create_job(
        actor=parser,
        reference="CLIENT-VISIBLE",
        client_id=client_a.id,
        branch_id=branch.id,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
        goods_description="Private internal description",
        now=NOW,
    )
    hidden = service.create_job(
        actor=parser,
        reference="CLIENT-HIDDEN",
        client_id=client_b.id,
        branch_id=branch.id,
        direction=JobDirection.EXPORT,
        mode=JobMode.FCL,
        now=NOW,
    )
    service.update_job(
        actor=parser,
        job=visible,
        expected_version=visible.version,
        container_reference="INTERNAL-CONTAINER",
        now=NOW + timedelta(minutes=1),
    )
    session.commit()
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}

    status = api_client.get(f"/v1/client/jobs/{visible.id}/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["reference"] == "CLIENT-VISIBLE"
    assert api_client.get(f"/v1/client/jobs/{hidden.id}/status", headers=headers).status_code == 404
    detail = api_client.get(f"/v1/jobs/{visible.id}", headers=headers)
    assert detail.status_code == 200
    assert set(detail.json()) == {
        "id",
        "reference",
        "client_id",
        "direction",
        "mode",
        "stage",
        "version",
    }
    assert api_client.get(f"/v1/jobs/{hidden.id}", headers=headers).status_code == 404
    assert (
        api_client.get(f"/v1/admin/jobs/{visible.id}/versions", headers=headers).status_code == 404
    )
    assert (
        api_client.get(f"/v1/jobs/{visible.id}/operational-history", headers=headers).status_code
        == 404
    )

    first = api_client.get("/v1/client/updates?limit=1", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()
    assert len(first_payload["items"]) == 1
    assert first_payload["next_cursor"]
    item = first_payload["items"][0]
    assert set(item) == {
        "cursor",
        "job_id",
        "reference",
        "stage",
        "progress_percent",
        "message",
        "occurred_at",
        "version",
    }
    assert item["job_id"] == visible.id

    second = api_client.get(
        "/v1/client/updates",
        headers=headers,
        params={"limit": 1, "cursor": first_payload["next_cursor"]},
    )
    assert second.status_code == 200
    assert [entry["job_id"] for entry in second.json()["items"]] == [visible.id]
    history = api_client.get(f"/v1/client/jobs/{visible.id}/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert all("actor_user_id" not in entry for entry in history.json())
    assert all("reason" not in entry for entry in history.json())
    assert (
        api_client.get("/v1/client/updates", headers=headers, params={"cursor": "%%%"}).status_code
        == 422
    )
