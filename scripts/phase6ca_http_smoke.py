"""Run a disposable real-HTTP smoke test for the Phase 6C-A Maker APIs."""

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
ADMIN_EMAIL = "phase6ca-admin@example.test"
ADMIN_PASSWORD = "Phase6CA Admin Smoke 42!"
MAKER_EMAIL = "phase6ca-maker@example.test"
MAKER_PASSWORD = "Phase6CA Maker Smoke 42!"


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


def _login(base_url: str, email: str, password: str) -> str:
    result = _request(
        base_url,
        "POST",
        "/v1/auth/login",
        payload={"email": email, "password": password},
    )
    assert isinstance(result, dict)
    return str(result["access_token"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nfpl-phase6ca-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'smoke.db'}"
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["database_url"] = database_url
        command.upgrade(config, "head")

        engine = create_database_engine(database_url)
        with Session(engine) as session:
            admin = bootstrap_first_admin(
                session,
                display_name="Phase 6C-A Admin",
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD,
                branch_code="C6A",
                branch_name="Phase 6C-A Branch",
            )
            session.flush()
            session.add(Client(code="C6A", name="Phase 6C-A Client"))
            maker = User(
                email=MAKER_EMAIL,
                display_name="Phase 6C-A Maker",
                kind=UserKind.STAFF,
                branch_id=admin.branch_id,
                account_status=AccountStatus.ACTIVE,
                is_active=True,
            )
            maker.password_credential = PasswordCredential(
                password_hash=hash_password(MAKER_PASSWORD)
            )
            session.add(maker)
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
            admin_token = _login(base_url, ADMIN_EMAIL, ADMIN_PASSWORD)
            references = _request(base_url, "GET", "/v1/admin/reference-data", token=admin_token)
            employees = _request(base_url, "GET", "/v1/admin/employees", token=admin_token)
            assert isinstance(references, dict) and isinstance(employees, dict)
            maker_record = next(item for item in employees["items"] if item["email"] == MAKER_EMAIL)
            _request(
                base_url,
                "POST",
                "/v1/admin/role-assignments",
                token=admin_token,
                payload={
                    "target_user_id": maker_record["id"],
                    "role_slug": "maker",
                    "reason": "Phase 6C-A HTTP smoke grant",
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
            client = references["clients"][0]
            branch = references["branches"][0]
            job = _request(
                base_url,
                "POST",
                "/v1/jobs",
                token=admin_token,
                payload={
                    "reference": "PHASE6CA-HTTP-001",
                    "client_id": client["id"],
                    "branch_id": branch["id"],
                    "direction": "import",
                    "mode": "air",
                    "goods_description": "Initial disposable shipment",
                    "container_reference": None,
                },
            )
            assert isinstance(job, dict)
            _request(
                base_url,
                "PUT",
                f"/v1/admin/jobs/{job['id']}/assignment",
                token=admin_token,
                payload={
                    "responsibility": "maker",
                    "target_user_id": maker_record["id"],
                    "reason": "Phase 6C-A HTTP smoke assignment",
                },
            )

            maker_token = _login(base_url, MAKER_EMAIL, MAKER_PASSWORD)
            queue = _request(base_url, "GET", "/v1/my-work?limit=20", token=maker_token)
            detail = _request(base_url, "GET", f"/v1/jobs/{job['id']}", token=maker_token)
            responsibilities = _request(
                base_url,
                "GET",
                f"/v1/jobs/{job['id']}/responsibilities",
                token=maker_token,
            )
            assert isinstance(queue, dict) and queue["count"] == 1
            assert queue["items"][0]["job_id"] == job["id"]
            assert queue["items"][0]["client_name"] == client["name"]
            assert queue["items"][0]["branch_name"] == branch["name"]
            assert isinstance(detail, dict) and detail["client_name"] == client["name"]
            assert any(item["current_actor_responsible"] for item in responsibilities)

            updated = _request(
                base_url,
                "PATCH",
                f"/v1/jobs/{job['id']}",
                token=maker_token,
                payload={
                    "expected_version": detail["version"],
                    "goods_description": "Maker-updated disposable shipment",
                    "container_reference": "C6A-REF-1",
                },
            )
            assert isinstance(updated, dict)
            submitted = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/prepare",
                token=maker_token,
                payload={
                    "expected_version": updated["version"],
                    "checklist_data": None,
                    "justification": "",
                },
            )
            assert isinstance(submitted, dict)
            assert submitted["stage"] == "prepared" and submitted["maker_edit_locked"]
            post_submit_queue = _request(base_url, "GET", "/v1/my-work?limit=20", token=maker_token)
            assert isinstance(post_submit_queue, dict)
            assert post_submit_queue["count"] == 0
            edit_request = _request(
                base_url,
                "POST",
                f"/v1/jobs/{job['id']}/edit-requests",
                token=maker_token,
                payload={"reason": "Correct a submitted reference"},
            )
            notifications = _request(
                base_url, "GET", "/v1/notifications?limit=50", token=maker_token
            )
            unread = _request(base_url, "GET", "/v1/notifications/unread-count", token=maker_token)
            assert isinstance(edit_request, dict) and edit_request["status"] == "pending"
            assert isinstance(notifications, list) and notifications
            assert isinstance(unread, dict) and unread["count"] >= 1
            read = _request(
                base_url,
                "POST",
                f"/v1/notifications/{notifications[0]['id']}/read",
                token=maker_token,
            )
            assert isinstance(read, dict) and read["read_at"] is not None
            print(
                json.dumps(
                    {
                        "health": "ok",
                        "admin_authenticated": True,
                        "maker_authenticated": True,
                        "initial_queue_count": queue["count"],
                        "job_detail": True,
                        "responsibility_context": True,
                        "maker_update": True,
                        "maker_submission_locked": True,
                        "post_submit_queue_count": post_submit_queue["count"],
                        "edit_request_status": edit_request["status"],
                        "notifications_found": len(notifications),
                        "notification_marked_read": True,
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
