"""Run real HTTP checks against a disposable migrated Phase 7 demo database."""

from __future__ import annotations

import gc
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from alembic import command
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.models import (
    Job,
    JobDelegation,
    JobResponsibility,
    JobStage,
    ResponsibilityType,
    User,
)
from nfpl_access_control.sample_data.builder import DatasetBuilder
from nfpl_access_control.sample_data.importer import import_dataset

ROOT = Path(__file__).resolve().parents[1]


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
    with urlopen(request, timeout=15) as response:
        if response.status == 204:
            return None
        return json.loads(response.read())


def _wait_for_health(base_url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(60):
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


def _responsible_sample(
    session: Session,
    responsibility: ResponsibilityType,
    stage: JobStage,
    *,
    excluded_emails: set[str] | None = None,
) -> tuple[str, str, int]:
    rows = session.execute(
        select(User.email, Job.id, Job.version)
        .join(JobResponsibility, JobResponsibility.user_id == User.id)
        .join(Job, Job.id == JobResponsibility.job_id)
        .where(
            JobResponsibility.responsibility == responsibility,
            Job.stage == stage,
        )
    )
    excluded = excluded_emails or set()
    return next(row for row in rows if row.email not in excluded)


def main() -> int:
    password = "Smoke-" + secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="nfpl-phase7-") as directory:
        database_url = f"sqlite:///{(Path(directory) / 'demo.db').as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["database_url"] = database_url
        command.upgrade(config, "head")
        engine = create_database_engine(database_url)
        import_dataset(engine, DatasetBuilder().build(), demo_password=password)

        now = datetime.now(UTC)
        with Session(engine) as session:
            maker = _responsible_sample(
                session,
                ResponsibilityType.MAKER,
                JobStage.CONFIRMED,
                excluded_emails={"emp-00@nfpl.test"},
            )
            checker = _responsible_sample(session, ResponsibilityType.CHECKER, JobStage.PREPARED)
            filer = _responsible_sample(
                session, ResponsibilityType.FILING_OFFICER, JobStage.CHECKED
            )
            self_actor = session.scalar(select(User).where(User.email == "emp-03@nfpl.test"))
            self_job = session.scalar(
                select(Job).where(
                    Job.stage == JobStage.PREPARED,
                    Job.prepared_by_user_id == self_actor.id,
                )
            )
            current_checker = session.scalar(
                select(JobResponsibility).where(
                    JobResponsibility.job_id == self_job.id,
                    JobResponsibility.responsibility == ResponsibilityType.CHECKER,
                )
            )
            session.add(
                JobDelegation(
                    job_id=self_job.id,
                    responsibility=ResponsibilityType.CHECKER,
                    delegator_user_id=current_checker.user_id,
                    delegate_user_id=self_actor.id,
                    valid_from=now - timedelta(minutes=1),
                    valid_until=now + timedelta(minutes=10),
                    created_by_user_id=current_checker.user_id,
                    reason="Adversarial smoke fixture; self-check must still be denied.",
                )
            )
            own_job = session.scalar(
                select(Job).where(
                    Job.client_id == DatasetBuilder().build().tables["clients"][0]["id"]
                )
            )
            foreign_job = session.scalar(select(Job).where(Job.client_id != own_job.client_id))
            self_job_id, self_job_version = self_job.id, self_job.version
            own_job_id, foreign_job_id = own_job.id, foreign_job.id
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
            admin_token = _login(base_url, "admin@nfpl.test", password)
            overview = _request(base_url, "GET", "/v1/admin/dashboard/overview", token=admin_token)

            maker_token = _login(base_url, maker.email, password)
            maker_result = _request(
                base_url,
                "PATCH",
                f"/v1/jobs/{maker.id}",
                token=maker_token,
                payload={
                    "expected_version": maker.version,
                    "goods_description": "Phase 7 real-HTTP Maker update.",
                },
            )

            checker_token = _login(base_url, checker.email, password)
            checker_result = _request(
                base_url,
                "POST",
                f"/v1/jobs/{checker.id}/check",
                token=checker_token,
                payload={"expected_version": checker.version, "approved": True},
            )

            filer_token = _login(base_url, filer.email, password)
            filer_result = _request(
                base_url,
                "POST",
                f"/v1/jobs/{filer.id}/file",
                token=filer_token,
                payload={"expected_version": filer.version},
            )

            self_token = _login(base_url, "emp-03@nfpl.test", password)
            try:
                _request(
                    base_url,
                    "POST",
                    f"/v1/jobs/{self_job_id}/check",
                    token=self_token,
                    payload={"expected_version": self_job_version, "approved": True},
                )
            except HTTPError as error:
                self_denial = json.loads(error.read())["detail"]["reason_code"]
                assert error.code == 403 and self_denial == "self_check_forbidden"
            else:
                raise AssertionError("Adversarial self-check unexpectedly succeeded.")

            viewer_token = _login(base_url, "client-viewer-00@portal.test", password)
            own_status = _request(
                base_url,
                "GET",
                f"/v1/client/jobs/{own_job_id}/status",
                token=viewer_token,
            )
            try:
                _request(
                    base_url,
                    "GET",
                    f"/v1/client/jobs/{foreign_job_id}/status",
                    token=viewer_token,
                )
            except HTTPError as error:
                assert error.code == 404
                cross_client = "hidden"
            else:
                raise AssertionError("Cross-client shipment unexpectedly succeeded.")

            # The dashboard intentionally excludes the 42 archived demo jobs.
            assert isinstance(overview, dict) and overview["total_jobs"] == 378
            assert isinstance(maker_result, dict) and maker_result["version"] == maker.version + 1
            assert isinstance(checker_result, dict) and checker_result["stage"] == "checked"
            assert isinstance(filer_result, dict) and filer_result["stage"] == "filed"
            assert isinstance(own_status, dict)
            print(
                json.dumps(
                    {
                        "health": "ok",
                        "admin_non_archived_jobs": overview["total_jobs"],
                        "maker_update": "allowed",
                        "checker_verification": checker_result["stage"],
                        "filing": filer_result["stage"],
                        "self_check": "denied",
                        "cross_client": cross_client,
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
            time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(main())
