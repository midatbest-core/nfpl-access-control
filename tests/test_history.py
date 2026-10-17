from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import ReasonCode
from nfpl_access_control.authorization.roles import CHECKER_ROLE, MAKER_ROLE
from nfpl_access_control.models import (
    AuditEvent,
    EmployeeAvailability,
    Job,
    JobDirection,
    JobMode,
    JobResponsibilityEvent,
    JobStage,
    JobVersion,
    Permission,
    ResponsibilityEventType,
    ResponsibilityType,
    RoleAssignmentEvent,
    User,
)
from nfpl_access_control.services.history import HistoryService
from nfpl_access_control.services.role_management import RoleManagementService
from nfpl_access_control.services.workflow import WorkflowError, WorkflowService
from tests.test_authorization import _scope
from tests.test_workflow import NOW, _assign_core, _grant, _setup, _user


def _versioned_setup(session: Session) -> dict[str, object]:
    values = _setup(session)
    for value in values.values():
        if isinstance(value, User):
            value.created_at = NOW - timedelta(days=2)
    service = WorkflowService(session)
    parser = values["parser"]
    client = values["client"]
    branch = values["branch"]
    assert isinstance(parser, User)
    job = service.create_job(
        actor=parser,
        reference="HISTORY-001",
        client_id=client.id,  # type: ignore[union-attr]
        branch_id=branch.id,  # type: ignore[union-attr]
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
        goods_description="Original description",
        now=NOW,
    )
    values["job"] = job
    _assign_core(service, values)
    session.flush()
    return values


def test_versions_diff_state_at_and_atomic_rollback(session: Session) -> None:
    values = _versioned_setup(session)
    parser = values["parser"]
    job = values["job"]
    assert isinstance(parser, User) and isinstance(job, Job)
    service = WorkflowService(session)
    service.update_job(
        actor=parser,
        job=job,
        expected_version=job.version,
        goods_description="Revised description",
        now=NOW + timedelta(minutes=1),
    )
    session.commit()

    history = HistoryService(session)
    assert [item.version_number for item in history.list_versions(job.id)] == [2, 1]
    assert history.state_at(job.id, NOW).version_number == 1  # type: ignore[union-attr]
    assert history.state_at(job.id, NOW + timedelta(minutes=1)).version_number == 2  # type: ignore[union-attr]
    changes = {item.field: item for item in history.diff(job.id, 1, 2)}
    assert changes["goods_description"].before == "Original description"
    assert changes["goods_description"].after == "Revised description"
    changed_by = history.changes_for_field(job.id, "goods_description")
    assert [(item.version_number, item.actor_user_id) for item in changed_by] == [(2, parser.id)]
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.job_id == job.id,
            AuditEvent.action == "job.updated",
        )
    )
    assert audit is not None and audit.affected_job_version == 2

    service.update_job(
        actor=parser,
        job=job,
        expected_version=job.version,
        goods_description="Rolled back",
        now=NOW + timedelta(minutes=2),
    )
    session.rollback()
    assert HistoryService(session).version(job.id, 3) is None
    assert not session.scalar(
        select(AuditEvent.id).where(
            AuditEvent.job_id == job.id,
            AuditEvent.affected_job_version == 3,
        )
    )


def test_approval_and_rejection_versions_preserve_actual_actor(session: Session) -> None:
    values = _versioned_setup(session)
    service = WorkflowService(session)
    maker = values["maker"]
    checker = values["checker"]
    job = values["job"]
    assert isinstance(maker, User) and isinstance(checker, User) and isinstance(job, Job)
    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"complete": True},
        expected_version=job.version,
        now=NOW + timedelta(minutes=1),
    )
    service.check(
        actor=checker,
        job=job,
        approved=False,
        reason="Missing invoice",
        expected_version=job.version,
        now=NOW + timedelta(minutes=2),
    )
    versions = HistoryService(session).list_versions(job.id)

    assert versions[0].action == "job.check_rejected"
    assert versions[0].actor_user_id == checker.id
    assert versions[0].snapshot["stage"] == JobStage.CONFIRMED.value
    assert versions[1].action == "job.prepared"
    assert versions[1].snapshot["prepared_by_user_id"] == maker.id
    reconstructed = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_CHECK,
        at=NOW + timedelta(minutes=2),
    )
    assert reconstructed.actual_events_at_timestamp[0].actor_user_id == checker.id
    assert reconstructed.actual_events_at_timestamp[0].action == "job.check_rejected"


def test_historical_role_revocation_exact_boundary_and_role_audit(session: Session) -> None:
    values = _versioned_setup(session)
    admin = values["admin"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(job, Job)
    candidate = _user(session, "historical-maker")
    candidate.created_at = NOW - timedelta(days=2)
    manager = RoleManagementService(session)
    assignment = manager.grant_role(
        actor=admin,
        target_user_id=candidate.id,
        role_slug=MAKER_ROLE,
        scope=_scope(),
        reason="Temporary Maker access",
        valid_from=NOW,
        now=NOW,
    )
    WorkflowService(session).assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=candidate.id,
        reason="Historical Maker",
        now=NOW + timedelta(minutes=1),
    )
    revoked_at = NOW + timedelta(hours=1)
    manager.revoke_role(
        actor=admin,
        assignment_id=assignment.id,
        reason="Access no longer required",
        now=revoked_at,
    )

    before = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=revoked_at - timedelta(microseconds=1),
    )
    boundary = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=revoked_at,
    )
    assert candidate.id in {item.user_id for item in before.candidates}
    assert candidate.id not in {item.user_id for item in boundary.candidates}
    actions = set(
        session.scalars(
            select(AuditEvent.action).where(
                AuditEvent.actor_user_id == admin.id,
                AuditEvent.action.in_(("role.granted", "role.revoked")),
            )
        )
    )
    assert actions == {"role.granted", "role.revoked"}


def test_responsibility_reassignment_and_delegation_boundaries(session: Session) -> None:
    values = _versioned_setup(session)
    admin = values["admin"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(job, Job)
    first = _user(session, "history-first")
    second = _user(session, "history-second")
    delegate = _user(session, "history-delegate")
    for user in (first, second, delegate):
        user.created_at = NOW - timedelta(days=2)
        _grant(session, user, MAKER_ROLE, admin)
    service = WorkflowService(session)
    first_at = NOW + timedelta(minutes=1)
    second_at = NOW + timedelta(minutes=2)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=first.id,
        reason="First historical Maker",
        now=first_at,
    )
    service.delegate(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        delegate_user_id=delegate.id,
        valid_from=first_at,
        valid_until=second_at,
        reason="Short cover",
        now=first_at,
    )
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=second.id,
        reason="Permanent reassignment",
        now=second_at,
    )

    during = HistoryService(session).historical_eligibility(
        job_id=job.id, permission=Permission.JOB_PREPARE, at=first_at
    )
    boundary = HistoryService(session).historical_eligibility(
        job_id=job.id, permission=Permission.JOB_PREPARE, at=second_at
    )
    assert {item.user_id for item in during.candidates} == {first.id, delegate.id}
    assert {item.user_id for item in boundary.candidates} == {second.id}
    assert during.complete and boundary.complete
    assert all(item.explanation.startswith("Effective scoped") for item in during.candidates)


def test_role_grant_and_responsibility_become_effective_at_exact_boundary(
    session: Session,
) -> None:
    values = _versioned_setup(session)
    admin = values["admin"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(job, Job)
    candidate = _user(session, "grant-boundary-maker")
    candidate.created_at = NOW - timedelta(days=2)
    boundary = NOW + timedelta(minutes=5)
    RoleManagementService(session).grant_role(
        actor=admin,
        target_user_id=candidate.id,
        role_slug=MAKER_ROLE,
        scope=_scope(),
        reason="Boundary grant",
        valid_from=boundary,
        now=NOW,
    )
    WorkflowService(session).assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=candidate.id,
        reason="Boundary assignment",
        now=boundary,
    )

    before = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=boundary - timedelta(microseconds=1),
    )
    effective = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=boundary,
    )
    assert candidate.id not in {item.user_id for item in before.candidates}
    assert candidate.id in {item.user_id for item in effective.candidates}


def test_historical_maker_checker_separation_and_availability(session: Session) -> None:
    values = _versioned_setup(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    _grant(session, maker, CHECKER_ROLE, admin)
    service = WorkflowService(session)
    prepared_at = NOW + timedelta(minutes=1)
    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"complete": True},
        expected_version=job.version,
        now=prepared_at,
    )
    session.add(
        JobResponsibilityEvent(
            job_id=job.id,
            responsibility=ResponsibilityType.CHECKER,
            event_type=ResponsibilityEventType.REASSIGNED,
            previous_user_id=values["checker"].id,  # type: ignore[union-attr]
            new_user_id=maker.id,
            actor_user_id=admin.id,
            occurred_at=prepared_at,
            reason="Construct conflict to verify historical invariant",
        )
    )
    session.flush()

    checking = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_CHECK,
        at=prepared_at,
    )
    assert maker.id not in {item.user_id for item in checking.candidates}

    service.set_availability(
        actor=admin,
        employee=maker,
        availability=EmployeeAvailability.ABSENT,
        reason="Leave started",
        now=prepared_at + timedelta(minutes=1),
    )
    before_absence = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=prepared_at + timedelta(seconds=30),
    )
    at_absence = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=prepared_at + timedelta(minutes=1),
    )
    assert maker.id in {item.user_id for item in before_absence.candidates}
    assert maker.id not in {item.user_id for item in at_absence.candidates}


def test_missing_version_evidence_returns_explicit_incomplete_result(session: Session) -> None:
    values = _setup(session)
    job = values["job"]
    assert isinstance(job, Job)

    result = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=NOW,
    )

    assert not result.complete
    assert not result.candidates
    assert "No trustworthy job version" in result.limitations[0]


def test_versions_and_assignment_events_are_append_only(session: Session) -> None:
    values = _versioned_setup(session)
    job = values["job"]
    assert isinstance(job, Job)
    version = session.scalar(select(JobVersion).where(JobVersion.job_id == job.id))
    event = session.scalar(
        select(JobResponsibilityEvent).where(JobResponsibilityEvent.job_id == job.id)
    )
    assert version is not None and event is not None
    session.commit()
    session.delete(version)
    with pytest.raises(RuntimeError, match="append-only"):
        session.flush()
    session.rollback()

    event = session.scalar(
        select(JobResponsibilityEvent).where(JobResponsibilityEvent.job_id == job.id)
    )
    assert event is not None
    session.delete(event)
    with pytest.raises(RuntimeError, match="append-only"):
        session.flush()


def test_role_assignment_events_are_append_only(session: Session) -> None:
    values = _versioned_setup(session)
    admin = values["admin"]
    assert isinstance(admin, User)
    candidate = _user(session, "immutable-role-event")
    RoleManagementService(session).grant_role(
        actor=admin,
        target_user_id=candidate.id,
        role_slug=MAKER_ROLE,
        scope=_scope(),
        reason="Create immutable event",
        now=NOW,
    )
    session.commit()
    event = session.scalar(select(RoleAssignmentEvent))
    assert event is not None
    session.delete(event)
    with pytest.raises(RuntimeError, match="append-only"):
        session.flush()


def test_stale_version_and_invalid_stage_denials_are_audited(session: Session) -> None:
    values = _versioned_setup(session)
    maker = values["maker"]
    filer = values["filer"]
    job = values["job"]
    assert isinstance(maker, User) and isinstance(filer, User) and isinstance(job, Job)
    service = WorkflowService(session)

    with pytest.raises(WorkflowError) as stale:
        service.prepare(
            actor=maker,
            job=job,
            checklist_data={"complete": True},
            expected_version=job.version + 1,
            now=NOW + timedelta(minutes=1),
        )
    assert stale.value.decision.reason_code is ReasonCode.STALE_VERSION

    with pytest.raises(WorkflowError) as invalid_stage:
        service.file(
            actor=filer,
            job=job,
            expected_version=job.version,
            now=NOW + timedelta(minutes=2),
        )
    assert invalid_stage.value.decision.reason_code is ReasonCode.INVALID_STAGE

    denials = list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.job_id == job.id, AuditEvent.denied.is_(True))
            .order_by(AuditEvent.occurred_at)
        )
    )
    assert [(item.action, item.authorization_context["reason_code"]) for item in denials] == [
        ("job.prepare.denied", ReasonCode.STALE_VERSION.value),
        ("job.file.denied", ReasonCode.INVALID_STAGE.value),
    ]
    assert all(item.affected_job_version == job.version for item in denials)
    assert len(HistoryService(session).list_versions(job.id)) == 1
