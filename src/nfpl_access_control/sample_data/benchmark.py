"""Lightweight streaming generator for the large benchmark dataset.

Targets 500 employees and 200,000 jobs by default. Rows are yielded lazily and
written straight to disk so peak memory stays flat regardless of job count.
History tables are intentionally minimal here (one version + responsibilities
per job) to keep generation fast and file sizes predictable; the standard
dataset carries the rich history and edge cases.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from nfpl_access_control.sample_data import reference as ref
from nfpl_access_control.sample_data.reference import stable_id

EPOCH = datetime(2025, 1, 6, 9, 0, 0, tzinfo=UTC)
_ADMIN_ID = stable_id("user", "bench-admin")


def _ts(minutes: int) -> str:
    return (EPOCH + timedelta(minutes=minutes)).isoformat()


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    branches: int = 10
    clients: int = 200
    employees: int = 500
    jobs: int = 200_000


def _branches(config: BenchmarkConfig) -> Iterator[dict]:
    for index in range(config.branches):
        code = f"BR{index + 1:03d}"
        yield {
            "id": stable_id("bench-branch", code),
            "code": code,
            "name": f"Benchmark Branch {index + 1}",
            "created_at": _ts(0),
            "updated_at": _ts(0),
        }


def _clients(config: BenchmarkConfig) -> Iterator[dict]:
    for index in range(config.clients):
        code = f"CL{index + 1:05d}"
        yield {
            "id": stable_id("bench-client", code),
            "code": code,
            "name": f"Benchmark Client {index + 1}",
            "created_at": _ts(0),
            "updated_at": _ts(0),
        }


def _users(config: BenchmarkConfig) -> Iterator[dict]:
    yield {
        "id": _ADMIN_ID,
        "email": "bench-admin@nfpl.test",
        "display_name": "Benchmark Admin",
        "kind": "staff",
        "is_active": True,
        "account_status": "active",
        "branch_id": stable_id("bench-branch", "BR001"),
        "availability": "available",
        "created_at": _ts(0),
        "updated_at": _ts(0),
    }
    for index in range(config.employees):
        # Deterministic availability spread (~10% busy, ~5% absent).
        availability = "available"
        if index % 10 == 3:
            availability = "busy"
        elif index % 20 == 7:
            availability = "absent"
        branch = index % config.branches
        yield {
            "id": stable_id("bench-user", index),
            "email": f"bench-emp-{index:05d}@nfpl.test",
            "display_name": f"Benchmark Employee {index + 1}",
            "kind": "staff",
            "is_active": True,
            "account_status": "active",
            "branch_id": stable_id("bench-branch", f"BR{branch + 1:03d}"),
            "availability": availability,
            "created_at": _ts(0),
            "updated_at": _ts(0),
        }


def _role_assignments(config: BenchmarkConfig) -> Iterator[dict]:
    # Global admin.
    yield _assignment_row(_ADMIN_ID, "admin", 0, all_branches=True, branch_id=None)
    # Three branch-scoped operational grants per employee. This keeps every
    # generated responsibility eligible while still exercising scoped joins.
    roles = ("maker", "checker", "filing-officer")
    for index in range(config.employees):
        branch = index % config.branches
        for role_index, slug in enumerate(roles):
            yield _assignment_row(
                stable_id("bench-user", index),
                slug,
                index * len(roles) + role_index,
                all_branches=False,
                branch_id=stable_id("bench-branch", f"BR{branch + 1:03d}"),
            )


def _assignment_row(
    user_id: str, slug: str, seq: int, *, all_branches: bool, branch_id: str | None
) -> dict:
    return {
        "id": stable_id("bench-assignment", user_id, slug, seq),
        "user_id": user_id,
        "role_id": ref.role_id(slug),
        "client_id": None,
        "all_clients": True,
        "branch_id": branch_id,
        "all_branches": all_branches,
        "direction": None,
        "all_directions": True,
        "mode": None,
        "all_modes": True,
        "valid_from": _ts(0),
        "valid_until": None,
        "revoked_at": None,
        "granted_by_user_id": _ADMIN_ID,
        "revoked_by_user_id": None,
        "grant_reason": "Benchmark scoped grant.",
        "revoke_reason": None,
        "version": 1,
        "created_at": _ts(0),
        "updated_at": _ts(0),
    }


def _responsible_user_indices(config: BenchmarkConfig, index: int) -> tuple[int, int, int]:
    branch = index % config.branches
    branch_staff = list(range(branch, config.employees, config.branches))
    if len(branch_staff) < 3:
        raise ValueError("benchmark mode needs at least three employees per branch")
    return tuple(branch_staff[(index + offset) % len(branch_staff)] for offset in range(3))


def _job_row(config: BenchmarkConfig, index: int) -> dict:
    branch = index % config.branches
    client = index % config.clients
    direction = ref.JOB_DIRECTION[index % 2]
    mode = ref.JOB_MODE[index % 3]
    stage = ("confirmed", "prepared", "checked", "filed")[index % 4]
    maker_index, checker_index, filer_index = _responsible_user_indices(config, index)
    recorded = index % 100000
    is_prepared = stage in ("prepared", "checked", "filed")
    is_checked = stage in ("checked", "filed")
    is_filed = stage == "filed"
    return {
        "id": stable_id("bench-job", index),
        "reference": f"BENCH-{index + 1:08d}",
        "client_id": stable_id("bench-client", f"CL{client + 1:05d}"),
        "branch_id": stable_id("bench-branch", f"BR{branch + 1:03d}"),
        "direction": direction,
        "mode": mode,
        "stage": stage,
        "assignee_id": stable_id("bench-user", maker_index),
        "version": 1,
        "goods_description": f"Benchmark consignment {index + 1}.",
        "container_reference": None if mode == "air" else f"BCONT-{index + 1:08d}",
        "checklist_data": {"benchmark": True} if is_prepared else {},
        "checklist_revision": 1 if is_prepared else 0,
        "maker_edit_locked": is_prepared,
        "maker_correction_required": False,
        "checker_correction_required": False,
        "last_return_category": None,
        "last_return_reason": None,
        "last_maker_justification": None,
        "last_checker_justification": None,
        "prepared_by_user_id": stable_id("bench-user", maker_index) if is_prepared else None,
        "prepared_at": _ts(recorded) if is_prepared else None,
        "checked_by_user_id": stable_id("bench-user", checker_index) if is_checked else None,
        "checked_at": _ts(recorded) if is_checked else None,
        "filed_by_user_id": stable_id("bench-user", filer_index) if is_filed else None,
        "filed_at": _ts(recorded) if is_filed else None,
        "archived_at": None,
        "archived_by_user_id": None,
        "archive_reason": None,
        "created_at": _ts(recorded),
        "updated_at": _ts(recorded),
    }


def _jobs(config: BenchmarkConfig) -> Iterator[dict]:
    for index in range(config.jobs):
        yield _job_row(config, index)


def _responsibilities(config: BenchmarkConfig) -> Iterator[dict]:
    responsibilities = ("maker", "checker", "filing_officer")
    for index in range(config.jobs):
        job_id = stable_id("bench-job", index)
        responsible_users = _responsible_user_indices(config, index)
        # Three distinct, branch-scoped staff per job.
        for offset, responsibility in enumerate(responsibilities):
            user_index = responsible_users[offset]
            yield {
                "id": stable_id("bench-resp", index, responsibility),
                "job_id": job_id,
                "responsibility": responsibility,
                "user_id": stable_id("bench-user", user_index),
                "assigned_by_user_id": _ADMIN_ID,
                "assigned_at": _ts(index % 100000),
                "version": 1,
            }


def _job_versions(config: BenchmarkConfig) -> Iterator[dict]:
    for index in range(config.jobs):
        job = _job_row(config, index)
        snapshot = {
            key: job[key]
            for key in (
                "id",
                "reference",
                "client_id",
                "branch_id",
                "direction",
                "mode",
                "stage",
                "goods_description",
                "container_reference",
                "checklist_data",
                "checklist_revision",
                "maker_edit_locked",
                "maker_correction_required",
                "checker_correction_required",
                "last_return_category",
                "last_return_reason",
                "last_maker_justification",
                "last_checker_justification",
                "prepared_by_user_id",
                "checked_by_user_id",
                "filed_by_user_id",
                "archived_at",
                "archived_by_user_id",
                "archive_reason",
                "version",
            )
        }
        yield {
            "id": stable_id("bench-jobver", index),
            "job_id": stable_id("bench-job", index),
            "version_number": 1,
            "recorded_at": _ts(index % 100000),
            "actor_user_id": _ADMIN_ID,
            "action": "benchmark.snapshot",
            "reason": "Minimal complete benchmark snapshot.",
            "snapshot": snapshot,
        }


BENCHMARK_STREAMS = {
    "branches": _branches,
    "clients": _clients,
    "users": _users,
    "role_assignments": _role_assignments,
    "jobs": _jobs,
    "job_responsibilities": _responsibilities,
    "job_versions": _job_versions,
}


def expected_counts(config: BenchmarkConfig) -> dict[str, int]:
    return {
        "branches": config.branches,
        "clients": config.clients,
        "users": config.employees + 1,
        "role_assignments": config.employees * 3 + 1,
        "jobs": config.jobs,
        "job_responsibilities": config.jobs * 3,
        "job_versions": config.jobs,
    }
