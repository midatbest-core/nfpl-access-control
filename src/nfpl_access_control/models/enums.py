"""Closed domain values persisted as portable strings."""

from enum import StrEnum


class UserKind(StrEnum):
    STAFF = "staff"
    CLIENT = "client"
    SERVICE = "service"


class AccountStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class EmployeeAvailability(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    ABSENT = "absent"


class JobDirection(StrEnum):
    IMPORT = "import"
    EXPORT = "export"


class JobMode(StrEnum):
    AIR = "air"
    FCL = "fcl"
    LCL = "lcl"


class JobStage(StrEnum):
    CONFIRMED = "confirmed"
    PREPARED = "prepared"
    CHECKED = "checked"
    FILED = "filed"
    CANCELLED = "cancelled"
    REOPENED = "reopened"


class ChecklistItemStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NOT_APPLICABLE = "not_applicable"


class FilingReturnCategory(StrEnum):
    MAKER_FAULT = "maker_fault"
    CHECKER_FAULT = "checker_fault"
    BOTH = "both"


class EditRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CONSUMED = "consumed"


class AbsenceNominationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class AbsenceJobOutcome(StrEnum):
    DELEGATED = "delegated"
    INELIGIBLE = "ineligible"
    CONFLICT = "conflict"
    OVERRIDDEN = "overridden"


class Permission(StrEnum):
    JOB_VIEW = "job:view"
    JOB_CREATE = "job:create"
    JOB_UPDATE = "job:update"
    JOB_PREPARE = "job:prepare"
    JOB_CHECK = "job:check"
    JOB_FILE = "job:file"
    JOB_CANCEL = "job:cancel"
    JOB_REOPEN = "job:reopen"
    CLIENT_HISTORY_VIEW = "client_history:view"
    ACCESS_GRANT = "access:grant"
    ACCESS_REVOKE = "access:revoke"
    ROLE_MANAGE = "role:manage"


class AssignmentEventType(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"


class ResponsibilityType(StrEnum):
    MAKER = "maker"
    CHECKER = "checker"
    FILING_OFFICER = "filing_officer"


class ResponsibilityEventType(StrEnum):
    ASSIGNED = "assigned"
    REASSIGNED = "reassigned"
    UNASSIGNED = "unassigned"
    DELEGATED = "delegated"
    DELEGATION_REVOKED = "delegation_revoked"


class ExceptionalAction(StrEnum):
    CANCEL = "cancel"
    REOPEN = "reopen"


class ExceptionalRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTED = "executed"
