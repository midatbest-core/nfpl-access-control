"""Run a disposable real-HTTP smoke test for the Phase 6B Admin APIs."""

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
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.models import AccountStatus, Client, User, UserKind
from nfpl_access_control.services.bootstrap import bootstrap_first_admin

ROOT = Path(__file__).resolve().parents[1]
EMAIL = "phase6b-admin@example.test"
PASSWORD = "Phase6B Smoke Password 42!"


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
            result = _request(base_url, "GET", "/health")
            if result == {"status": "ok"}:
                return
        except (HTTPError, URLError):
            time.sleep(0.1)
    raise RuntimeError("Uvicorn did not become healthy.")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nfpl-phase6b-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'smoke.db'}"
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["database_url"] = database_url
        command.upgrade(config, "head")

        engine = create_database_engine(database_url)
        with Session(engine) as session:
            admin = bootstrap_first_admin(
                session,
                display_name="Phase 6B Admin",
                email=EMAIL,
                password=PASSWORD,
                branch_code="SMK",
                branch_name="Smoke Branch",
            )
            session.flush()
            session.add(Client(code="SMK", name="Smoke Client"))
            session.add(
                User(
                    email="phase6b-employee@example.test",
                    display_name="Phase 6B Employee",
                    kind=UserKind.STAFF,
                    branch_id=admin.branch_id,
                    account_status=AccountStatus.ACTIVE,
                    is_active=True,
                )
            )
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
            login = _request(
                base_url,
                "POST",
                "/v1/auth/login",
                payload={"email": EMAIL, "password": PASSWORD},
            )
            assert isinstance(login, dict)
            token = str(login["access_token"])
            references = _request(base_url, "GET", "/v1/admin/reference-data", token=token)
            overview = _request(base_url, "GET", "/v1/admin/dashboard/overview", token=token)
            employees = _request(base_url, "GET", "/v1/admin/employees", token=token)
            assert isinstance(references, dict) and isinstance(employees, dict)
            target = next(
                item
                for item in employees["items"]
                if item["email"] == "phase6b-employee@example.test"
            )
            grant = _request(
                base_url,
                "POST",
                "/v1/admin/role-assignments",
                token=token,
                payload={
                    "target_user_id": target["id"],
                    "role_slug": "maker",
                    "reason": "Phase 6B HTTP smoke grant",
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
            assert isinstance(grant, dict)
            client = references["clients"][0]
            branch = references["branches"][0]
            job = _request(
                base_url,
                "POST",
                "/v1/jobs",
                token=token,
                payload={
                    "reference": "PHASE6B-HTTP-001",
                    "client_id": client["id"],
                    "branch_id": branch["id"],
                    "direction": "import",
                    "mode": "air",
                    "goods_description": "Disposable HTTP smoke shipment",
                    "container_reference": None,
                },
            )
            assert isinstance(job, dict)
            retrieved = _request(base_url, "GET", f"/v1/jobs/{job['id']}", token=token)
            suggestions = _request(
                base_url,
                "GET",
                f"/v1/admin/jobs/{job['id']}/assignment-suggestions",
                token=token,
            )
            audit = _request(
                base_url,
                "GET",
                f"/v1/admin/jobs/{job['id']}/audit",
                token=token,
            )
            urgent = _request(
                base_url,
                "GET",
                "/v1/admin/dashboard/urgent-requests",
                token=token,
            )
            revoked = _request(
                base_url,
                "POST",
                f"/v1/admin/role-assignments/{grant['id']}/revoke",
                token=token,
                payload={"reason": "Phase 6B HTTP smoke cleanup"},
            )
            assert isinstance(retrieved, dict) and retrieved["id"] == job["id"]
            assert isinstance(suggestions, dict) and "maker" in suggestions
            assert isinstance(audit, list) and any(
                item["action"] == "job.created" for item in audit
            )
            assert isinstance(urgent, list)
            assert isinstance(revoked, dict) and revoked["revoked_at"] is not None
            print(
                json.dumps(
                    {
                        "health": "ok",
                        "authenticated": True,
                        "clients": len(references["clients"]),
                        "branches": len(references["branches"]),
                        "employees": len(employees["items"]),
                        "dashboard_total_jobs_before_create": overview["total_jobs"],
                        "created_job_id": job["id"],
                        "suggestion_groups": sorted(suggestions),
                        "audit_events": len(audit),
                        "urgent_requests": len(urgent),
                        "role_grant_revoked": True,
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
