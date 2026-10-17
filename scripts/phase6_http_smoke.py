"""Run disposable real-HTTP Checker, Filing, and Client Viewer workflows."""

from __future__ import annotations

import gc
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from nfpl_access_control.core.security import hash_password
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.models import (
    AccountStatus,
    Client,
    PasswordCredential,
    User,
    UserKind,
)
from nfpl_access_control.services.bootstrap import bootstrap_first_admin

ROOT = Path(__file__).resolve().parents[1]
ADMIN_EMAIL = "phase6-admin@example.test"
PASSWORD = "Phase6 Smoke Password 42!"
USERS = {
    "maker": ("phase6-maker@example.test", UserKind.STAFF),
    "checker": ("phase6-checker@example.test", UserKind.STAFF),
    "filer": ("phase6-filer@example.test", UserKind.STAFF),
    "client": ("phase6-client@example.test", UserKind.CLIENT),
}


def _port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> object:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=10) as response:
        if response.status == 204:
            return None
        return json.loads(response.read())


def _wait_for_health(base_url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(50):
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Uvicorn exited before health check:\n{output}")
        try:
            if _request(base_url, "GET", "/health") == {"status": "ok"}:
                return
        except (HTTPError, URLError):
            time.sleep(0.1)
    raise RuntimeError("Uvicorn did not become healthy.")


def _login(base_url: str, email: str) -> str:
    result = _request(
        base_url,
        "POST",
        "/v1/auth/login",
        payload={"email": email, "password": PASSWORD},
    )
    assert isinstance(result, dict)
    return str(result["access_token"])


def _scope(client_id: str | None = None) -> dict[str, object]:
    return {
        "all_clients": client_id is None,
        "client_id": client_id,
        "all_branches": True,
        "branch_id": None,
        "all_directions": True,
        "direction": None,
        "all_modes": True,
        "mode": None,
    }


def _grant(
    base_url: str,
    token: str,
    user_id: str,
    role_slug: str,
    client_id: str | None = None,
) -> None:
    _request(
        base_url,
        "POST",
        "/v1/admin/role-assignments",
        token=token,
        payload={
            "target_user_id": user_id,
            "role_slug": role_slug,
            "reason": f"Phase 6 HTTP smoke {role_slug} grant",
            "scope": _scope(client_id),
        },
    )


def _assign(
    base_url: str,
    token: str,
    job_id: str,
    responsibility: str,
    user_id: str,
) -> None:
    _request(
        base_url,
        "PUT",
        f"/v1/admin/jobs/{job_id}/assignment",
        token=token,
        payload={
            "responsibility": responsibility,
            "target_user_id": user_id,
            "reason": f"Phase 6 HTTP smoke {responsibility} assignment",
        },
    )


def _complete_items(job: dict[str, object]) -> list[dict[str, object]]:
    checklist = job["checklist_data"]
    assert isinstance(checklist, dict)
    items = checklist["items"]
    assert isinstance(items, list)
    return [
        {
            "key": item["key"],
            "status": "complete",
            "justification": None,
        }
        for item in items
    ]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nfpl-phase6-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'smoke.db'}"
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["database_url"] = database_url
        command.upgrade(config, "head")

        engine = create_database_engine(database_url)
        seeded_ids: dict[str, str] = {}
        with Session(engine) as session:
            admin = bootstrap_first_admin(
                session,
                display_name="Phase 6 Admin",
                email=ADMIN_EMAIL,
                password=PASSWORD,
                branch_code="P6",
                branch_name="Phase 6 Branch",
            )
            session.flush()
            session.add_all(
                [
                    Client(code="P6A", name="Phase 6 Visible Client"),
                    Client(code="P6B", name="Phase 6 Hidden Client"),
                ]
            )
            for name, (email, kind) in USERS.items():
                user = User(
                    email=email,
                    display_name=f"Phase 6 {name.title()}",
                    kind=kind,
                    branch_id=admin.branch_id if kind is UserKind.STAFF else None,
                    account_status=AccountStatus.ACTIVE,
                    is_active=True,
                )
                user.password_credential = PasswordCredential(password_hash=hash_password(PASSWORD))
                session.add(user)
                session.flush()
                seeded_ids[name] = user.id
            session.commit()
        engine.dispose()

        port = _port()
        base_url = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment["DATABASE_URL"] = database_url
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "nfpl_access_control.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            _wait_for_health(base_url, process)
            admin_token = _login(base_url, ADMIN_EMAIL)
            references = _request(base_url, "GET", "/v1/admin/reference-data", token=admin_token)
            employees = _request(base_url, "GET", "/v1/admin/employees?limit=25", token=admin_token)
            assert isinstance(references, dict) and isinstance(employees, dict)
            listed_emails = {item["email"] for item in employees["items"]}
            assert all(
                email in listed_emails for email, kind in USERS.values() if kind is UserKind.STAFF
            )
            ids = seeded_ids
            visible_client = next(item for item in references["clients"] if item["code"] == "P6A")
            hidden_client = next(item for item in references["clients"] if item["code"] == "P6B")
            branch = references["branches"][0]
            _grant(base_url, admin_token, ids["maker"], "maker")
            _grant(base_url, admin_token, ids["checker"], "checker")
            _grant(base_url, admin_token, ids["filer"], "filing-officer")
            _grant(
                base_url,
                admin_token,
                ids["client"],
                "client-viewer",
                visible_client["id"],
            )

            job = _request(
                base_url,
                "POST",
                "/v1/jobs",
                token=admin_token,
                payload={
                    "reference": "PHASE6-HTTP-001",
                    "client_id": visible_client["id"],
                    "branch_id": branch["id"],
                    "direction": "export",
                    "mode": "fcl",
                    "goods_description": "Phase 6 machinery",
                    "container_reference": "P6-CONT-1",
                },
            )
            hidden = _request(
                base_url,
                "POST",
                "/v1/jobs",
                token=admin_token,
                payload={
                    "reference": "PHASE6-HIDDEN-001",
                    "client_id": hidden_client["id"],
                    "branch_id": branch["id"],
                    "direction": "import",
                    "mode": "air",
                    "goods_description": "Other client shipment",
                    "container_reference": None,
                },
            )
            assert isinstance(job, dict) and isinstance(hidden, dict)
            _assign(base_url, admin_token, job["id"], "maker", ids["maker"])
            _assign(base_url, admin_token, job["id"], "checker", ids["checker"])
            _assign(base_url, admin_token, job["id"], "filing_officer", ids["filer"])

            maker_token = _login(base_url, USERS["maker"][0])
            prepared = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/prepare",
                token=maker_token,
                payload={
                    "expected_version": job["version"],
                    "checklist_data": None,
                    "justification": "",
                },
            )
            assert isinstance(prepared, dict) and prepared["stage"] == "prepared"
            assert len(_complete_items(prepared)) == 5

            checker_token = _login(base_url, USERS["checker"][0])
            checker_queue = _request(base_url, "GET", "/v1/my-work?limit=20", token=checker_token)
            checker_detail = _request(base_url, "GET", f"/v1/jobs/{job['id']}", token=checker_token)
            assert isinstance(checker_queue, dict) and checker_queue["count"] == 1
            assert isinstance(checker_detail, dict)
            checked = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/check",
                token=checker_token,
                payload={
                    "expected_version": checker_detail["version"],
                    "approved": True,
                    "reason": "",
                    "checklist_items": _complete_items(checker_detail),
                    "justification": "",
                },
            )
            assert isinstance(checked, dict) and checked["stage"] == "checked"

            filer_token = _login(base_url, USERS["filer"][0])
            filer_queue = _request(base_url, "GET", "/v1/my-work?limit=20", token=filer_token)
            history = _request(
                base_url,
                "GET",
                f"/v1/jobs/{job['id']}/operational-history?limit=25",
                token=filer_token,
            )
            assert isinstance(filer_queue, dict) and filer_queue["count"] == 1
            assert isinstance(history, list) and history
            returned = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/return-for-correction",
                token=filer_token,
                payload={
                    "expected_version": checked["version"],
                    "category": "both",
                    "reason": "Description and verification evidence need correction.",
                },
            )
            assert isinstance(returned, dict) and returned["stage"] == "confirmed"

            corrected = _request(
                base_url,
                "PATCH",
                f"/v1/jobs/{job['id']}",
                token=maker_token,
                payload={
                    "expected_version": returned["version"],
                    "goods_description": "Corrected Phase 6 machinery",
                    "container_reference": "P6-CONT-1",
                },
            )
            assert isinstance(corrected, dict)
            resubmitted = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/prepare",
                token=maker_token,
                payload={
                    "expected_version": corrected["version"],
                    "checklist_data": None,
                    "justification": "Corrected description and confirmed supporting evidence.",
                },
            )
            assert isinstance(resubmitted, dict)
            rechecked = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/check",
                token=checker_token,
                payload={
                    "expected_version": resubmitted["version"],
                    "approved": True,
                    "reason": "",
                    "checklist_items": _complete_items(resubmitted),
                    "justification": "Reevaluated every item after Maker correction.",
                },
            )
            assert isinstance(rechecked, dict) and rechecked["stage"] == "checked"
            filed = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/file",
                token=filer_token,
                payload={"expected_version": rechecked["version"]},
            )
            assert isinstance(filed, dict) and filed["stage"] == "filed"

            client_token = _login(base_url, USERS["client"][0])
            shipments = _request(base_url, "GET", "/v1/client/jobs?limit=25", token=client_token)
            status = _request(
                base_url,
                "GET",
                f"/v1/client/jobs/{job['id']}/status",
                token=client_token,
            )
            client_history = _request(
                base_url,
                "GET",
                f"/v1/client/jobs/{job['id']}/history?limit=25",
                token=client_token,
            )
            updates = _request(base_url, "GET", "/v1/client/updates?limit=25", token=client_token)
            assert isinstance(shipments, dict)
            assert [item["job_id"] for item in shipments["items"]] == [job["id"]]
            assert isinstance(status, dict) and status["stage"] == "filed"
            assert isinstance(client_history, list) and client_history
            assert all(
                "reason" not in item and "actor_user_id" not in item for item in client_history
            )
            assert isinstance(updates, dict)
            assert {item["job_id"] for item in updates["items"]} == {job["id"]}
            try:
                _request(
                    base_url,
                    "GET",
                    f"/v1/client/jobs/{hidden['id']}/status",
                    token=client_token,
                )
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("Cross-client status unexpectedly succeeded.")

            print(
                json.dumps(
                    {
                        "health": "ok",
                        "checker_queue_count": checker_queue["count"],
                        "generated_checklist_items": len(_complete_items(prepared)),
                        "initial_verification": checked["stage"],
                        "filing_return_category": returned["last_return_category"],
                        "maker_correction": corrected["goods_description"],
                        "reevaluation": rechecked["stage"],
                        "final_stage": filed["stage"],
                        "client_shipments": len(shipments["items"]),
                        "client_history_events": len(client_history),
                        "client_update_events": len(updates["items"]),
                        "cross_client_status": "hidden",
                    },
                    indent=2,
                )
            )
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            gc.collect()
            time.sleep(0.2)


if __name__ == "__main__":
    raise SystemExit(main())
