from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization.roles import ADMIN_ROLE
from nfpl_access_control.core.security import hash_api_token, verify_password
from nfpl_access_control.models import (
    AccountStateEvent,
    AccountStatus,
    AdminBootstrap,
    ApiCredential,
    AuditEvent,
    Branch,
    EmployeeAvailability,
    PasswordCredential,
    Role,
    RoleAssignment,
    User,
    UserKind,
)
from nfpl_access_control.services.authentication import (
    LOGIN_FAILURE_LIMIT,
    AuthenticationError,
    EmployeeAuthenticationService,
)
from nfpl_access_control.services.bootstrap import BootstrapError, bootstrap_first_admin
from tests.conftest import TEST_TOKEN

PASSWORD = "StrongPassword42"


def _admin_role(session: Session, user: User) -> None:
    role = session.scalar(select(Role).where(Role.slug == ADMIN_ROLE))
    assert role is not None
    session.add(
        RoleAssignment(
            user_id=user.id,
            role_id=role.id,
            client_id=None,
            all_clients=True,
            branch_id=None,
            all_branches=True,
            direction=None,
            all_directions=True,
            mode=None,
            all_modes=True,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            valid_until=None,
            granted_by_user_id=user.id,
            grant_reason="trusted Phase 5A test bootstrap",
        )
    )
    session.commit()


def _register(api_client: TestClient, branch: Branch, email: str = "new@example.test"):
    return api_client.post(
        "/v1/auth/register",
        json={
            "name": "New Employee",
            "email": email,
            "password": PASSWORD,
            "branch_id": branch.id,
        },
    )


def test_registration_is_pending_unique_and_stores_secure_password(
    api_client: TestClient,
    session: Session,
) -> None:
    branch = Branch(code="REG-BR", name="Registration Branch")
    session.add(branch)
    session.commit()

    response = _register(api_client, branch)
    assert response.status_code == 201
    assert response.json()["account_status"] == AccountStatus.PENDING.value
    assert "password" not in response.json()
    user = session.scalar(select(User).where(User.email == "new@example.test"))
    assert user is not None
    credential = session.get(PasswordCredential, user.id)
    assert credential is not None
    assert credential.password_hash != PASSWORD
    assert PASSWORD not in credential.password_hash
    assert verify_password(PASSWORD, credential.password_hash)
    assert not user.is_active
    assert not user.role_assignments

    duplicate = _register(api_client, branch, email="NEW@example.test")
    assert duplicate.status_code == 409
    denied = api_client.post(
        "/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Account is not active."}


def test_admin_approval_login_logout_and_disable_revoke_sessions(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    _admin_role(session, active_user)
    branch = Branch(code="LIFE-BR", name="Lifecycle Branch")
    session.add(branch)
    session.commit()
    registered = _register(api_client, branch, email="lifecycle@example.test")
    employee_id = registered.json()["id"]
    admin_headers = {"Authorization": f"Bearer {TEST_TOKEN}"}

    approved = api_client.post(
        f"/v1/admin/employees/{employee_id}/approve",
        headers=admin_headers,
        json={"reason": "Employment verified"},
    )
    assert approved.status_code == 200
    assert approved.json()["account_status"] == AccountStatus.ACTIVE.value
    assert "password_hash" not in approved.text
    assert "token_hash" not in approved.text

    login = api_client.post(
        "/v1/auth/login",
        json={"email": "lifecycle@example.test", "password": PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token.startswith("nfpl_")
    assert login.json()["expires_at"]
    employee_headers = {"Authorization": f"Bearer {token}"}
    profile = api_client.get("/v1/employees/me", headers=employee_headers)
    assert profile.status_code == 200
    assert profile.json()["id"] == employee_id
    assert "password_hash" not in profile.text
    assert "token_hash" not in profile.text

    logout = api_client.post("/v1/auth/logout", headers=employee_headers)
    assert logout.status_code == 204
    assert api_client.get("/v1/employees/me", headers=employee_headers).status_code == 401

    second_login = api_client.post(
        "/v1/auth/login",
        json={"email": "lifecycle@example.test", "password": PASSWORD},
    )
    second_token = second_login.json()["access_token"]
    deactivated = api_client.post(
        f"/v1/admin/employees/{employee_id}/deactivate",
        headers=admin_headers,
        json={"reason": "Employment ended"},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["account_status"] == AccountStatus.DISABLED.value
    assert (
        api_client.get(
            "/v1/employees/me",
            headers={"Authorization": f"Bearer {second_token}"},
        ).status_code
        == 401
    )

    session.expire_all()
    employee = session.get(User, employee_id)
    assert employee is not None and not employee.is_active
    assert all(item.revoked_at is not None for item in employee.credentials)
    events = list(
        session.scalars(
            select(AccountStateEvent)
            .where(AccountStateEvent.user_id == employee_id)
            .order_by(AccountStateEvent.effective_at)
        )
    )
    assert [item.status for item in events] == [
        AccountStatus.PENDING,
        AccountStatus.ACTIVE,
        AccountStatus.DISABLED,
    ]


def test_non_admin_cannot_list_or_view_another_employee(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    other = User(
        email="private@example.test",
        display_name="Private Employee",
        kind=active_user.kind,
        branch_id=active_user.branch_id,
    )
    session.add(other)
    session.commit()
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}

    listing = api_client.get("/v1/admin/employees", headers=headers)
    profile = api_client.get(f"/v1/admin/employees/{other.id}", headers=headers)
    missing_transition = api_client.post(
        "/v1/admin/employees/not-a-real-id/deactivate",
        headers=headers,
        json={"reason": "Attempted lookup"},
    )
    assert listing.status_code == 403
    assert profile.status_code == 403
    assert missing_transition.status_code == 403
    assert "private@example.test" not in listing.text
    assert "private@example.test" not in profile.text


def test_admin_directory_search_pagination_roles_and_workload(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    _admin_role(session, active_user)
    employee = User(
        email="directory@example.test",
        display_name="Directory Match",
        kind=active_user.kind,
    )
    session.add(employee)
    session.commit()

    response = api_client.get(
        "/v1/admin/employees",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        params={"search": "directory", "page": 1, "limit": 10},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["id"] == employee.id
    assert item["pending_workload"] == 0
    assert item["roles"] == []


def test_first_admin_bootstrap_is_one_time_and_never_stores_plaintext(
    session: Session,
) -> None:
    admin = bootstrap_first_admin(
        session,
        display_name="First Admin",
        email="first-admin@example.test",
        password=PASSWORD,
        branch_code="HQ",
        branch_name="Head Office",
    )
    session.commit()
    credential = session.get(PasswordCredential, admin.id)
    assert credential is not None and verify_password(PASSWORD, credential.password_hash)
    assert PASSWORD not in credential.password_hash
    marker = session.get(AdminBootstrap, "first_admin")
    assert marker is not None and marker.user_id == admin.id
    assignment = session.scalar(select(RoleAssignment).where(RoleAssignment.user_id == admin.id))
    assert assignment is not None and assignment.all_clients and assignment.all_branches

    with pytest.raises(BootstrapError, match="already been used"):
        bootstrap_first_admin(
            session,
            display_name="Second Admin",
            email="second-admin@example.test",
            password=PASSWORD,
            branch_code="HQ",
            branch_name="Head Office",
        )
    session.rollback()
    assert not session.scalar(select(User.id).where(User.email == "second-admin@example.test"))


def test_first_admin_bootstrap_refuses_an_existing_admin_assignment(
    session: Session,
) -> None:
    existing = User(
        email="existing-admin@example.test",
        display_name="Existing Admin",
        kind=UserKind.STAFF,
    )
    session.add(existing)
    session.flush()
    _admin_role(session, existing)

    with pytest.raises(BootstrapError, match="Admin assignment already exists"):
        bootstrap_first_admin(
            session,
            display_name="Replacement Admin",
            email="replacement-admin@example.test",
            password=PASSWORD,
            branch_code="REPL",
            branch_name="Replacement Branch",
        )


def test_employee_updates_own_availability_with_append_only_audit(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    response = api_client.patch(
        "/v1/employees/me/availability",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={"availability": "busy", "reason": "Working on an urgent filing"},
    )
    assert response.status_code == 200
    assert response.json()["availability"] == EmployeeAvailability.BUSY.value
    session.expire_all()
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.actor_user_id == active_user.id,
            AuditEvent.action == "employee.availability_changed",
        )
    )
    assert audit is not None
    assert audit.authorization_context["self_service"] is True


def test_database_backed_login_lockout_expires_without_background_worker(
    session: Session,
) -> None:
    branch = Branch(code="LOCK-BR", name="Lockout Branch")
    session.add(branch)
    session.flush()
    service = EmployeeAuthenticationService(session)
    start = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)
    user = service.register(
        display_name="Lockout Employee",
        email="lockout@example.test",
        password=PASSWORD,
        branch_id=branch.id,
        now=start,
    )
    user.account_status = AccountStatus.ACTIVE
    user.is_active = True
    session.flush()

    for index in range(LOGIN_FAILURE_LIMIT):
        with pytest.raises(AuthenticationError):
            service.login(
                email=user.email,
                password="WrongPassword99",
                now=start + timedelta(seconds=index),
            )
    with pytest.raises(AuthenticationError):
        service.login(email=user.email, password=PASSWORD, now=start + timedelta(minutes=1))
    result = service.login(email=user.email, password=PASSWORD, now=start + timedelta(minutes=16))
    assert result.user.id == user.id
    assert session.scalar(
        select(ApiCredential).where(ApiCredential.token_hash == hash_api_token(result.token))
    )


def test_account_state_events_are_append_only(session: Session) -> None:
    branch = Branch(code="IMM-BR", name="Immutable Branch")
    session.add(branch)
    session.flush()
    user = EmployeeAuthenticationService(session).register(
        display_name="Immutable Employee",
        email="immutable-account@example.test",
        password=PASSWORD,
        branch_id=branch.id,
    )
    session.commit()
    event = session.scalar(select(AccountStateEvent).where(AccountStateEvent.user_id == user.id))
    assert event is not None
    session.delete(event)
    with pytest.raises(RuntimeError, match="append-only"):
        session.flush()
