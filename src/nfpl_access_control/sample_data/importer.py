"""Atomic import of deterministic demo data into an empty migrated database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.orm import Session

from nfpl_access_control.authorization.roles import SYSTEM_ROLES
from nfpl_access_control.core.security import hash_password
from nfpl_access_control.db.base import Base
from nfpl_access_control.models import (
    AdminBootstrap,
    PasswordCredential,
    Role,
    RolePermission,
    UserKind,
)
from nfpl_access_control.models.base import UtcDateTime
from nfpl_access_control.sample_data.builder import Dataset

INSERT_ORDER = (
    "branches",
    "clients",
    "users",
    "account_state_events",
    "user_availability_events",
    "role_assignments",
    "role_assignment_events",
    "jobs",
    "job_responsibilities",
    "job_responsibility_events",
    "job_versions",
    "audit_events",
    "job_edit_requests",
    "exceptional_transition_requests",
    "absence_nominations",
    "job_delegations",
    "absence_nomination_jobs",
    "notifications",
)

EXPECTED_MIGRATION_HEAD = "20261017_0007"
BOOTSTRAP_KEY = "first-admin"


class SampleImportError(RuntimeError):
    """Raised when a database is unsafe or incompatible with sample import."""


@dataclass(frozen=True, slots=True)
class ImportResult:
    row_counts: dict[str, int]
    password_credentials: int
    admin_bootstraps: int

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values()) + self.password_credentials + self.admin_bootstraps


def _migration_revision(connection: object) -> str | None:
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        return None
    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def _assert_migrated(connection: object) -> None:
    revision = _migration_revision(connection)
    if revision != EXPECTED_MIGRATION_HEAD:
        raise SampleImportError(
            "The target must be migrated to the current Alembic head "
            f"{EXPECTED_MIGRATION_HEAD}; found {revision or 'no migration state'}."
        )
    expected_tables = set(Base.metadata.tables)
    actual_tables = set(inspect(connection).get_table_names())
    missing = expected_tables - actual_tables
    if missing:
        raise SampleImportError(f"The migrated schema is missing tables: {sorted(missing)}")


def _assert_system_roles(session: Session) -> None:
    roles = {role.slug: role for role in session.scalars(select(Role))}
    expected_slugs = {definition.slug for definition in SYSTEM_ROLES}
    unexpected_slugs = set(roles) - expected_slugs
    if unexpected_slugs:
        raise SampleImportError(
            "Refusing to seed a database containing application-defined roles: "
            + ", ".join(sorted(unexpected_slugs))
        )
    for definition in SYSTEM_ROLES:
        role = roles.get(definition.slug)
        if role is None or role.id != definition.id or not role.is_system:
            raise SampleImportError(f"System role {definition.slug!r} is missing or inconsistent.")
        permissions = {
            item
            for item in session.scalars(
                select(RolePermission.permission).where(RolePermission.role_id == role.id)
            )
        }
        if permissions != set(definition.permissions):
            raise SampleImportError(
                f"System role {definition.slug!r} has an inconsistent permission set."
            )


def _assert_empty(session: Session) -> None:
    populated: list[str] = []
    exempt = {"roles", "role_permissions", "alembic_version"}
    for table_name, table in Base.metadata.tables.items():
        if table_name in exempt:
            continue
        count = session.scalar(select(func.count()).select_from(table))
        if count:
            populated.append(table_name)
    if populated:
        raise SampleImportError(
            "Refusing to seed a non-empty database; populated tables: "
            + ", ".join(sorted(populated))
        )


def _coerce_rows(table_name: str, rows: list[dict]) -> list[dict]:
    table = Base.metadata.tables[table_name]
    expected = set(table.columns.keys())
    result: list[dict] = []
    for row in rows:
        actual = set(row)
        if actual != expected:
            raise SampleImportError(
                f"{table_name} row columns differ from the model; "
                f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
            )
        converted = dict(row)
        for column in table.columns:
            value = converted[column.name]
            if value is not None and isinstance(column.type, UtcDateTime):
                if not isinstance(value, str):
                    raise SampleImportError(
                        f"{table_name}.{column.name} must be an ISO-8601 string."
                    )
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise SampleImportError(
                        f"{table_name}.{column.name} must include a UTC offset."
                    )
                converted[column.name] = parsed
        result.append(converted)
    return result


def import_dataset(engine: Engine, dataset: Dataset, *, demo_password: str) -> ImportResult:
    """Import once, atomically, after validating migration and emptiness.

    The caller supplies the demo password through a secret channel. Only unique
    scrypt hashes are stored; plaintext is neither persisted nor returned.
    """

    if not 12 <= len(demo_password) <= 128:
        raise SampleImportError("NFPL_DEMO_PASSWORD must contain 12-128 characters.")
    unexpected = set(dataset.tables) - set(INSERT_ORDER)
    missing = set(INSERT_ORDER) - set(dataset.tables)
    if unexpected or missing:
        raise SampleImportError(
            f"Dataset table set is incompatible; missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )

    counts = {name: len(dataset.tables[name]) for name in INSERT_ORDER}
    with Session(engine) as session, session.begin():
        _assert_migrated(session.connection())
        _assert_system_roles(session)
        _assert_empty(session)

        for table_name in INSERT_ORDER:
            rows = _coerce_rows(table_name, dataset.tables[table_name])
            if rows:
                session.execute(Base.metadata.tables[table_name].insert(), rows)

        users = dataset.tables["users"]
        credential_count = 0
        for user in users:
            if user["kind"] == UserKind.SERVICE.value:
                continue
            session.add(
                PasswordCredential(
                    user_id=user["id"],
                    password_hash=hash_password(demo_password),
                    failed_attempts=0,
                    locked_until=None,
                    created_at=datetime.fromisoformat(user["created_at"]),
                    updated_at=datetime.fromisoformat(user["updated_at"]),
                )
            )
            credential_count += 1

        admin_id = next(user["id"] for user in users if user["email"] == "admin@nfpl.test")
        session.add(
            AdminBootstrap(
                key=BOOTSTRAP_KEY,
                user_id=admin_id,
                occurred_at=datetime.fromisoformat(
                    next(user["created_at"] for user in users if user["id"] == admin_id)
                ),
            )
        )
        session.flush()

        if engine.dialect.name == "sqlite":
            violations = session.execute(text("PRAGMA foreign_key_check")).all()
            if violations:
                raise SampleImportError(
                    f"SQLite foreign-key verification failed with {len(violations)} violation(s)."
                )

    return ImportResult(
        row_counts=counts,
        password_credentials=credential_count,
        admin_bootstraps=1,
    )
