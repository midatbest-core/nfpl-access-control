from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_initial_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite:///{database_path}"

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    expected_tables = {
        "users",
        "api_credentials",
        "branches",
        "clients",
        "jobs",
        "roles",
        "role_permissions",
        "role_assignments",
        "role_assignment_events",
        "job_responsibilities",
        "job_responsibility_events",
        "job_delegations",
        "exceptional_transition_requests",
        "audit_events",
        "job_versions",
        "user_availability_events",
        "password_credentials",
        "account_state_events",
        "admin_bootstraps",
        "job_edit_requests",
    }
    assert expected_tables.issubset(set(inspector.get_table_names()))
    assert {
        "ix_jobs_scope_stage_id",
        "ix_jobs_assignee_stage_id",
    }.issubset({index["name"] for index in inspector.get_indexes("jobs")})
    with engine.connect() as connection:
        role_count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM roles WHERE is_system = 1"
        ).scalar_one()
        permission_count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM role_permissions"
        ).scalar_one()
        assert role_count == 6
        assert permission_count == 23

    command.downgrade(config, "base")
    inspector = inspect(engine)
    assert not expected_tables.intersection(inspector.get_table_names())
    engine.dispose()


def test_employee_account_migration_normalizes_existing_email(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-email.db"
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite:///{database_path}"
    command.upgrade(config, "20261017_0004")
    engine = create_engine(f"sqlite:///{database_path}")
    now = datetime.now(UTC).isoformat()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO users "
            "(email, display_name, kind, is_active, id, created_at, updated_at, availability) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "Legacy.Employee@Example.Test",
                "Legacy Employee",
                "staff",
                1,
                "legacy-email-user",
                now,
                now,
                "available",
            ),
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        email = connection.exec_driver_sql(
            "SELECT email FROM users WHERE id = 'legacy-email-user'"
        ).scalar_one()
    assert email == "legacy.employee@example.test"
    engine.dispose()
