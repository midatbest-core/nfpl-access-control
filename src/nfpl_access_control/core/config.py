"""Application configuration loaded from process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_DATABASE_URL = "sqlite:///./nfpl.db"


def normalize_database_url(database_url: str) -> str:
    """Select psycopg 3 for provider-issued PostgreSQL URLs."""

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def parse_cors_origins(raw_origins: str) -> tuple[str, ...]:
    """Parse explicit browser origins; wildcard origins are never accepted."""

    origins: list[str] = []
    for raw_origin in raw_origins.split(","):
        origin = raw_origin.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or origin == "*"
        ):
            raise ValueError("NFPL_CORS_ALLOWED_ORIGINS must contain valid explicit origins")
        origins.append(origin)
    return tuple(dict.fromkeys(origins))


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings.

    A small dependency-free settings object keeps Phase 1 configuration explicit.
    Production deployments should inject the database URL from a secret manager.
    """

    database_url: str = DEFAULT_DATABASE_URL
    sql_echo: bool = False
    cors_allowed_origins: tuple[str, ...] = ()

    @classmethod
    def from_environment(cls) -> Settings:
        raw_echo = os.getenv("NFPL_SQL_ECHO", "false").strip().lower()
        if raw_echo not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("NFPL_SQL_ECHO must be a boolean value")

        raw_database_url = os.getenv("DATABASE_URL")
        if raw_database_url is None:
            raw_database_url = os.getenv("NFPL_DATABASE_URL", DEFAULT_DATABASE_URL)
        if not raw_database_url.strip():
            raise ValueError("DATABASE_URL must not be empty")

        return cls(
            database_url=normalize_database_url(raw_database_url.strip()),
            sql_echo=raw_echo in {"true", "1", "yes"},
            cors_allowed_origins=parse_cors_origins(os.getenv("NFPL_CORS_ALLOWED_ORIGINS", "")),
        )


settings = Settings.from_environment()
