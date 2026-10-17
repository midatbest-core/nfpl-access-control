"""Phase 7 deterministic generation, import, and API security verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from nfpl_access_control.api.dependencies import get_db
from nfpl_access_control.authorization import AuthorizationEngine
from nfpl_access_control.core.security import verify_password
from nfpl_access_control.db.base import Base
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.main import create_app
from nfpl_access_control.models import (
    Job,
    JobDelegation,
    JobResponsibility,
    JobStage,
    PasswordCredential,
    Permission,
    ResponsibilityType,
    Role,
    User,
)
from nfpl_access_control.sample_data.benchmark import (
    BENCHMARK_STREAMS,
    BenchmarkConfig,
    expected_counts,
)
from nfpl_access_control.sample_data.builder import DatasetBuilder, DatasetConfig
from nfpl_access_control.sample_data.importer import SampleImportError, import_dataset
from nfpl_access_control.sample_data.writers import (
    OutputSafetyError,
    prepare_output_dir,
    write_manifest,
    write_table_stream,
    write_tables,
)
from nfpl_access_control.services.history import HistoryService

DEMO_PASSWORD = "Phase7-Disposable-Test-Only!"


@pytest.fixture(scope="module")
def dataset():
    return DatasetBuilder(DatasetConfig()).build()


@pytest.fixture(scope="module")
def seeded_database(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("phase7") / "demo.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    engine = create_database_engine(database_url)
    result = import_dataset(engine, DatasetBuilder().build(), demo_password=DEMO_PASSWORD)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield engine, factory, result
    finally:
        engine.dispose()


def test_standard_dataset_has_required_counts_and_identities(dataset) -> None:
    assert len(dataset.tables["branches"]) == 5
    assert len(dataset.tables["clients"]) == 10
    assert len(dataset.tables["jobs"]) == 420
    operational = [
        user
        for user in dataset.tables["users"]
        if user["kind"] == "staff" and user["email"] != "admin@nfpl.test"
    ]
    assert len(operational) == 20
    assert len([user for user in dataset.tables["users"] if user["kind"] == "client"]) == 10
    assert len([user for user in dataset.tables["users"] if user["kind"] == "service"]) == 1
    assert {job["stage"] for job in dataset.tables["jobs"]} == {
        "confirmed",
        "prepared",
        "checked",
        "filed",
        "cancelled",
        "reopened",
    }


def test_builder_is_deterministic_and_rows_match_live_schema(dataset) -> None:
    rebuilt = DatasetBuilder(DatasetConfig()).build()
    assert json.dumps(dataset.tables, sort_keys=True) == json.dumps(rebuilt.tables, sort_keys=True)
    for table_name, rows in dataset.tables.items():
        assert set(rows[0]) == set(Base.metadata.tables[table_name].columns.keys())


def test_scopes_responsibilities_absence_and_history_edges_exist(dataset) -> None:
    assignments = dataset.tables["role_assignments"]
    role_ids = {
        assignment["role_id"]
        for assignment in assignments
        if assignment["user_id"] == dataset.tables["users"][1]["id"]
    }
    assert len(role_ids) >= 2
    assert any(item["revoked_at"] for item in assignments)
    assert any(item["valid_until"] for item in assignments)
    assert len(dataset.tables["job_responsibilities"]) == 420 * 3
    assert len(dataset.tables["job_responsibility_events"]) == 420 * 3
    assert len(dataset.tables["absence_nominations"]) == 3
    assert {item["outcome"] for item in dataset.tables["absence_nomination_jobs"]} == {
        "delegated",
        "ineligible",
        "conflict",
        "overridden",
    }
    assert dataset.tables["job_delegations"]
    assert len(dataset.tables["job_versions"]) > 420
    required_snapshot = {"client_id", "branch_id", "direction", "mode", "stage", "version"}
    assert all(required_snapshot <= set(row["snapshot"]) for row in dataset.tables["job_versions"])

    responsibilities = {
        (row["job_id"], row["responsibility"]): row["user_id"]
        for row in dataset.tables["job_responsibilities"]
    }
    approved = next(
        row for row in dataset.tables["absence_nominations"] if row["status"] == "approved"
    )
    outcomes = {row["outcome"]: row for row in dataset.tables["absence_nomination_jobs"]}
    for outcome in ("delegated", "ineligible", "conflict", "overridden"):
        row = outcomes[outcome]
        assert responsibilities[row["job_id"], "maker"] == approved["requester_user_id"]
    assert (
        responsibilities[outcomes["conflict"]["job_id"], "checker"]
        == outcomes["conflict"]["nominee_user_id"]
    )
    assert outcomes["ineligible"]["delegation_id"] is None
    assert outcomes["conflict"]["delegation_id"] is None
    assert outcomes["overridden"]["nominee_user_id"] != approved["nominee_user_id"]
    assert len(
        [
            event
            for event in dataset.tables["audit_events"]
            if event["action"] == "notification.created"
        ]
    ) == len(dataset.tables["notifications"])


def test_responsible_people_have_scoped_permission_and_no_self_check(
    seeded_database,
) -> None:
    _, factory, _ = seeded_database
    permission_by_responsibility = {
        ResponsibilityType.MAKER: Permission.JOB_PREPARE,
        ResponsibilityType.CHECKER: Permission.JOB_CHECK,
        ResponsibilityType.FILING_OFFICER: Permission.JOB_FILE,
    }
    with factory() as session:
        engine = AuthorizationEngine(session)
        rows = session.execute(
            select(JobResponsibility, Job, User)
            .join(Job, Job.id == JobResponsibility.job_id)
            .join(User, User.id == JobResponsibility.user_id)
        )
        for responsibility, job, user in rows:
            assert engine.authorize_job(
                user, permission_by_responsibility[responsibility.responsibility], job
            ).allowed
        conflicts = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.prepared_by_user_id.is_not(None),
                Job.prepared_by_user_id == Job.checked_by_user_id,
            )
        )
        assert conflicts == 0


def test_file_output_is_byte_deterministic_and_rerun_safe(tmp_path: Path, dataset) -> None:
    output = tmp_path / "generated"
    prepare_output_dir(output, force=False)
    write_tables(dataset.tables, output, fmt="json")
    counts = {name: len(rows) for name, rows in dataset.tables.items()}
    write_manifest(
        output,
        mode="standard",
        fmt="json",
        counts=counts,
        edge_cases=dataset.edge_cases,
    )
    first = {path.name: path.read_bytes() for path in output.iterdir()}
    prepare_output_dir(output, force=False)
    write_tables(dataset.tables, output, fmt="json")
    write_manifest(
        output,
        mode="standard",
        fmt="json",
        counts=counts,
        edge_cases=dataset.edge_cases,
    )
    assert first == {path.name: path.read_bytes() for path in output.iterdir()}

    unsafe = tmp_path / "unrelated"
    unsafe.mkdir()
    (unsafe / "keep.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(OutputSafetyError):
        prepare_output_dir(unsafe, force=False)


def test_benchmark_default_path_declares_500_users_and_200000_jobs(tmp_path: Path) -> None:
    full = BenchmarkConfig()
    counts = expected_counts(full)
    assert full.employees == 500
    assert full.jobs == 200_000
    assert counts["users"] == 501  # 500 operational employees plus benchmark Admin.
    assert counts["jobs"] == 200_000
    assert counts["job_responsibilities"] == 600_000

    small = BenchmarkConfig(branches=3, clients=5, employees=10, jobs=50)
    prepare_output_dir(tmp_path, force=False)
    measured = {
        table: write_table_stream(table, stream(small), tmp_path, fmt="ndjson")
        for table, stream in BENCHMARK_STREAMS.items()
    }
    assert measured == expected_counts(small)


def test_import_is_atomic_referentially_valid_and_refuses_rerun(
    seeded_database,
) -> None:
    engine, factory, result = seeded_database
    assert result.row_counts["jobs"] == 420
    assert result.password_credentials == 31
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 420
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []
        before = session.scalar(select(func.count()).select_from(User))
    with pytest.raises(SampleImportError, match="non-empty"):
        import_dataset(engine, DatasetBuilder().build(), demo_password=DEMO_PASSWORD)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == before


def test_demo_passwords_are_scrypt_hashed_and_never_shared_as_hashes(
    seeded_database,
) -> None:
    _, factory, _ = seeded_database
    with factory() as session:
        credentials = list(session.scalars(select(PasswordCredential)))
        assert len(credentials) == 31
        assert len({item.password_hash for item in credentials}) == 31
        assert all(item.password_hash != DEMO_PASSWORD for item in credentials)
        assert all(verify_password(DEMO_PASSWORD, item.password_hash) for item in credentials)


def _client(factory) -> TestClient:
    app = create_app()

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/v1/auth/login",
        json={"email": email, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_role_specific_api_access_and_client_isolation(seeded_database) -> None:
    _, factory, _ = seeded_database
    with factory() as session:
        admin_email = "admin@nfpl.test"
        own_job = session.scalar(
            select(Job).where(Job.client_id == DatasetBuilder().build().tables["clients"][0]["id"])
        )
        foreign_job = session.scalar(select(Job).where(Job.client_id != own_job.client_id))
        assert own_job is not None and foreign_job is not None
        samples = {}
        for responsibility, stage in (
            (ResponsibilityType.MAKER, JobStage.CONFIRMED),
            (ResponsibilityType.CHECKER, JobStage.PREPARED),
            (ResponsibilityType.FILING_OFFICER, JobStage.CHECKED),
        ):
            samples[responsibility] = session.execute(
                select(User.email, Job.id)
                .join(JobResponsibility, JobResponsibility.user_id == User.id)
                .join(Job, Job.id == JobResponsibility.job_id)
                .where(
                    JobResponsibility.responsibility == responsibility,
                    Job.stage == stage,
                )
                .limit(1)
            ).one()

    with _client(factory) as client:
        admin = _login(client, admin_email)
        assert client.get("/v1/admin/dashboard/overview", headers=admin).status_code == 200
        for email, job_id in samples.values():
            headers = _login(client, email)
            assert client.get("/v1/my-work", headers=headers).status_code == 200
            assert client.get(f"/v1/jobs/{job_id}", headers=headers).status_code == 200

        viewer = _login(client, "client-viewer-00@portal.test")
        assert client.get(f"/v1/client/jobs/{own_job.id}/status", headers=viewer).status_code == 200
        hidden = client.get(f"/v1/client/jobs/{foreign_job.id}/status", headers=viewer)
        assert hidden.status_code == 404
        assert own_job.reference not in hidden.text


def test_api_no_self_check_survives_adversarial_delegation(seeded_database) -> None:
    _, factory, _ = seeded_database
    now = datetime.now(UTC)
    with factory() as session:
        actor = session.scalar(select(User).where(User.email == "emp-03@nfpl.test"))
        job = session.scalar(
            select(Job).where(
                Job.stage == JobStage.PREPARED,
                Job.prepared_by_user_id == actor.id,
            )
        )
        assert actor is not None and job is not None
        checker = session.scalar(
            select(JobResponsibility).where(
                JobResponsibility.job_id == job.id,
                JobResponsibility.responsibility == ResponsibilityType.CHECKER,
            )
        )
        session.add(
            JobDelegation(
                job_id=job.id,
                responsibility=ResponsibilityType.CHECKER,
                delegator_user_id=checker.user_id,
                delegate_user_id=actor.id,
                valid_from=now - timedelta(minutes=1),
                valid_until=now + timedelta(minutes=5),
                created_by_user_id=checker.user_id,
                reason="Adversarial test fixture: delegation cannot bypass self-check.",
            )
        )
        session.commit()
        version = job.version
        job_id = job.id

    with _client(factory) as client:
        headers = _login(client, "emp-03@nfpl.test")
        response = client.post(
            f"/v1/jobs/{job_id}/check",
            headers=headers,
            json={"expected_version": version, "approved": True},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["reason_code"] == "self_check_forbidden"


def test_historical_eligibility_uses_complete_seed_evidence(seeded_database) -> None:
    _, factory, _ = seeded_database
    with factory() as session:
        job = session.scalar(select(Job).where(Job.stage == JobStage.PREPARED))
        version = HistoryService(session).state_at(job.id, job.updated_at)
        assert version is not None
        result = HistoryService(session).historical_eligibility(
            job_id=job.id,
            permission=Permission.JOB_CHECK,
            at=version.recorded_at,
        )
        assert result.complete
        assert result.candidates


def test_system_roles_remain_authoritative_after_import(seeded_database) -> None:
    _, factory, _ = seeded_database
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Role)) == 6
        assert not any(role.slug.startswith("sample") for role in session.scalars(select(Role)))
