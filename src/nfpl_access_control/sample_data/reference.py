"""Schema reference data mirrored from the NFPL access-control project.

This module is deliberately decoupled from the application package so the
generator runs with the standard library alone (no SQLAlchemy, no project
install required). Every constant here mirrors the authoritative source in
``src/nfpl_access_control`` and is cross-checked by the test suite when the
project happens to be importable:

* enum values  -> ``models/enums.py``
* system roles -> ``authorization/roles.py`` / migration ``0002``
* column names -> ``models/*.py``

If the project schema changes, update the mirrors here and the drift tests
will confirm they match again. This file never performs database work.
"""

from __future__ import annotations

import uuid

# Fixed namespace so every id is a pure function of its stable natural key.
# Regenerating with the same inputs always yields byte-identical ids.
NAMESPACE = uuid.UUID("5f9b4d2e-0000-5000-a000-6e66706c0001")


def stable_id(*parts: object) -> str:
    """Return a deterministic UUID string (36 chars) for the given key parts."""

    key = "|".join(str(part) for part in parts)
    return str(uuid.uuid5(NAMESPACE, key))


# --- Closed domain values (mirror of models/enums.py) ------------------------

USER_KIND = ("staff", "client", "service")
ACCOUNT_STATUS = ("pending", "active", "disabled")
EMPLOYEE_AVAILABILITY = ("available", "busy", "absent")
JOB_DIRECTION = ("import", "export")
JOB_MODE = ("air", "fcl", "lcl")
JOB_STAGE = ("confirmed", "prepared", "checked", "filed", "cancelled", "reopened")
CHECKLIST_ITEM_STATUS = ("complete", "incomplete", "not_applicable")
FILING_RETURN_CATEGORY = ("maker_fault", "checker_fault", "both")
EDIT_REQUEST_STATUS = ("pending", "approved", "denied", "consumed")
ABSENCE_NOMINATION_STATUS = ("pending", "approved", "rejected", "revoked")
ABSENCE_JOB_OUTCOME = ("delegated", "ineligible", "conflict", "overridden")
ASSIGNMENT_EVENT_TYPE = ("granted", "revoked")
RESPONSIBILITY_TYPE = ("maker", "checker", "filing_officer")
RESPONSIBILITY_EVENT_TYPE = (
    "assigned",
    "reassigned",
    "unassigned",
    "delegated",
    "delegation_revoked",
)
EXCEPTIONAL_ACTION = ("cancel", "reopen")
EXCEPTIONAL_REQUEST_STATUS = ("pending", "approved", "denied", "executed")

PERMISSION = (
    "job:view",
    "job:create",
    "job:update",
    "job:prepare",
    "job:check",
    "job:file",
    "job:cancel",
    "job:reopen",
    "client_history:view",
    "access:grant",
    "access:revoke",
    "role:manage",
)


# --- System roles (mirror of authorization/roles.py & migration 0002) --------
# role_assignment rows reference these ids; the roles themselves are installed
# by Alembic migration 0002, so the generator never emits role rows for insert.

SYSTEM_ROLES = {
    "maker": {
        "id": "00000000-0000-4000-8000-000000000101",
        "name": "Maker",
        "permissions": ("job:view", "job:prepare"),
    },
    "checker": {
        "id": "00000000-0000-4000-8000-000000000102",
        "name": "Checker",
        "permissions": ("job:view", "job:check"),
    },
    "filing-officer": {
        "id": "00000000-0000-4000-8000-000000000103",
        "name": "Filing Officer",
        "permissions": ("job:view", "job:file"),
    },
    "admin": {
        "id": "00000000-0000-4000-8000-000000000104",
        "name": "Admin",
        "permissions": PERMISSION,
    },
    "client-viewer": {
        "id": "00000000-0000-4000-8000-000000000105",
        "name": "Client Viewer",
        "permissions": ("job:view", "client_history:view"),
    },
    "parser-service": {
        "id": "00000000-0000-4000-8000-000000000106",
        "name": "Parser Service",
        "permissions": ("job:view", "job:create", "job:update"),
    },
}


def role_id(slug: str) -> str:
    return SYSTEM_ROLES[slug]["id"]


# --- Column orders (mirror of models/*.py) -----------------------------------
# Used for stable CSV headers and for the schema-conformance test. Order follows
# the model definitions so output diffs stay readable across regenerations.

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "branches": ("id", "code", "name", "created_at", "updated_at"),
    "clients": ("id", "code", "name", "created_at", "updated_at"),
    "users": (
        "id",
        "email",
        "display_name",
        "kind",
        "is_active",
        "account_status",
        "branch_id",
        "availability",
        "created_at",
        "updated_at",
    ),
    "account_state_events": (
        "id",
        "user_id",
        "previous_status",
        "status",
        "effective_at",
        "actor_user_id",
        "reason",
    ),
    "user_availability_events": (
        "id",
        "user_id",
        "previous_availability",
        "availability",
        "effective_at",
        "actor_user_id",
        "reason",
    ),
    "role_assignments": (
        "id",
        "user_id",
        "role_id",
        "client_id",
        "all_clients",
        "branch_id",
        "all_branches",
        "direction",
        "all_directions",
        "mode",
        "all_modes",
        "valid_from",
        "valid_until",
        "revoked_at",
        "granted_by_user_id",
        "revoked_by_user_id",
        "grant_reason",
        "revoke_reason",
        "version",
        "created_at",
        "updated_at",
    ),
    "role_assignment_events": (
        "id",
        "assignment_id",
        "event_type",
        "actor_user_id",
        "occurred_at",
        "reason",
    ),
    "jobs": (
        "id",
        "reference",
        "client_id",
        "branch_id",
        "direction",
        "mode",
        "stage",
        "assignee_id",
        "version",
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
        "prepared_at",
        "checked_by_user_id",
        "checked_at",
        "filed_by_user_id",
        "filed_at",
        "archived_at",
        "archived_by_user_id",
        "archive_reason",
        "created_at",
        "updated_at",
    ),
    "job_responsibilities": (
        "id",
        "job_id",
        "responsibility",
        "user_id",
        "assigned_by_user_id",
        "assigned_at",
        "version",
    ),
    "job_responsibility_events": (
        "id",
        "job_id",
        "responsibility",
        "event_type",
        "previous_user_id",
        "new_user_id",
        "actor_user_id",
        "occurred_at",
        "reason",
    ),
    "job_delegations": (
        "id",
        "job_id",
        "responsibility",
        "delegator_user_id",
        "delegate_user_id",
        "valid_from",
        "valid_until",
        "revoked_at",
        "created_by_user_id",
        "reason",
        "absence_nomination_id",
    ),
    "job_edit_requests": (
        "id",
        "job_id",
        "status",
        "requested_by_user_id",
        "requested_at",
        "reason",
        "decided_by_user_id",
        "decided_at",
        "decision_reason",
        "consumed_at",
    ),
    "exceptional_transition_requests": (
        "id",
        "job_id",
        "action",
        "status",
        "requested_by_user_id",
        "requested_at",
        "reason",
        "decided_by_user_id",
        "decided_at",
    ),
    "job_versions": (
        "id",
        "job_id",
        "version_number",
        "recorded_at",
        "actor_user_id",
        "action",
        "reason",
        "snapshot",
    ),
    "audit_events": (
        "id",
        "job_id",
        "actor_user_id",
        "action",
        "occurred_at",
        "reason",
        "before_state",
        "after_state",
        "authorization_context",
        "affected_job_version",
        "denied",
    ),
    "absence_nominations": (
        "id",
        "requester_user_id",
        "nominee_user_id",
        "valid_from",
        "valid_until",
        "reason",
        "status",
        "requested_at",
        "decided_by_user_id",
        "decided_at",
        "decision_reason",
        "revoked_at",
        "version",
    ),
    "absence_nomination_jobs": (
        "id",
        "nomination_id",
        "job_id",
        "responsibility",
        "nominee_user_id",
        "outcome",
        "reason",
        "delegation_id",
    ),
    "notifications": (
        "id",
        "recipient_user_id",
        "job_id",
        "job_reference",
        "event_type",
        "message",
        "target_path",
        "dedupe_key",
        "created_at",
        "read_at",
        "is_client_safe",
    ),
}

# JSON columns are embedded as objects in JSON output and as compact JSON
# strings in CSV output.
JSON_COLUMNS = frozenset(
    {"checklist_data", "snapshot", "before_state", "after_state", "authorization_context"}
)
