from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm.session import sessionmaker

from nfpl_access_control.authorization.roles import (
    ADMIN_ROLE,
    CHECKER_ROLE,
    CLIENT_VIEWER_ROLE,
    FILING_OFFICER_ROLE,
    MAKER_ROLE,
)
from nfpl_access_control.models import (
    AbsenceJobOutcome,
    AbsenceNomination,
    AbsenceNominationJob,
    AbsenceNominationStatus,
    AuditEvent,
    Branch,
    Client,
    EmployeeAvailability,
    Job,
    JobDelegation,
    JobDirection,
    JobMode,
    JobResponsibility,
    JobStage,
    Notification,
    Permission,
    ResponsibilityType,
    Role,
    RoleAssignment,
    User,
    UserKind,
)
from nfpl_access_control.services.absence import AbsenceService
from nfpl_access_control.services.attention import (
    AttentionAccessError,
    AttentionConflictError,
    AttentionService,
)
from nfpl_access_control.services.dashboard import DashboardAccessError, DashboardService
from nfpl_access_control.services.history import HistoryService
from nfpl_access_control.services.notifications import (
    NotificationAccessError,
    NotificationService,
)
from nfpl_access_control.services.role_management import RoleManagementService
from nfpl_access_control.services.work_queue import WorkQueueService
from nfpl_access_control.services.workflow import WorkflowConflictError, WorkflowService
from tests.conftest import TEST_TOKEN

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "path",
    (
        "/v1/absence-nominations",
        "/v1/notifications",
        "/v1/my-work",
        "/v1/admin/dashboard/overview",
    ),
)
def test_phase5c_routes_require_authentication(api_client: TestClient, path: str) -> None:
    response = api_client.get(path)
    assert response.status_code == 401


def test_admin_reference_data_is_secured_and_urgent_requests_include_versions(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    assert api_client.get("/v1/admin/reference-data", headers=headers).status_code == 403

    branch_b = Branch(code="ZZZ", name="Zulu Branch")
    branch_a = Branch(code="AAA", name="Alpha Branch")
    client_b = Client(code="ZZZ", name="Zulu Client")
    client_a = Client(code="AAA", name="Alpha Client")
    nominee = _user(session, "reference-nominee")
    session.add_all([branch_b, branch_a, client_b, client_a])
    nomination = AbsenceService(session).nominate(
        actor=active_user,
        nominee_user_id=nominee.id,
        valid_from=NOW + timedelta(hours=1),
        valid_until=NOW + timedelta(hours=2),
        reason="Versioned urgent request",
        now=NOW,
    )
    _grant(session, active_user, ADMIN_ROLE, active_user)
    session.commit()

    response = api_client.get("/v1/admin/reference-data", headers=headers)
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["clients"]] == [
        "Alpha Client",
        "Zulu Client",
    ]
    assert [item["name"] for item in response.json()["branches"]] == [
        "Alpha Branch",
        "Zulu Branch",
    ]

    urgent = api_client.get("/v1/admin/dashboard/urgent-requests", headers=headers)
    assert urgent.status_code == 200
    assert urgent.json()[0]["request_id"] == nomination.id
    assert urgent.json()[0]["version"] == nomination.version


def test_absence_admin_route_does_not_leak_resource_existence(
    api_client: TestClient,
    session: Session,
    active_user: User,
) -> None:
    nominee = _user(session, "phase5c-api-nominee")
    nomination = AbsenceService(session).nominate(
        actor=active_user,
        nominee_user_id=nominee.id,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=1),
        reason="API existence test",
        now=NOW,
    )
    session.commit()
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    body = {"expected_version": 1, "approved": True, "reason": "unauthorized"}
    existing = api_client.post(
        f"/v1/admin/absence-nominations/{nomination.id}/decision",
        headers=headers,
        json=body,
    )
    missing = api_client.post(
        "/v1/admin/absence-nominations/not-a-real-id/decision",
        headers=headers,
        json=body,
    )
    assert existing.status_code == missing.status_code == 403


def _user(
    session: Session,
    name: str,
    *,
    availability: EmployeeAvailability = EmployeeAvailability.AVAILABLE,
) -> User:
    user = User(
        email=f"{name}@example.test",
        display_name=name.title(),
        kind=UserKind.STAFF,
        availability=availability,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
    )
    session.add(user)
    session.flush()
    return user


def _grant(session: Session, user: User, role_slug: str, admin: User) -> RoleAssignment:
    role = session.scalar(select(Role).where(Role.slug == role_slug))
    assert role is not None
    grant = RoleAssignment(
        user_id=user.id,
        role_id=role.id,
        all_clients=True,
        all_branches=True,
        all_directions=True,
        all_modes=True,
        valid_from=NOW - timedelta(days=1),
        granted_by_user_id=admin.id,
        grant_reason="Phase 5C test",
    )
    session.add(grant)
    session.flush()
    return grant


def _setup(session: Session) -> dict[str, object]:
    branch = Branch(code="P5C", name="Phase 5C Branch")
    client = Client(code="P5C", name="Phase 5C Client")
    admin = _user(session, "phase5c-admin")
    maker = _user(session, "phase5c-maker")
    checker = _user(session, "phase5c-checker")
    filer = _user(session, "phase5c-filer")
    replacement = _user(session, "phase5c-replacement")
    session.add_all([branch, client])
    session.flush()
    _grant(session, admin, ADMIN_ROLE, admin)
    maker_grant = _grant(session, maker, MAKER_ROLE, admin)
    _grant(session, checker, CHECKER_ROLE, admin)
    _grant(session, filer, FILING_OFFICER_ROLE, admin)
    _grant(session, replacement, MAKER_ROLE, admin)
    job = Job(
        reference="P5C-001",
        client_id=client.id,
        branch_id=branch.id,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
        goods_description="Test goods",
    )
    session.add(job)
    session.flush()
    service = WorkflowService(session)
    for responsibility, employee in (
        (ResponsibilityType.MAKER, maker),
        (ResponsibilityType.CHECKER, checker),
        (ResponsibilityType.FILING_OFFICER, filer),
    ):
        service.assign(
            actor=admin,
            job=job,
            responsibility=responsibility,
            target_user_id=employee.id,
            reason="Initial assignment",
            now=NOW,
        )
    return {
        "admin": admin,
        "maker": maker,
        "checker": checker,
        "filer": filer,
        "replacement": replacement,
        "maker_grant": maker_grant,
        "job": job,
    }


def test_absence_bulk_delegation_expires_and_restores_original_queue(session: Session) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    replacement = values["replacement"]
    job = values["job"]
    assert all(isinstance(item, User) for item in (admin, maker, replacement))
    assert isinstance(job, Job)
    service = AbsenceService(session)
    nomination = service.nominate(
        actor=maker,
        nominee_user_id=replacement.id,
        valid_from=NOW + timedelta(minutes=1),
        valid_until=NOW + timedelta(hours=4),
        reason="Medical appointment",
        now=NOW,
    )
    service.decide(
        actor=admin,
        nomination=nomination,
        approved=True,
        reason="Coverage is appropriate",
        expected_version=nomination.version,
        now=NOW + timedelta(seconds=1),
    )

    outcome = session.scalar(
        select(AbsenceNominationJob).where(AbsenceNominationJob.nomination_id == nomination.id)
    )
    assert outcome is not None and outcome.outcome is AbsenceJobOutcome.DELEGATED
    during = NOW + timedelta(minutes=2)
    assert WorkQueueService(session).count(actor=maker, now=during) == 0
    replacement_items = WorkQueueService(session).list(actor=replacement, now=during)
    assert [item.job_id for item in replacement_items] == [job.id]
    assert replacement_items[0].is_delegated is True
    assert replacement_items[0].branch_id == job.branch_id
    assert replacement_items[0].direction is job.direction
    assert replacement_items[0].mode is job.mode
    after = NOW + timedelta(hours=4)
    assert WorkQueueService(session).count(actor=replacement, now=after) == 0
    assert WorkQueueService(session).count(actor=maker, now=after) == 1


def test_ineligible_nominee_is_flagged_and_admin_can_override_one_job(session: Session) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    checker = values["checker"]
    replacement = values["replacement"]
    assert all(isinstance(item, User) for item in (admin, maker, checker, replacement))
    service = AbsenceService(session)
    nomination = service.nominate(
        actor=maker,
        nominee_user_id=checker.id,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=2),
        reason="Unexpected absence",
        now=NOW,
    )
    service.decide(
        actor=admin,
        nomination=nomination,
        approved=True,
        reason="Review each responsibility",
        expected_version=nomination.version,
        now=NOW + timedelta(seconds=1),
    )
    outcome = session.scalar(
        select(AbsenceNominationJob).where(AbsenceNominationJob.nomination_id == nomination.id)
    )
    assert outcome is not None and outcome.outcome is AbsenceJobOutcome.INELIGIBLE

    service.override_job(
        actor=admin,
        outcome=outcome,
        replacement_user_id=replacement.id,
        reason="Use qualified Maker instead",
        now=NOW + timedelta(minutes=1),
    )
    assert outcome.outcome is AbsenceJobOutcome.OVERRIDDEN
    assert outcome.nominee_user_id == replacement.id
    assert outcome.delegation_id is not None


def test_absence_replacement_cannot_check_the_revision_they_prepared(session: Session) -> None:
    values = _setup(session)
    admin, maker = values["admin"], values["maker"]
    checker, job = values["checker"], values["job"]
    assert all(isinstance(item, User) for item in (admin, maker, checker))
    assert isinstance(job, Job)
    _grant(session, maker, CHECKER_ROLE, admin)
    WorkflowService(session).prepare(
        actor=maker,
        job=job,
        checklist_data=None,
        expected_version=job.version,
        now=NOW,
    )
    service = AbsenceService(session)
    nomination = service.nominate(
        actor=checker,
        nominee_user_id=maker.id,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=1),
        reason="Checker coverage",
        now=NOW,
    )
    service.decide(
        actor=admin,
        nomination=nomination,
        approved=True,
        reason="Evaluate each job independently",
        expected_version=nomination.version,
        now=NOW + timedelta(seconds=1),
    )
    outcome = session.scalar(
        select(AbsenceNominationJob).where(AbsenceNominationJob.nomination_id == nomination.id)
    )
    assert outcome is not None and outcome.outcome is AbsenceJobOutcome.INELIGIBLE
    assert "preparer" in outcome.reason.lower()


def test_absence_revoke_is_audited_and_ends_delegation_immediately(session: Session) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    replacement = values["replacement"]
    assert all(isinstance(item, User) for item in (admin, maker, replacement))
    service = AbsenceService(session)
    nomination = service.nominate(
        actor=maker,
        nominee_user_id=replacement.id,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=3),
        reason="Short absence",
        now=NOW,
    )
    service.decide(
        actor=admin,
        nomination=nomination,
        approved=True,
        reason="Approved coverage",
        expected_version=nomination.version,
        now=NOW + timedelta(seconds=1),
    )
    service.revoke(
        actor=admin,
        nomination=nomination,
        reason="Employee returned early",
        expected_version=nomination.version,
        now=NOW + timedelta(minutes=5),
    )
    assert nomination.status is AbsenceNominationStatus.REVOKED
    delegation = session.scalar(
        select(JobDelegation).where(JobDelegation.absence_nomination_id == nomination.id)
    )
    assert delegation is not None and delegation.revoked_at == NOW + timedelta(minutes=5)
    actions = set(session.scalars(select(AuditEvent.action)))
    assert "absence.nomination_revoked" in actions
    assert "absence.delegation_revoked" in actions
    assert WorkQueueService(session).count(actor=replacement, now=NOW + timedelta(minutes=6)) == 0


def test_overlapping_manual_delegations_are_rejected(session: Session) -> None:
    values = _setup(session)
    admin, replacement = values["admin"], values["replacement"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(replacement, User) and isinstance(job, Job)
    service = WorkflowService(session)
    service.delegate(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        delegate_user_id=replacement.id,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=2),
        reason="First temporary coverage",
        now=NOW,
    )
    with pytest.raises(WorkflowConflictError):
        service.delegate(
            actor=admin,
            job=job,
            responsibility=ResponsibilityType.MAKER,
            delegate_user_id=replacement.id,
            valid_from=NOW + timedelta(minutes=1),
            valid_until=NOW + timedelta(hours=1),
            reason="Duplicate coverage",
            now=NOW,
        )


def test_work_queue_count_list_busy_and_revocation_are_consistent(session: Session) -> None:
    values = _setup(session)
    maker = values["maker"]
    grant = values["maker_grant"]
    assert isinstance(maker, User) and isinstance(grant, RoleAssignment)
    queue = WorkQueueService(session)
    maker.availability = EmployeeAvailability.BUSY
    assert queue.count(actor=maker, now=NOW) == len(queue.list(actor=maker, now=NOW)) == 1
    assert queue.list(actor=maker, now=NOW)[0].is_delegated is False
    grant.revoked_at = NOW + timedelta(minutes=1)
    session.flush()
    assert queue.count(actor=maker, now=NOW + timedelta(minutes=1)) == 0
    assert queue.list(actor=maker, now=NOW + timedelta(minutes=1)) == []


def test_work_queue_keyset_pages_do_not_duplicate_jobs(session: Session) -> None:
    values = _setup(session)
    admin, maker = values["admin"], values["maker"]
    first_job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(first_job, Job)
    second_job = Job(
        reference="P5C-002",
        client_id=first_job.client_id,
        branch_id=first_job.branch_id,
        direction=first_job.direction,
        mode=first_job.mode,
        goods_description="Second queued job",
    )
    session.add(second_job)
    session.flush()
    WorkflowService(session).assign(
        actor=admin,
        job=second_job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=maker.id,
        reason="Second queue assignment",
        now=NOW + timedelta(seconds=1),
    )
    queue = WorkQueueService(session)
    first_page, cursor = queue.page(actor=maker, limit=1, now=NOW + timedelta(minutes=1))
    assert len(first_page) == 1 and cursor is not None
    second_page, final_cursor = queue.page(
        actor=maker,
        limit=1,
        cursor=cursor,
        now=NOW + timedelta(minutes=1),
    )
    assert len(second_page) == 1 and final_cursor is None
    assert first_page[0].job_id != second_page[0].job_id
    assert queue.count(actor=maker, now=NOW + timedelta(minutes=1)) == 2


def test_notifications_are_deduplicated_audited_and_current_access_is_rechecked(
    session: Session,
) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    grant = values["maker_grant"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User)
    assert isinstance(grant, RoleAssignment) and isinstance(job, Job)
    notifications = NotificationService(session)
    first = notifications.create(
        actor=admin,
        recipient_user_id=maker.id,
        event_type="test_action",
        message="A test action is ready.",
        target_path=f"/v1/jobs/{job.id}",
        dedupe_key="phase5c-dedupe",
        job=job,
        now=NOW,
    )
    second = notifications.create(
        actor=admin,
        recipient_user_id=maker.id,
        event_type="test_action",
        message="A test action is ready.",
        target_path=f"/v1/jobs/{job.id}",
        dedupe_key="phase5c-dedupe",
        job=job,
        now=NOW,
    )
    assert first is not None and first.id == second.id
    assert session.scalar(select(Notification).where(Notification.dedupe_key == "phase5c-dedupe"))
    assert first.job_reference == job.reference
    assert session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "notification.created",
            AuditEvent.authorization_context["dedupe_key"].as_string() == "phase5c-dedupe",
        )
    )
    assert notifications.unread_count(actor=maker, now=NOW) >= 1
    notifications.mark_read(actor=maker, notification_id=first.id, now=NOW)
    grant.revoked_at = NOW
    session.flush()
    assert first not in notifications.list_for_actor(actor=maker, now=NOW)
    with pytest.raises(NotificationAccessError):
        notifications.mark_read(actor=maker, notification_id=first.id, now=NOW)


def test_queue_search_uses_database_filters_and_matching_count(session: Session) -> None:
    values = _setup(session)
    maker = values["maker"]
    job = values["job"]
    assert isinstance(maker, User) and isinstance(job, Job)
    queue = WorkQueueService(session)

    for search in ("P5C-001", job.id, "Phase 5C Client", "Test goods"):
        items, cursor = queue.page(actor=maker, search=search, now=NOW)
        assert [item.job_id for item in items] == [job.id]
        assert cursor is None
        assert queue.count(actor=maker, search=search, now=NOW) == 1

    assert queue.page(actor=maker, search="not visible", now=NOW) == ([], None)
    assert queue.count(actor=maker, search="not visible", now=NOW) == 0


def test_admin_attention_queue_explains_missing_and_uncovered_responsibility(
    session: Session,
) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    maker.availability = EmployeeAvailability.ABSENT
    checker = session.scalar(
        select(JobResponsibility).where(
            JobResponsibility.job_id == job.id,
            JobResponsibility.responsibility == ResponsibilityType.CHECKER,
        )
    )
    assert checker is not None
    checker.user_id = None
    session.flush()

    items, cursor = DashboardService(session).attention_jobs(actor=admin, now=NOW)

    assert cursor is None
    assert [item.job_id for item in items] == [job.id]
    assert any("Missing Checker" in reason for reason in items[0].reasons)
    assert any("absent without an effective replacement" in reason for reason in items[0].reasons)
    assert DashboardService(session).overview(actor=admin, now=NOW).reassignment_required_jobs == 1


def test_mark_all_read_preserves_notifications_and_audit(session: Session) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    service = NotificationService(session)
    notification = service.create(
        actor=admin,
        recipient_user_id=maker.id,
        event_type="attention",
        message="Please review the shipment.",
        target_path=f"/v1/jobs/{job.id}",
        dedupe_key="mark-all-read-regression",
        job=job,
        now=NOW,
    )
    assert notification is not None
    audit_count = len(list(session.scalars(select(AuditEvent))))

    assert service.mark_all_read(actor=maker, now=NOW + timedelta(seconds=1)) >= 1
    session.expire(notification)
    assert notification.read_at == NOW + timedelta(seconds=1)
    assert service.unread_count(actor=maker, now=NOW + timedelta(seconds=1)) == 0
    assert session.get(Notification, notification.id) is notification
    assert len(list(session.scalars(select(AuditEvent)))) == audit_count


def test_client_query_and_admin_attention_are_scoped_audited_and_deduplicated(
    session: Session,
) -> None:
    values = _setup(session)
    admin = values["admin"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(job, Job)
    client_viewer = _user(session, "phase5c-client")
    client_viewer.kind = UserKind.CLIENT
    outsider = _user(session, "phase5c-outsider")
    outsider.kind = UserKind.CLIENT
    _grant(session, client_viewer, CLIENT_VIEWER_ROLE, admin)
    service = AttentionService(session)

    receipt = service.client_query(
        actor=client_viewer,
        job=job,
        category="delay",
        explanation="Please clarify the expected filing date.",
        now=NOW,
    )
    assert receipt.delivered >= 1
    assert session.get(AuditEvent, receipt.audit_event_id).action == "client.query_raised"
    assert session.scalar(
        select(Notification).where(
            Notification.recipient_user_id == admin.id,
            Notification.event_type == "client_query",
        )
    )
    with pytest.raises(AttentionConflictError):
        service.client_query(
            actor=client_viewer,
            job=job,
            category="delay",
            explanation="Please clarify the expected filing date.",
            now=NOW + timedelta(seconds=1),
        )
    with pytest.raises(AttentionAccessError):
        service.client_query(
            actor=outsider,
            job=job,
            category="delay",
            explanation="Attempt outside client scope.",
            now=NOW,
        )

    attention = service.admin_attention(
        actor=admin,
        job=job,
        explanation="Resolve the client delay query today.",
        now=NOW + timedelta(minutes=1),
    )
    assert attention.delivered == 3
    assert session.get(AuditEvent, attention.audit_event_id).action == "admin.attention_sent"


def test_notification_and_audit_rollback_leave_no_orphans(session: Session) -> None:
    values = _setup(session)
    session.commit()
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    service = NotificationService(session)
    created = service.create(
        actor=admin,
        recipient_user_id=maker.id,
        event_type="rollback_test",
        message="This notification must roll back.",
        target_path=f"/v1/jobs/{job.id}",
        dedupe_key="phase5c-rollback",
        job=job,
        now=NOW,
    )
    assert created is not None
    session.rollback()
    assert (
        session.scalar(select(Notification).where(Notification.dedupe_key == "phase5c-rollback"))
        is None
    )
    assert (
        session.scalar(
            select(AuditEvent).where(
                AuditEvent.authorization_context["dedupe_key"].as_string() == "phase5c-rollback"
            )
        )
        is None
    )


def test_admin_dashboard_is_restricted_searchable_and_archival_is_versioned(
    session: Session,
) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    dashboard = DashboardService(session)
    with pytest.raises(DashboardAccessError):
        dashboard.overview(actor=maker, now=NOW)
    nomination = AbsenceService(session).nominate(
        actor=maker,
        nominee_user_id=values["replacement"].id,  # type: ignore[union-attr]
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=1),
        reason="Dashboard absence count",
        now=NOW,
    )
    AbsenceService(session).decide(
        actor=admin,
        nomination=nomination,
        approved=True,
        reason="Approved dashboard coverage",
        expected_version=nomination.version,
        now=NOW + timedelta(seconds=1),
    )
    overview = dashboard.overview(actor=admin, now=NOW + timedelta(seconds=2))
    assert overview.total_jobs == 1
    assert overview.employees_by_availability["absent"] == 1
    assert dashboard.list_jobs(actor=admin, search="P5C-001", now=NOW)[0][0].id == job.id

    job.stage = JobStage.FILED
    session.flush()
    original_version = job.version
    dashboard.archive(
        actor=admin,
        job=job,
        expected_version=original_version,
        reason="Completed retention archive",
        now=NOW + timedelta(minutes=10),
    )
    assert job.archived_at == NOW + timedelta(minutes=10)
    assert job.version == original_version + 1
    audit = session.scalar(
        select(AuditEvent).where(AuditEvent.job_id == job.id, AuditEvent.action == "job.archived")
    )
    assert audit is not None and audit.affected_job_version == job.version


def test_urgent_absence_requests_are_admin_only_and_role_revocation_notifies(
    session: Session,
) -> None:
    values = _setup(session)
    admin, maker = values["admin"], values["maker"]
    replacement, grant = values["replacement"], values["maker_grant"]
    assert all(isinstance(item, User) for item in (admin, maker, replacement))
    assert isinstance(grant, RoleAssignment)
    nomination = AbsenceService(session).nominate(
        actor=maker,
        nominee_user_id=replacement.id,
        valid_from=NOW + timedelta(hours=1),
        valid_until=NOW + timedelta(hours=2),
        reason="Pending urgent request",
        now=NOW,
    )
    with pytest.raises(DashboardAccessError):
        DashboardService(session).urgent_requests(actor=maker, now=NOW)
    urgent = DashboardService(session).urgent_requests(actor=admin, now=NOW)
    assert [(item.request_type, item.request_id) for item in urgent] == [
        ("absence_nomination", nomination.id)
    ]
    RoleManagementService(session).revoke_role(
        actor=admin,
        assignment_id=grant.id,
        reason="Operational access removed",
        now=NOW + timedelta(minutes=1),
    )
    notice = session.scalar(
        select(Notification).where(
            Notification.recipient_user_id == maker.id,
            Notification.event_type == "permission_revoked",
        )
    )
    assert notice is not None and notice.job_id is None


def test_workflow_assignment_notification_is_atomic_with_responsibility(session: Session) -> None:
    values = _setup(session)
    session.commit()
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    service = WorkflowService(session)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=None,
        reason="Test transactional removal",
        now=NOW + timedelta(minutes=1),
    )
    assert (
        session.scalar(
            select(Notification).where(Notification.event_type == "responsibility_revoked")
        )
        is not None
    )
    session.rollback()
    responsibility = session.scalar(
        select(JobResponsibility).where(
            JobResponsibility.job_id == job.id,
            JobResponsibility.responsibility == ResponsibilityType.MAKER,
        )
    )
    assert responsibility is not None and responsibility.user_id == maker.id
    assert (
        session.scalar(
            select(Notification).where(Notification.event_type == "responsibility_revoked")
        )
        is None
    )


def test_historical_eligibility_observes_absence_and_delegation_boundaries(
    session: Session,
) -> None:
    values = _setup(session)
    admin, maker = values["admin"], values["maker"]
    replacement, job = values["replacement"], values["job"]
    assert all(isinstance(item, User) for item in (admin, maker, replacement))
    assert isinstance(job, Job)
    WorkflowService(session).update_job(
        actor=maker,
        job=job,
        expected_version=job.version,
        goods_description="Versioned before absence",
        now=NOW,
    )
    service = AbsenceService(session)
    nomination = service.nominate(
        actor=maker,
        nominee_user_id=replacement.id,
        valid_from=NOW + timedelta(minutes=1),
        valid_until=NOW + timedelta(hours=1),
        reason="Historical boundary test",
        now=NOW,
    )
    service.decide(
        actor=admin,
        nomination=nomination,
        approved=True,
        reason="Approved for historical reconstruction",
        expected_version=nomination.version,
        now=NOW + timedelta(seconds=1),
    )
    during = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=NOW + timedelta(minutes=2),
    )
    during_ids = {item.user_id for item in during.candidates}
    assert replacement.id in during_ids
    assert maker.id not in during_ids
    at_expiry = HistoryService(session).historical_eligibility(
        job_id=job.id,
        permission=Permission.JOB_PREPARE,
        at=NOW + timedelta(hours=1),
    )
    expiry_ids = {item.user_id for item in at_expiry.candidates}
    assert maker.id in expiry_ids
    assert replacement.id not in expiry_ids


def test_client_notification_delivery_is_scoped_and_sanitized(session: Session) -> None:
    values = _setup(session)
    admin, job = values["admin"], values["job"]
    assert isinstance(admin, User) and isinstance(job, Job)
    viewer = User(
        email="phase5c-viewer@example.test",
        display_name="Phase 5C Viewer",
        kind=UserKind.CLIENT,
    )
    session.add(viewer)
    session.flush()
    role = session.scalar(select(Role).where(Role.slug == CLIENT_VIEWER_ROLE))
    assert role is not None
    session.add(
        RoleAssignment(
            user_id=viewer.id,
            role_id=role.id,
            client_id=job.client_id,
            all_clients=False,
            all_branches=True,
            all_directions=True,
            all_modes=True,
            valid_from=NOW - timedelta(days=1),
            granted_by_user_id=admin.id,
            grant_reason="Client-safe notification test",
        )
    )
    session.flush()
    service = NotificationService(session)
    delivered = service.notify_client_viewers(
        actor=admin,
        job=job,
        event_type="shipment_checked",
        message="Shipment verification is complete.",
        event_key="phase5c-client-safe",
        now=NOW,
    )
    service.create(
        actor=admin,
        recipient_user_id=viewer.id,
        event_type="internal_only",
        message="Internal policy detail.",
        target_path=f"/v1/jobs/{job.id}",
        dedupe_key="phase5c-client-unsafe",
        job=job,
        now=NOW,
    )
    assert len(delivered) == 1
    assert [item.event_type for item in service.list_for_actor(actor=viewer, now=NOW)] == [
        "shipment_checked"
    ]


def test_concurrent_absence_approval_cannot_create_duplicate_delegation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as seed:
        values = _setup(seed)
        admin = values["admin"]
        maker = values["maker"]
        replacement = values["replacement"]
        assert all(isinstance(item, User) for item in (admin, maker, replacement))
        nomination = AbsenceService(seed).nominate(
            actor=maker,
            nominee_user_id=replacement.id,
            valid_from=NOW,
            valid_until=NOW + timedelta(hours=1),
            reason="Concurrent decision test",
            now=NOW,
        )
        admin_id, nomination_id = admin.id, nomination.id
        seed.commit()

    with session_factory() as first, session_factory() as second:
        first_admin, second_admin = first.get(User, admin_id), second.get(User, admin_id)
        first_nomination = first.get(AbsenceNomination, nomination_id)
        second_nomination = second.get(AbsenceNomination, nomination_id)
        assert first_admin and second_admin and first_nomination and second_nomination
        AbsenceService(first).decide(
            actor=first_admin,
            nomination=first_nomination,
            approved=True,
            reason="First decision wins",
            expected_version=1,
            now=NOW + timedelta(seconds=1),
        )
        first.commit()
        with pytest.raises(StaleDataError):
            AbsenceService(second).decide(
                actor=second_admin,
                nomination=second_nomination,
                approved=True,
                reason="Stale concurrent decision",
                expected_version=1,
                now=NOW + timedelta(seconds=2),
            )
            second.flush()
        second.rollback()

    with session_factory() as verify:
        delegations = verify.scalars(
            select(JobDelegation).where(JobDelegation.absence_nomination_id == nomination_id)
        )
        assert len(list(delegations)) == 1
