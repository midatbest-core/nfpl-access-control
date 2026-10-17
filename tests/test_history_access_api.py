from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import ReasonCode
from nfpl_access_control.core.security import hash_api_token
from nfpl_access_control.models import ApiCredential, AuditEvent, Job, User
from tests.test_history import _versioned_setup


def _credential(user: User, token: str) -> None:
    user.credentials.append(
        ApiCredential(name=f"{user.display_name} history test", token_hash=hash_api_token(token))
    )


def test_history_access_matrix_is_enforced_by_the_api(
    api_client: TestClient,
    session: Session,
) -> None:
    values = _versioned_setup(session)
    admin = values["admin"]
    maker = values["maker"]
    checker = values["checker"]
    filer = values["filer"]
    job = values["job"]
    assert all(isinstance(user, User) for user in (admin, maker, checker, filer))
    assert isinstance(job, Job)
    tokens = {
        "admin": "phase4-admin-history-token",
        "maker": "phase4-maker-history-token",
        "checker": "phase4-checker-history-token",
        "filer": "phase4-filer-history-token",
    }
    for name, token in tokens.items():
        _credential(values[name], token)  # type: ignore[arg-type]
    session.commit()

    def get(path: str, actor: str):
        return api_client.get(path, headers={"Authorization": f"Bearer {tokens[actor]}"})

    full_history = f"/v1/admin/jobs/{job.id}/versions"
    audit_history = f"/v1/admin/jobs/{job.id}/audit"
    operational_history = f"/v1/jobs/{job.id}/operational-history"

    assert get(full_history, "admin").status_code == 200
    assert get(audit_history, "admin").status_code == 200
    assert get(operational_history, "admin").status_code == 200
    assert get(operational_history, "filer").status_code == 200
    assert get(full_history, "filer").status_code == 404
    assert get(audit_history, "filer").status_code == 404
    assert get(operational_history, "maker").status_code == 404
    assert get(operational_history, "checker").status_code == 404

    payload = get(operational_history, "filer").json()
    assert payload
    assert set(payload[0]) == {
        "version_number",
        "occurred_at",
        "actor_user_id",
        "action",
        "reason",
        "stage",
        "changed_fields",
    }
    assert "snapshot" not in payload[0]
    assert "authorization_context" not in payload[0]

    stale = api_client.post(
        f"/v1/jobs/{job.id}/prepare",
        headers={"Authorization": f"Bearer {tokens['maker']}"},
        json={"expected_version": job.version + 1, "checklist_data": {"complete": True}},
    )
    invalid_stage = api_client.post(
        f"/v1/jobs/{job.id}/file",
        headers={"Authorization": f"Bearer {tokens['filer']}"},
        json={"expected_version": job.version},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason_code"] == ReasonCode.STALE_VERSION.value
    assert invalid_stage.status_code == 409
    assert invalid_stage.json()["detail"]["reason_code"] == ReasonCode.INVALID_STAGE.value

    session.expire_all()
    persisted_denials = list(
        session.scalars(
            select(AuditEvent.action)
            .where(AuditEvent.job_id == job.id, AuditEvent.denied.is_(True))
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        )
    )
    assert set(persisted_denials) == {"job.prepare.denied", "job.file.denied"}
