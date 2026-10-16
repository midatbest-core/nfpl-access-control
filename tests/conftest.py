from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from nfpl_access_control.api.dependencies import get_db
from nfpl_access_control.authorization.roles import install_system_roles
from nfpl_access_control.core.security import hash_api_token
from nfpl_access_control.db.base import Base
from nfpl_access_control.db.session import create_database_engine
from nfpl_access_control.main import create_app
from nfpl_access_control.models import ApiCredential, User, UserKind

TEST_TOKEN = "nfpl_test-token-never-use-in-production"


@pytest.fixture
def session_factory(tmp_path: Path) -> Generator[sessionmaker[Session], None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as seed_session:
        install_system_roles(seed_session)
        seed_session.commit()
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    with session_factory() as database_session:
        yield database_session


@pytest.fixture
def active_user(session: Session) -> User:
    user = User(
        email="maker@example.test",
        display_name="Phase One Maker",
        kind=UserKind.STAFF,
    )
    user.credentials.append(
        ApiCredential(
            name="test credential",
            token_hash=hash_api_token(TEST_TOKEN),
        )
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def api_client(
    session_factory: sessionmaker[Session], active_user: User
) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as database_session:
            yield database_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
