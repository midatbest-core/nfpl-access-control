from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from nfpl_access_control.db.base import Base
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.models import (
    Branch,
    Client,
    Job,
    JobDirection,
    JobMode,
    JobStage,
    User,
    UserKind,
)


def _create_job(session: Session) -> Job:
    branch = Branch(code="KTM", name="Kathmandu")
    client = Client(code="ACME", name="Acme Imports")
    assignee = User(
        email="assignee@example.test",
        display_name="Assigned Staff",
        kind=UserKind.STAFF,
    )
    job = Job(
        reference="NFPL-0001",
        branch=branch,
        client=client,
        assignee=assignee,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
    )
    session.add(job)
    session.commit()
    return job


def test_job_defaults_and_enum_round_trip(session: Session) -> None:
    job = _create_job(session)
    session.expire_all()

    stored_job = session.scalar(select(Job).where(Job.id == job.id))

    assert stored_job is not None
    assert stored_job.stage is JobStage.CONFIRMED
    assert stored_job.direction is JobDirection.IMPORT
    assert stored_job.mode is JobMode.AIR
    assert stored_job.version == 1


def test_sqlite_foreign_keys_are_enforced(session: Session) -> None:
    job = Job(
        reference="NFPL-BAD-FK",
        client_id="missing-client",
        branch_id="missing-branch",
        direction=JobDirection.EXPORT,
        mode=JobMode.LCL,
    )
    session.add(job)

    with pytest.raises(IntegrityError):
        session.commit()


def test_naive_security_timestamp_is_rejected(session: Session, active_user: User) -> None:
    active_user.credentials[0].expires_at = datetime(2030, 1, 1)

    with pytest.raises((StatementError, ValueError)):
        session.commit()


def test_optimistic_version_rejects_stale_update(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'locking.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as setup_session:
        job_id = _create_job(setup_session).id

    with factory() as first_session, factory() as stale_session:
        first_job = first_session.get(Job, job_id)
        stale_job = stale_session.get(Job, job_id)
        assert first_job is not None and stale_job is not None

        first_job.reference = "NFPL-0001-A"
        first_session.commit()
        assert first_job.version == 2

        stale_job.reference = "NFPL-0001-B"
        with pytest.raises(StaleDataError):
            stale_session.commit()

    engine.dispose()
