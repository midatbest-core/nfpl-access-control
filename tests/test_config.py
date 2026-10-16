import pytest

from nfpl_access_control.core.config import (
    DEFAULT_DATABASE_URL,
    Settings,
    parse_cors_origins,
)
from nfpl_access_control.db.session import create_database_engine


def test_database_url_defaults_to_local_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NFPL_DATABASE_URL", raising=False)

    assert Settings.from_environment().database_url == DEFAULT_DATABASE_URL


def test_database_url_takes_precedence_over_legacy_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///canonical.db")
    monkeypatch.setenv("NFPL_DATABASE_URL", "sqlite:///legacy.db")

    assert Settings.from_environment().database_url == "sqlite:///canonical.db"


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_provider_postgres_url_selects_psycopg_driver(
    monkeypatch: pytest.MonkeyPatch, scheme: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{scheme}user:secret@db.example/nfpl?sslmode=require")

    assert Settings.from_environment().database_url.startswith("postgresql+psycopg://")


def test_empty_database_url_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", " ")

    with pytest.raises(ValueError, match="must not be empty"):
        Settings.from_environment()


def test_invalid_sql_echo_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFPL_SQL_ECHO", "sometimes")

    with pytest.raises(ValueError, match="must be a boolean"):
        Settings.from_environment()


def test_cors_origins_are_explicit_normalized_and_deduplicated() -> None:
    origins = parse_cors_origins(
        "https://nfpl.vercel.app/, http://localhost:3000, https://nfpl.vercel.app"
    )

    assert origins == ("https://nfpl.vercel.app", "http://localhost:3000")


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "javascript:alert(1)",
        "https://user:password@example.test",
        "https://example.test/path",
    ],
)
def test_invalid_or_overbroad_cors_origin_fails_closed(origin: str) -> None:
    with pytest.raises(ValueError, match="valid explicit origins"):
        parse_cors_origins(origin)


def test_postgres_engine_uses_psycopg_and_a_small_bounded_pool() -> None:
    engine = create_database_engine(
        "postgresql+psycopg://user:password@localhost/nfpl?sslmode=require"
    )
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.pool.size() == 5  # type: ignore[attr-defined]
        assert engine.pool._max_overflow == 0  # type: ignore[attr-defined]
    finally:
        engine.dispose()
