from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import ReasonCode
from nfpl_access_control.authorization.roles import (
    ADMIN_ROLE,
    CHECKER_ROLE,
    FILING_OFFICER_ROLE,
    MAKER_ROLE,
    PARSER_SERVICE_ROLE,
)
from nfpl_access_control.models import (
    AuditEvent,
    Branch,
    Client,
    EmployeeAvailability,
    ExceptionalAction,
    ExceptionalRequestStatus,
    FilingReturnCategory,
    Job,
    JobDelegation,
    JobDirection,
    JobEditRequest,
    JobMode,
    JobResponsibility,
    JobStage,
    ResponsibilityType,
    Role,
    RoleAssignment,
    User,
    UserKind,
)
from nfpl_access_control.services.workflow import (
    WorkflowError,
    WorkflowService,
    WorkflowValidationError,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _user(
    session: Session,
    name: str,
    *,
    kind: UserKind = UserKind.STAFF,
    availability: EmployeeAvailability = EmployeeAvailability.AVAILABLE,
) -> User:
    user = User(
        email=f"{name}@example.test",
        display_name=name.title(),
        kind=kind,
        availability=availability,
    )
    session.add(user)
    session.flush()
    return user


def _grant(
    session: Session,
    user: User,
    role_slug: str,
    grantor: User,
    *,
    valid_until: datetime | None = None,
) -> RoleAssignment:
    role = session.scalar(select(Role).where(Role.slug == role_slug))
    assert role is not None
    assignment = RoleAssignment(
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
        valid_from=NOW - timedelta(days=1),
        valid_until=valid_until,
        granted_by_user_id=grantor.id,
        grant_reason="workflow test",
    )
    session.add(assignment)
    session.flush()
    return assignment


def _setup(session: Session) -> dict[str, object]:
    branch = Branch(code="WF-BR", name="Workflow Branch")
    client = Client(code="WF-CL", name="Workflow Client")
    admin = _user(session, "workflow-admin")
    maker = _user(session, "workflow-maker")
    checker = _user(session, "workflow-checker")
    filer = _user(session, "workflow-filer")
    parser = _user(session, "workflow-parser", kind=UserKind.SERVICE)
    session.add_all([branch, client])
    session.flush()
    _grant(session, admin, ADMIN_ROLE, admin)
    maker_grant = _grant(session, maker, MAKER_ROLE, admin)
    _grant(session, checker, CHECKER_ROLE, admin)
    _grant(session, filer, FILING_OFFICER_ROLE, admin)
    _grant(session, parser, PARSER_SERVICE_ROLE, admin)
    job = Job(
        reference="WF-001",
        client_id=client.id,
        branch_id=branch.id,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
        goods_description="Machine parts",
    )
    session.add(job)
    session.flush()
    return {
        "branch": branch,
        "client": client,
        "admin": admin,
        "maker": maker,
        "checker": checker,
        "filer": filer,
        "parser": parser,
        "maker_grant": maker_grant,
        "job": job,
    }


def _assign_core(service: WorkflowService, values: dict[str, object]) -> None:
    job = values["job"]
    admin = values["admin"]
    assert isinstance(job, Job) and isinstance(admin, User)
    for responsibility, key in (
        (ResponsibilityType.MAKER, "maker"),
        (ResponsibilityType.CHECKER, "checker"),
        (ResponsibilityType.FILING_OFFICER, "filer"),
    ):
        employee = values[key]
        assert isinstance(employee, User)
        service.assign(
            actor=admin,
            job=job,
            responsibility=responsibility,
            target_user_id=employee.id,
            reason="Initial responsibility",
            now=NOW,
        )


def test_checker_suggestions_exclude_the_actually_assigned_maker(session: Session) -> None:
    values = _setup(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    _grant(session, maker, CHECKER_ROLE, admin)
    alternate_maker = _user(session, "aaa-alternate-maker")
    _grant(session, alternate_maker, MAKER_ROLE, admin)
    service = WorkflowService(session)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=maker.id,
        reason="Assign overlapping-role employee as Maker",
        now=NOW,
    )

    suggestions = service.suggestions(actor=admin, job=job, now=NOW)

    checker_ids = {item.user_id for item in suggestions[ResponsibilityType.CHECKER]}
    assert maker.id not in checker_ids
    assert alternate_maker.id != maker.id


def test_independent_prepare_check_file_and_atomic_audit(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    checker = values["checker"]
    filer = values["filer"]
    assert all(isinstance(item, User) for item in (maker, checker, filer))
    assert isinstance(job, Job)

    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"documents_complete": True},
        expected_version=job.version,
        now=NOW,
    )
    service.check(
        actor=checker,
        job=job,
        approved=True,
        reason="Documents independently verified",
        expected_version=job.version,
        now=NOW + timedelta(minutes=1),
    )
    service.file(
        actor=filer,
        job=job,
        expected_version=job.version,
        now=NOW + timedelta(minutes=2),
    )
    session.commit()

    assert job.stage is JobStage.FILED
    assert job.prepared_by_user_id == maker.id
    assert job.checked_by_user_id == checker.id
    assert job.filed_by_user_id == filer.id
    actions = set(session.scalars(select(AuditEvent.action).where(AuditEvent.job_id == job.id)))
    assert {"job.prepared", "job.checked", "job.filed"}.issubset(actions)


def test_actual_preparer_cannot_check_after_checker_promotion(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    _grant(session, maker, CHECKER_ROLE, admin)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=maker.id,
        reason="Maker assignment",
        now=NOW,
    )
    session.add(
        JobResponsibility(
            job_id=job.id,
            responsibility=ResponsibilityType.CHECKER,
            user_id=maker.id,
            assigned_by_user_id=admin.id,
            assigned_at=NOW,
        )
    )
    session.flush()
    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"ready": True},
        expected_version=job.version,
        now=NOW,
    )

    with pytest.raises(WorkflowError) as caught:
        service.check(
            actor=maker,
            job=job,
            approved=True,
            reason="self approval attempt",
            expected_version=job.version,
            now=NOW,
        )

    assert caught.value.decision.reason_code is ReasonCode.SELF_CHECK_FORBIDDEN
    assert job.stage is JobStage.PREPARED


def test_revoked_role_immediately_stops_assigned_employee(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    grant = values["maker_grant"]
    assert all(isinstance(item, User) for item in (admin, maker))
    assert isinstance(job, Job) and isinstance(grant, RoleAssignment)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=maker.id,
        reason="Maker assignment",
        now=NOW,
    )
    grant.revoked_at = NOW
    session.flush()

    with pytest.raises(WorkflowError) as caught:
        service.prepare(
            actor=maker,
            job=job,
            checklist_data={"ready": True},
            expected_version=job.version,
            now=NOW,
        )

    assert caught.value.decision.reason_code is ReasonCode.ACCESS_REVOKED
    assert job.stage is JobStage.CONFIRMED


def test_temporary_delegation_expires_at_authorization_time(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    delegate = _user(session, "temporary-maker")
    _grant(session, delegate, MAKER_ROLE, admin)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=maker.id,
        reason="Primary Maker",
        now=NOW,
    )
    delegation = service.delegate(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        delegate_user_id=delegate.id,
        valid_from=NOW,
        valid_until=NOW + timedelta(hours=1),
        reason="Cover temporary absence",
        now=NOW,
    )
    assert isinstance(delegation, JobDelegation)

    with pytest.raises(WorkflowError) as caught:
        service.prepare(
            actor=delegate,
            job=job,
            checklist_data={"ready": True},
            expected_version=job.version,
            now=NOW + timedelta(hours=1),
        )

    assert caught.value.decision.reason_code is ReasonCode.MISSING_RESPONSIBILITY
    service.prepare(
        actor=delegate,
        job=job,
        checklist_data={"ready": True},
        expected_version=job.version,
        now=NOW + timedelta(minutes=30),
    )
    assert job.prepared_by_user_id == delegate.id
    service.revoke_delegation(
        actor=admin,
        delegation=delegation,
        reason="Employee returned",
        now=NOW + timedelta(minutes=31),
    )
    assert delegation.revoked_at == NOW + timedelta(minutes=31)


def test_absent_employee_cannot_be_assigned_or_act(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    maker.availability = EmployeeAvailability.ABSENT

    with pytest.raises(WorkflowValidationError, match="Absent"):
        service.assign(
            actor=admin,
            job=job,
            responsibility=ResponsibilityType.MAKER,
            target_user_id=maker.id,
            reason="Should be rejected",
            now=NOW,
        )

    session.add(
        JobResponsibility(
            job_id=job.id,
            responsibility=ResponsibilityType.MAKER,
            user_id=maker.id,
            assigned_by_user_id=admin.id,
            assigned_at=NOW,
        )
    )
    session.flush()
    with pytest.raises(WorkflowError) as caught:
        service.prepare(
            actor=maker,
            job=job,
            checklist_data={"ready": True},
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.EMPLOYEE_ABSENT


def test_edit_after_check_requires_admin_approval_and_fresh_verification(
    session: Session,
) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    checker = values["checker"]
    assert isinstance(job, Job) and isinstance(maker, User) and isinstance(checker, User)
    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"ready": True},
        expected_version=job.version,
        now=NOW,
    )
    service.check(
        actor=checker,
        job=job,
        approved=True,
        reason="verified",
        expected_version=job.version,
        now=NOW,
    )
    checked_revision = job.checklist_revision

    with pytest.raises(WorkflowError) as caught:
        service.update_job(
            actor=maker,
            job=job,
            expected_version=job.version,
            goods_description="Unapproved correction",
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.SUBMISSION_LOCKED

    request = service.request_edit(
        actor=maker,
        job=job,
        reason="The goods description needs correction",
        now=NOW,
    )
    service.decide_edit_request(
        actor=values["admin"],
        request=request,
        approved=True,
        reason="Correction is limited to this shipment",
        expected_version=job.version,
        now=NOW,
    )
    service.update_job(
        actor=maker,
        job=job,
        expected_version=job.version,
        goods_description="Corrected description",
        now=NOW,
    )

    assert job.stage is JobStage.CONFIRMED
    assert job.checked_by_user_id is None
    assert job.checklist_revision == checked_revision
    with pytest.raises(WorkflowError) as caught:
        service.prepare(
            actor=maker,
            job=job,
            checklist_data=None,
            justification="",
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.JUSTIFICATION_REQUIRED
    service.prepare(
        actor=maker,
        job=job,
        checklist_data=None,
        justification="Corrected the goods description requested above",
        expected_version=job.version,
        now=NOW,
    )
    assert job.checklist_revision == checked_revision + 1
    assert job.maker_edit_locked is True


def test_dynamic_checker_checklist_rejects_invalid_na_and_returns_incomplete(
    session: Session,
) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    checker = values["checker"]
    assert isinstance(job, Job) and isinstance(maker, User) and isinstance(checker, User)
    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"maker_cannot_define": True},
        expected_version=job.version,
        now=NOW,
    )
    items = job.checklist_data["items"]
    assert isinstance(items, list)
    assert {item["key"] for item in items} >= {"air_waybill", "import_requirements"}
    assert "maker_cannot_define" not in job.checklist_data
    invalid = [{"key": item["key"], "status": "complete"} for item in items]
    invalid[0] = {"key": invalid[0]["key"], "status": "not_applicable"}
    with pytest.raises(WorkflowError) as caught:
        service.check(
            actor=checker,
            job=job,
            approved=None,
            reason="",
            checklist_items=invalid,
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.INVALID_CHECKLIST

    returned = [{"key": item["key"], "status": "complete"} for item in items]
    returned[0]["status"] = "incomplete"
    service.check(
        actor=checker,
        job=job,
        approved=None,
        reason="Commercial invoice total does not match",
        checklist_items=returned,
        expected_version=job.version,
        now=NOW,
    )
    assert job.stage is JobStage.CONFIRMED
    assert job.maker_edit_locked is False
    assert job.maker_correction_required is True
    assert job.last_return_reason == "Commercial invoice total does not match"


@pytest.mark.parametrize(
    ("mode", "direction", "mode_key", "direction_key"),
    [
        (JobMode.AIR, JobDirection.IMPORT, "air_waybill", "import_requirements"),
        (JobMode.AIR, JobDirection.EXPORT, "air_waybill", "export_requirements"),
        (JobMode.FCL, JobDirection.IMPORT, "bill_of_lading", "import_requirements"),
        (JobMode.FCL, JobDirection.EXPORT, "container_reference", "export_requirements"),
        (JobMode.LCL, JobDirection.IMPORT, "house_bill_of_lading", "import_requirements"),
        (JobMode.LCL, JobDirection.EXPORT, "consolidation_reference", "export_requirements"),
    ],
)
def test_checklist_template_is_derived_from_fixed_job_category(
    session: Session,
    mode: JobMode,
    direction: JobDirection,
    mode_key: str,
    direction_key: str,
) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    assert isinstance(job, Job) and isinstance(maker, User)
    job.mode = mode
    job.direction = direction
    session.flush()
    service.prepare(
        actor=maker,
        job=job,
        checklist_data=None,
        expected_version=job.version,
        now=NOW,
    )
    keys = {item["key"] for item in job.checklist_data["items"]}  # type: ignore[index]
    assert {mode_key, direction_key}.issubset(keys)


def test_filing_return_routes_checker_or_maker_and_requires_justification(
    session: Session,
) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    checker = values["checker"]
    filer = values["filer"]
    assert isinstance(job, Job)
    assert all(isinstance(item, User) for item in (maker, checker, filer))
    service.prepare(
        actor=maker,
        job=job,
        checklist_data=None,
        expected_version=job.version,
        now=NOW,
    )
    service.check(
        actor=checker,
        job=job,
        approved=True,
        reason="Initial verification",
        expected_version=job.version,
        now=NOW,
    )
    with pytest.raises(WorkflowError) as caught:
        service.return_for_correction(
            actor=filer,
            job=job,
            category=FilingReturnCategory.CHECKER_FAULT,
            reason="",
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.JUSTIFICATION_REQUIRED
    service.return_for_correction(
        actor=filer,
        job=job,
        category=FilingReturnCategory.CHECKER_FAULT,
        reason="Not Applicable decision needs evidence",
        expected_version=job.version,
        now=NOW,
    )
    assert job.stage is JobStage.PREPARED
    assert job.maker_edit_locked is True
    with pytest.raises(WorkflowError) as caught:
        service.check(
            actor=checker,
            job=job,
            approved=True,
            reason="",
            justification="",
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.JUSTIFICATION_REQUIRED
    service.check(
        actor=checker,
        job=job,
        approved=True,
        reason="",
        justification="Rechecked the disputed supporting evidence",
        expected_version=job.version,
        now=NOW,
    )
    service.return_for_correction(
        actor=filer,
        job=job,
        category=FilingReturnCategory.BOTH,
        reason="Description and checklist both need correction",
        expected_version=job.version,
        now=NOW,
    )
    assert job.stage is JobStage.CONFIRMED
    assert job.maker_edit_locked is False
    assert job.maker_correction_required is True
    assert job.checker_correction_required is True


def test_admin_maker_cannot_approve_own_edit_request(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    admin = values["admin"]
    assert isinstance(job, Job) and isinstance(maker, User) and isinstance(admin, User)
    _grant(session, maker, ADMIN_ROLE, admin)
    service.prepare(
        actor=maker,
        job=job,
        checklist_data=None,
        expected_version=job.version,
        now=NOW,
    )
    request = service.request_edit(
        actor=maker, job=job, reason="Need to correct my submission", now=NOW
    )
    with pytest.raises(WorkflowError) as caught:
        service.decide_edit_request(
            actor=maker,
            request=request,
            approved=True,
            reason="Attempt to approve my own request",
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.SELF_APPROVAL_FORBIDDEN
    assert job.maker_edit_locked is True


def test_edit_request_is_job_specific_independent_and_version_safe(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    job = values["job"]
    maker = values["maker"]
    admin = values["admin"]
    assert isinstance(job, Job) and isinstance(maker, User) and isinstance(admin, User)
    service.prepare(
        actor=maker,
        job=job,
        checklist_data=None,
        expected_version=job.version,
        now=NOW,
    )
    request = service.request_edit(actor=maker, job=job, reason="Correct a typo", now=NOW)
    assert isinstance(request, JobEditRequest)
    with pytest.raises(WorkflowError) as caught:
        service.decide_edit_request(
            actor=admin,
            request=request,
            approved=True,
            reason="Approved",
            expected_version=job.version - 1,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.STALE_VERSION
    assert job.maker_edit_locked is True


def test_phase5b_mutation_and_audit_rollback_together(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    _assign_core(service, values)
    session.commit()
    job = values["job"]
    maker = values["maker"]
    assert isinstance(job, Job) and isinstance(maker, User)

    def fail_audit(**_kwargs: object) -> None:
        raise RuntimeError("simulated audit storage failure")

    service.audit.record = fail_audit  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="audit storage"):
        service.prepare(
            actor=maker,
            job=job,
            checklist_data=None,
            expected_version=job.version,
            now=NOW,
        )
    session.rollback()
    restored = session.get(Job, job.id)
    assert restored is not None
    assert restored.stage is JobStage.CONFIRMED
    assert restored.checklist_revision == 0
    assert restored.maker_edit_locked is False


def test_filed_cancel_requires_different_admin_approval(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(job, Job)
    second_admin = _user(session, "second-admin")
    _grant(session, second_admin, ADMIN_ROLE, admin)
    job.stage = JobStage.FILED
    session.flush()
    request = service.request_exception(
        actor=admin,
        job=job,
        action=ExceptionalAction.CANCEL,
        reason="Filed in error",
        now=NOW,
    )

    with pytest.raises(WorkflowError) as caught:
        service.approve_exception(
            actor=admin,
            request=request,
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.SELF_APPROVAL_FORBIDDEN
    assert request.status is ExceptionalRequestStatus.PENDING

    service.approve_exception(
        actor=second_admin,
        request=request,
        expected_version=job.version,
        now=NOW + timedelta(minutes=1),
    )
    assert job.stage is JobStage.CANCELLED
    assert request.status is ExceptionalRequestStatus.EXECUTED


def test_parser_can_create_and_update_only_parser_fields(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    parser = values["parser"]
    branch = values["branch"]
    client = values["client"]
    assert isinstance(parser, User)
    assert isinstance(branch, Branch) and isinstance(client, Client)
    job = service.create_job(
        actor=parser,
        reference="PARSED-001",
        client_id=client.id,
        branch_id=branch.id,
        direction=JobDirection.EXPORT,
        mode=JobMode.LCL,
        goods_description="Parsed goods",
        now=NOW,
    )
    service.update_job(
        actor=parser,
        job=job,
        expected_version=job.version,
        container_reference="CONT-1",
        now=NOW,
    )
    with pytest.raises(WorkflowError) as caught:
        service.prepare(
            actor=parser,
            job=job,
            checklist_data={"unsafe": True},
            expected_version=job.version,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.MISSING_PERMISSION
    assert job.stage is JobStage.CONFIRMED


def test_suggestions_rank_available_low_workload_and_separate_maker_checker(
    session: Session,
) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    job = values["job"]
    client = values["client"]
    branch = values["branch"]
    assert isinstance(admin, User) and isinstance(job, Job)
    assert isinstance(client, Client) and isinstance(branch, Branch)
    admin.availability = EmployeeAvailability.BUSY
    alpha = _user(session, "alpha")
    beta = _user(session, "beta")
    absent = _user(session, "absent-candidate", availability=EmployeeAvailability.ABSENT)
    for candidate in (alpha, beta, absent):
        _grant(session, candidate, MAKER_ROLE, admin)
    _grant(session, beta, CHECKER_ROLE, admin)
    workload_job = Job(
        reference="WF-WORKLOAD",
        client_id=client.id,
        branch_id=branch.id,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
    )
    session.add(workload_job)
    session.flush()
    session.add(
        JobResponsibility(
            job_id=workload_job.id,
            responsibility=ResponsibilityType.MAKER,
            user_id=alpha.id,
            assigned_by_user_id=admin.id,
            assigned_at=NOW,
        )
    )
    session.flush()

    suggestions = service.suggestions(actor=admin, job=job, now=NOW)

    maker = suggestions[ResponsibilityType.MAKER]
    checker = suggestions[ResponsibilityType.CHECKER]
    assert maker[0].user_id == beta.id
    assert beta.id not in {item.user_id for item in checker}
    assert absent.id not in {item.user_id for items in suggestions.values() for item in items}


def test_stale_version_and_transaction_rollback_preserve_job_and_audit(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    admin = values["admin"]
    maker = values["maker"]
    job = values["job"]
    assert isinstance(admin, User) and isinstance(maker, User) and isinstance(job, Job)
    service.assign(
        actor=admin,
        job=job,
        responsibility=ResponsibilityType.MAKER,
        target_user_id=maker.id,
        reason="Maker assignment",
        now=NOW,
    )
    session.commit()
    starting_version = job.version

    with pytest.raises(WorkflowError) as caught:
        service.prepare(
            actor=maker,
            job=job,
            checklist_data={"ready": True},
            expected_version=starting_version + 1,
            now=NOW,
        )
    assert caught.value.decision.reason_code is ReasonCode.STALE_VERSION

    service.prepare(
        actor=maker,
        job=job,
        checklist_data={"ready": True},
        expected_version=starting_version,
        now=NOW,
    )
    session.rollback()
    session.expire_all()
    restored = session.get(Job, job.id)
    assert restored is not None
    assert restored.stage is JobStage.CONFIRMED
    assert not session.scalar(
        select(AuditEvent.id).where(
            AuditEvent.job_id == job.id,
            AuditEvent.action == "job.prepared",
        )
    )


def test_audit_events_are_append_only(session: Session) -> None:
    values = _setup(session)
    service = WorkflowService(session)
    parser = values["parser"]
    client = values["client"]
    branch = values["branch"]
    assert isinstance(parser, User)
    assert isinstance(client, Client) and isinstance(branch, Branch)
    job = service.create_job(
        actor=parser,
        reference="AUDIT-IMMUTABLE",
        client_id=client.id,
        branch_id=branch.id,
        direction=JobDirection.IMPORT,
        mode=JobMode.AIR,
        now=NOW,
    )
    session.commit()
    event = session.scalar(
        select(AuditEvent).where(
            AuditEvent.job_id == job.id,
            AuditEvent.action == "job.created",
        )
    )
    assert event is not None
    session.delete(event)

    with pytest.raises(RuntimeError, match="append-only"):
        session.flush()
