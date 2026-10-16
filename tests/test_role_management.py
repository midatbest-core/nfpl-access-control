from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationEngine, ReasonCode, Scope
from nfpl_access_control.authorization.roles import ADMIN_ROLE, MAKER_ROLE
from nfpl_access_control.models import (
    AssignmentEventType,
    Branch,
    Client,
    Job,
    JobDirection,
    JobMode,
    Permission,
    Role,
    RoleAssignment,
    RoleAssignmentEvent,
    User,
    UserKind,
)
from nfpl_access_control.services.role_management import (
    RoleManagementError,
    RoleManagementService,
    RoleManagementValidationError,
)

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)


def _user(session: Session, email: str) -> User:
    user = User(email=email, display_name=email, kind=UserKind.STAFF)
    session.add(user)
    session.flush()
    return user


def _scope(client_id: str | None = None) -> Scope:
    return Scope(
        all_clients=client_id is None,
        client_id=client_id,
        all_branches=True,
        branch_id=None,
        all_directions=True,
        direction=None,
        all_modes=True,
        mode=None,
    )


def _bootstrap_admin(session: Session, *, client_id: str | None = None) -> User:
    admin = _user(session, f"admin-{client_id or 'global'}@example.test")
    role = session.scalar(select(Role).where(Role.slug == ADMIN_ROLE))
    assert role is not None
    scope = _scope(client_id)
    assignment = RoleAssignment(
        user_id=admin.id,
        role_id=role.id,
        client_id=scope.client_id,
        all_clients=scope.all_clients,
        branch_id=None,
        all_branches=True,
        direction=None,
        all_directions=True,
        mode=None,
        all_modes=True,
        valid_from=NOW - timedelta(days=1),
        granted_by_user_id=admin.id,
        grant_reason="trusted bootstrap fixture",
    )
    session.add(assignment)
    session.flush()
    return admin


def test_admin_grant_and_revoke_are_effective_and_append_history(
    session: Session,
) -> None:
    admin = _bootstrap_admin(session)
    target = _user(session, "target@example.test")
    client = Client(code="GRANT-C", name="Grant Client")
    branch = Branch(code="GRANT-B", name="Grant Branch")
    job = Job(
        reference="GRANT-JOB",
        client=client,
        branch=branch,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
    )
    session.add(job)
    session.flush()
    service = RoleManagementService(session)

    assignment = service.grant_role(
        actor=admin,
        target_user_id=target.id,
        role_slug=MAKER_ROLE,
        scope=_scope(client.id),
        reason="Cover client workload",
        now=NOW,
    )
    assert (
        AuthorizationEngine(session)
        .authorize_job(target, Permission.JOB_PREPARE, job, at=NOW)
        .allowed
    )

    revoked = service.revoke_role(
        actor=admin,
        assignment_id=assignment.id,
        reason="Responsibility changed",
        now=NOW + timedelta(hours=1),
    )
    decision = AuthorizationEngine(session).authorize_job(
        target, Permission.JOB_PREPARE, job, at=NOW + timedelta(hours=1)
    )

    assert decision.reason_code is ReasonCode.ACCESS_REVOKED
    assert revoked.version == 2
    events = list(
        session.scalars(
            select(RoleAssignmentEvent)
            .where(RoleAssignmentEvent.assignment_id == assignment.id)
            .order_by(RoleAssignmentEvent.occurred_at)
        )
    )
    assert [event.event_type for event in events] == [
        AssignmentEventType.GRANTED,
        AssignmentEventType.REVOKED,
    ]
    assert (
        AuthorizationEngine(session)
        .authorize_job(target, Permission.JOB_PREPARE, job, at=NOW + timedelta(minutes=30))
        .allowed
    )


def test_non_admin_cannot_grant_roles(session: Session) -> None:
    actor = _user(session, "ordinary@example.test")
    target = _user(session, "ordinary-target@example.test")

    with pytest.raises(RoleManagementError) as captured:
        RoleManagementService(session).grant_role(
            actor=actor,
            target_user_id=target.id,
            role_slug=MAKER_ROLE,
            scope=_scope(),
            reason="Unauthorized attempt",
            now=NOW,
        )

    assert captured.value.decision.reason_code is ReasonCode.ADMIN_REQUIRED


def test_admin_cannot_self_grant_or_directly_grant_admin(session: Session) -> None:
    admin = _bootstrap_admin(session)
    target = _user(session, "future-admin@example.test")
    service = RoleManagementService(session)

    with pytest.raises(RoleManagementError) as self_grant:
        service.grant_role(
            actor=admin,
            target_user_id=admin.id,
            role_slug=MAKER_ROLE,
            scope=_scope(),
            reason="Self escalation",
            now=NOW,
        )
    assert self_grant.value.decision.reason_code is ReasonCode.SELF_ESCALATION_FORBIDDEN

    with pytest.raises(RoleManagementError) as admin_grant:
        service.grant_role(
            actor=admin,
            target_user_id=target.id,
            role_slug=ADMIN_ROLE,
            scope=_scope(),
            reason="Bypass independent approval",
            now=NOW,
        )
    assert admin_grant.value.decision.reason_code is ReasonCode.SENSITIVE_APPROVAL_REQUIRED


def test_scoped_admin_cannot_grant_broader_or_other_client_scope(
    session: Session,
) -> None:
    client_a = Client(code="ADMIN-A", name="Admin A")
    client_b = Client(code="ADMIN-B", name="Admin B")
    session.add_all([client_a, client_b])
    session.flush()
    admin = _bootstrap_admin(session, client_id=client_a.id)
    target = _user(session, "scoped-target@example.test")
    service = RoleManagementService(session)

    allowed = service.grant_role(
        actor=admin,
        target_user_id=target.id,
        role_slug=MAKER_ROLE,
        scope=_scope(client_a.id),
        reason="Within scope",
        now=NOW,
    )
    assert allowed.client_id == client_a.id

    for forbidden_scope in (_scope(), _scope(client_b.id)):
        with pytest.raises(RoleManagementError) as captured:
            service.grant_role(
                actor=admin,
                target_user_id=target.id,
                role_slug=MAKER_ROLE,
                scope=forbidden_scope,
                reason="Outside scope",
                now=NOW,
            )
        assert captured.value.decision.reason_code is ReasonCode.ADMIN_REQUIRED


def test_custom_safe_role_works_without_code_change_but_cannot_manage_access(
    session: Session,
) -> None:
    admin = _bootstrap_admin(session)
    target = _user(session, "custom-role-user@example.test")
    client = Client(code="CUSTOM-C", name="Custom Client")
    branch = Branch(code="CUSTOM-B", name="Custom Branch")
    job = Job(
        reference="CUSTOM-JOB",
        client=client,
        branch=branch,
        direction=JobDirection.EXPORT,
        mode=JobMode.LCL,
    )
    session.add(job)
    session.flush()
    service = RoleManagementService(session)
    role = service.create_role(
        actor=admin,
        slug="quality-filer",
        name="Quality Filer",
        description="Can view and file scoped jobs.",
        permissions={Permission.JOB_VIEW, Permission.JOB_FILE},
    )
    assignment = service.grant_role(
        actor=admin,
        target_user_id=target.id,
        role_slug=role.slug,
        scope=_scope(client.id),
        reason="New operational role",
        now=NOW,
    )

    assert not role.is_system
    assert assignment.role_id == role.id
    assert (
        AuthorizationEngine(session).authorize_job(target, Permission.JOB_FILE, job, at=NOW).allowed
    )
    assert (
        not AuthorizationEngine(session)
        .authorize_job(target, Permission.JOB_CHECK, job, at=NOW)
        .allowed
    )

    with pytest.raises(RoleManagementValidationError):
        service.create_role(
            actor=admin,
            slug="shadow-admin",
            name="Shadow Admin",
            description="Must be rejected.",
            permissions={Permission.JOB_VIEW, Permission.ACCESS_GRANT},
        )


def test_future_and_expired_grants_remain_historical_records(session: Session) -> None:
    admin = _bootstrap_admin(session)
    target = _user(session, "timed-target@example.test")
    service = RoleManagementService(session)
    assignment = service.grant_role(
        actor=admin,
        target_user_id=target.id,
        role_slug=MAKER_ROLE,
        scope=_scope(),
        reason="Temporary cover",
        valid_from=NOW + timedelta(hours=1),
        valid_until=NOW + timedelta(hours=2),
        now=NOW,
    )
    role_count_before = session.scalar(select(func.count()).select_from(RoleAssignment))

    job_client = Client(code="TIMED-C", name="Timed Client")
    job_branch = Branch(code="TIMED-B", name="Timed Branch")
    job = Job(
        reference="TIMED-JOB",
        client=job_client,
        branch=job_branch,
        direction=JobDirection.IMPORT,
        mode=JobMode.FCL,
    )
    session.add(job)
    session.flush()
    engine = AuthorizationEngine(session)

    assert (
        engine.authorize_job(target, Permission.JOB_VIEW, job, at=NOW).reason_code
        is ReasonCode.ACCESS_NOT_YET_EFFECTIVE
    )
    assert engine.authorize_job(
        target, Permission.JOB_PREPARE, job, at=NOW + timedelta(hours=1)
    ).allowed
    assert (
        engine.authorize_job(
            target, Permission.JOB_PREPARE, job, at=NOW + timedelta(hours=2)
        ).reason_code
        is ReasonCode.ACCESS_EXPIRED
    )
    assert session.get(RoleAssignment, assignment.id) is assignment
    assert session.scalar(select(func.count()).select_from(RoleAssignment)) == role_count_before
