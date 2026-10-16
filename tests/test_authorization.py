from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationEngine, ReasonCode, Scope
from nfpl_access_control.authorization.roles import (
    CHECKER_ROLE,
    CLIENT_VIEWER_ROLE,
    MAKER_ROLE,
    PARSER_SERVICE_ROLE,
)
from nfpl_access_control.models import (
    Branch,
    Client,
    Job,
    JobDirection,
    JobMode,
    Permission,
    Role,
    RoleAssignment,
    User,
    UserKind,
)

NOW = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)


def _user(session: Session, email: str, *, kind: UserKind = UserKind.STAFF) -> User:
    user = User(email=email, display_name=email.split("@")[0], kind=kind)
    session.add(user)
    session.flush()
    return user


def _scope(
    *,
    client_id: str | None = None,
    branch_id: str | None = None,
    direction: JobDirection | None = None,
    mode: JobMode | None = None,
) -> Scope:
    return Scope(
        all_clients=client_id is None,
        client_id=client_id,
        all_branches=branch_id is None,
        branch_id=branch_id,
        all_directions=direction is None,
        direction=direction,
        all_modes=mode is None,
        mode=mode,
    )


def _assignment(
    session: Session,
    *,
    user: User,
    role_slug: str,
    grantor: User,
    scope: Scope,
    valid_from: datetime = NOW - timedelta(days=1),
    valid_until: datetime | None = None,
    revoked_at: datetime | None = None,
) -> RoleAssignment:
    role = session.scalar(select(Role).where(Role.slug == role_slug))
    assert role is not None
    assignment = RoleAssignment(
        user_id=user.id,
        role_id=role.id,
        client_id=scope.client_id,
        all_clients=scope.all_clients,
        branch_id=scope.branch_id,
        all_branches=scope.all_branches,
        direction=scope.direction,
        all_directions=scope.all_directions,
        mode=scope.mode,
        all_modes=scope.all_modes,
        valid_from=valid_from,
        valid_until=valid_until,
        revoked_at=revoked_at,
        granted_by_user_id=grantor.id,
        grant_reason="test setup",
    )
    session.add(assignment)
    session.flush()
    return assignment


def _jobs(session: Session) -> tuple[Job, Job, Client, Client, Branch, Branch]:
    client_a = Client(code="CLIENT-A", name="Client A")
    client_b = Client(code="CLIENT-B", name="Client B")
    branch_a = Branch(code="BR-A", name="Branch A")
    branch_b = Branch(code="BR-B", name="Branch B")
    job_a = Job(
        reference="AUTH-A",
        client=client_a,
        branch=branch_a,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
    )
    job_b = Job(
        reference="AUTH-B",
        client=client_b,
        branch=branch_b,
        direction=JobDirection.EXPORT,
        mode=JobMode.FCL,
    )
    session.add_all([job_a, job_b])
    session.flush()
    return job_a, job_b, client_a, client_b, branch_a, branch_b


def test_visibility_is_separate_from_action_permission(session: Session) -> None:
    actor = _user(session, "viewer@example.test", kind=UserKind.CLIENT)
    grantor = _user(session, "grantor@example.test")
    job, _, client, _, _, _ = _jobs(session)
    _assignment(
        session,
        user=actor,
        role_slug=CLIENT_VIEWER_ROLE,
        grantor=grantor,
        scope=_scope(client_id=client.id),
    )

    engine = AuthorizationEngine(session)
    visible = engine.authorize_job(actor, Permission.JOB_VIEW, job, at=NOW)
    prepare = engine.authorize_job(actor, Permission.JOB_PREPARE, job, at=NOW)

    assert visible.allowed
    assert not prepare.allowed
    assert prepare.reason_code is ReasonCode.MISSING_PERMISSION


def test_overlapping_global_maker_and_restricted_checker_assignments(
    session: Session,
) -> None:
    actor = _user(session, "overlap@example.test")
    grantor = _user(session, "grantor-overlap@example.test")
    job_a, job_b, client_a, _, _, _ = _jobs(session)
    _assignment(
        session,
        user=actor,
        role_slug=MAKER_ROLE,
        grantor=grantor,
        scope=_scope(),
    )
    _assignment(
        session,
        user=actor,
        role_slug=CHECKER_ROLE,
        grantor=grantor,
        scope=_scope(client_id=client_a.id),
    )

    engine = AuthorizationEngine(session)
    assert engine.authorize_job(actor, Permission.JOB_PREPARE, job_a, at=NOW).allowed
    assert engine.authorize_job(actor, Permission.JOB_PREPARE, job_b, at=NOW).allowed
    assert engine.authorize_job(actor, Permission.JOB_CHECK, job_a, at=NOW).allowed
    denied = engine.authorize_job(actor, Permission.JOB_CHECK, job_b, at=NOW)
    assert not denied.allowed
    assert denied.reason_code is ReasonCode.CLIENT_SCOPE_MISMATCH


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"client": True}, ReasonCode.CLIENT_SCOPE_MISMATCH),
        ({"branch": True}, ReasonCode.BRANCH_SCOPE_MISMATCH),
        ({"direction": JobDirection.EXPORT}, ReasonCode.DIRECTION_SCOPE_MISMATCH),
        ({"mode": JobMode.LCL}, ReasonCode.MODE_SCOPE_MISMATCH),
    ],
)
def test_checker_multidimensional_scope_mismatches_are_explained(
    session: Session, change: dict[str, object], expected: ReasonCode
) -> None:
    actor = _user(session, f"checker-{expected.value}@example.test")
    grantor = _user(session, f"grantor-{expected.value}@example.test")
    job, _, client, other_client, branch, other_branch = _jobs(session)
    _assignment(
        session,
        user=actor,
        role_slug=MAKER_ROLE,
        grantor=grantor,
        scope=_scope(),
    )
    _assignment(
        session,
        user=actor,
        role_slug=CHECKER_ROLE,
        grantor=grantor,
        scope=_scope(
            client_id=client.id,
            branch_id=branch.id,
            direction=JobDirection.IMPORT,
            mode=JobMode.AIR,
        ),
    )
    if change.get("client"):
        job.client = other_client
    if change.get("branch"):
        job.branch = other_branch
    if "direction" in change:
        job.direction = change["direction"]  # type: ignore[assignment]
    if "mode" in change:
        job.mode = change["mode"]  # type: ignore[assignment]
    session.flush()

    decision = AuthorizationEngine(session).authorize_job(actor, Permission.JOB_CHECK, job, at=NOW)

    assert not decision.allowed
    assert decision.reason_code is expected
    assert job.reference not in decision.explanation


def test_revocation_and_expiry_use_half_open_historical_intervals(
    session: Session,
) -> None:
    actor = _user(session, "temporal@example.test")
    grantor = _user(session, "temporal-grantor@example.test")
    job, _, _, _, _, _ = _jobs(session)
    assignment = _assignment(
        session,
        user=actor,
        role_slug=MAKER_ROLE,
        grantor=grantor,
        scope=_scope(),
        valid_from=NOW - timedelta(hours=2),
        valid_until=NOW + timedelta(hours=2),
        revoked_at=NOW,
    )
    engine = AuthorizationEngine(session)

    assert engine.authorize_job(
        actor, Permission.JOB_PREPARE, job, at=NOW - timedelta(microseconds=1)
    ).allowed
    revoked = engine.authorize_job(actor, Permission.JOB_PREPARE, job, at=NOW)
    assert revoked.reason_code is ReasonCode.ACCESS_REVOKED

    assignment.revoked_at = None
    assignment.valid_until = NOW
    expired = engine.authorize_job(actor, Permission.JOB_PREPARE, job, at=NOW)
    assert expired.reason_code is ReasonCode.ACCESS_EXPIRED


def test_missing_permission_and_parser_restrictions_default_deny(session: Session) -> None:
    actor = _user(session, "parser@example.test", kind=UserKind.SERVICE)
    grantor = _user(session, "parser-grantor@example.test")
    job, _, _, _, _, _ = _jobs(session)
    _assignment(
        session,
        user=actor,
        role_slug=PARSER_SERVICE_ROLE,
        grantor=grantor,
        scope=_scope(),
    )
    engine = AuthorizationEngine(session)

    assert engine.authorize_job(actor, Permission.JOB_UPDATE, job, at=NOW).allowed
    for forbidden in (
        Permission.JOB_CHECK,
        Permission.JOB_FILE,
        Permission.JOB_CANCEL,
        Permission.JOB_REOPEN,
        Permission.ACCESS_GRANT,
    ):
        decision = engine.authorize_job(actor, forbidden, job, at=NOW)
        assert not decision.allowed
        assert decision.reason_code is ReasonCode.MISSING_PERMISSION


def test_inactive_actor_and_naive_timestamp_fail_closed(session: Session) -> None:
    actor = _user(session, "inactive-policy@example.test")
    grantor = _user(session, "inactive-grantor@example.test")
    job, _, _, _, _, _ = _jobs(session)
    _assignment(
        session,
        user=actor,
        role_slug=MAKER_ROLE,
        grantor=grantor,
        scope=_scope(),
    )
    engine = AuthorizationEngine(session)
    actor.is_active = False

    assert (
        engine.authorize_job(actor, Permission.JOB_VIEW, job, at=NOW).reason_code
        is ReasonCode.ACTOR_INACTIVE
    )
    actor.is_active = True
    assert (
        engine.authorize_job(actor, Permission.JOB_VIEW, job, at=datetime(2026, 10, 17)).reason_code
        is ReasonCode.POLICY_DATA_INVALID
    )
