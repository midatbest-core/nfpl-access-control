"""Deterministic builder for the standard NFPL sample dataset.

Produces fictional, internally consistent rows for every access-control table
so the full authorization story can be exercised: overlapping scoped roles,
time-limited / revoked / not-yet-effective grants, Busy and Absent staff,
absence-driven delegation with every outcome, correction and return flows,
exceptional transitions, append-only history, and client/parser identities.

The builder is pure: given the same :class:`DatasetConfig` it returns
byte-identical rows. All ids derive from stable natural keys and all timestamps
derive from a fixed epoch, so no wall-clock or RNG state leaks in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from nfpl_access_control.sample_data import reference as ref
from nfpl_access_control.sample_data.reference import stable_id

# Fixed reference instant. Every generated timestamp is this plus a
# deterministic offset, and is always serialized with an explicit UTC offset
# because the model's UtcDateTime rejects naive datetimes.
EPOCH = datetime(2025, 1, 6, 9, 0, 0, tzinfo=UTC)


def _ts(minutes: int) -> str:
    return (EPOCH + timedelta(minutes=minutes)).isoformat()


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    branches: int = 5
    clients: int = 10
    employees: int = 20
    jobs: int = 420
    client_viewers: int = 10

    def validate(self) -> None:
        if not 300 <= self.jobs <= 500:
            raise ValueError("standard dataset expects 300-500 jobs; use benchmark mode for more")
        if self.branches < 1 or self.clients < 1 or self.employees < 6:
            raise ValueError("need at least 1 branch, 1 client, and 6 employees")


@dataclass
class Dataset:
    tables: dict[str, list[dict]] = field(default_factory=dict)
    edge_cases: list[str] = field(default_factory=list)

    def add(self, table: str, row: dict) -> dict:
        self.tables.setdefault(table, []).append(row)
        return row

    def note(self, label: str) -> None:
        if label not in self.edge_cases:
            self.edge_cases.append(label)


class DatasetBuilder:
    """Build the standard dataset in a fixed, reproducible order."""

    def __init__(self, config: DatasetConfig | None = None) -> None:
        self.config = config or DatasetConfig()
        self.config.validate()
        self.ds = Dataset()
        self.branches: list[dict] = []
        self.clients: list[dict] = []
        self.employees: list[dict] = []
        self.admin: dict = {}

    def build(self) -> Dataset:
        self._build_branches()
        self._build_clients()
        self._build_admin()
        self._build_employees()
        self._build_client_and_service_users()
        self._build_role_assignments()
        self._build_jobs()
        self._build_absence_flows()
        return self.ds

    # -- reference data -------------------------------------------------------

    def _build_branches(self) -> None:
        names = [
            "Mumbai Head Office",
            "Nhava Sheva Port",
            "Delhi ICD",
            "Chennai Seaport",
            "Bengaluru Air Cargo",
            "Kolkata Port",
            "Ahmedabad ICD",
            "Cochin Port",
        ]
        for index in range(self.config.branches):
            code = f"BR{index + 1:02d}"
            name = names[index % len(names)]
            self.branches.append(
                self.ds.add(
                    "branches",
                    {
                        "id": stable_id("branch", code),
                        "code": code,
                        "name": name,
                        "created_at": _ts(index),
                        "updated_at": _ts(index),
                    },
                )
            )

    def _build_clients(self) -> None:
        names = [
            "Oriana Textiles",
            "Harbour Pharma",
            "Meridian Auto Parts",
            "Saffron Spices Export",
            "Blue Lotus Electronics",
            "Deccan Steel",
            "Coral Reef Seafoods",
            "Summit Machinery",
            "Verdant Agro",
            "Lighthouse Chemicals",
            "Aster Garments",
            "Zenith Polymers",
        ]
        for index in range(self.config.clients):
            code = f"CL{index + 1:03d}"
            name = names[index % len(names)]
            self.clients.append(
                self.ds.add(
                    "clients",
                    {
                        "id": stable_id("client", code),
                        "code": code,
                        "name": name,
                        "created_at": _ts(index),
                        "updated_at": _ts(index),
                    },
                )
            )

    # -- identities -----------------------------------------------------------

    def _new_user(
        self,
        *,
        key: str,
        email: str,
        display_name: str,
        kind: str,
        branch_id: str | None,
        account_status: str,
        availability: str,
        is_active: bool,
        created_minute: int,
    ) -> dict:
        return self.ds.add(
            "users",
            {
                "id": stable_id("user", key),
                "email": email.lower(),
                "display_name": display_name,
                "kind": kind,
                "is_active": is_active,
                "account_status": account_status,
                "branch_id": branch_id,
                "availability": availability,
                "created_at": _ts(created_minute),
                "updated_at": _ts(created_minute),
            },
        )

    def _account_event(
        self, user: dict, previous: str | None, status: str, actor_id: str, minute: int, reason: str
    ) -> None:
        self.ds.add(
            "account_state_events",
            {
                "id": stable_id("acct-event", user["id"], status, minute),
                "user_id": user["id"],
                "previous_status": previous,
                "status": status,
                "effective_at": _ts(minute),
                "actor_user_id": actor_id,
                "reason": reason,
            },
        )

    def _availability_event(
        self, user: dict, previous: str, availability: str, actor_id: str, minute: int, reason: str
    ) -> None:
        self.ds.add(
            "user_availability_events",
            {
                "id": stable_id("avail-event", user["id"], availability, minute),
                "user_id": user["id"],
                "previous_availability": previous,
                "availability": availability,
                "effective_at": _ts(minute),
                "actor_user_id": actor_id,
                "reason": reason,
            },
        )

    def _build_admin(self) -> None:
        branch = self.branches[0]
        self.admin = self._new_user(
            key="admin",
            email="admin@nfpl.test",
            display_name="Nadia Admin",
            kind="staff",
            branch_id=branch["id"],
            account_status="active",
            availability="available",
            is_active=True,
            created_minute=0,
        )
        self._account_event(
            self.admin,
            None,
            "active",
            self.admin["id"],
            0,
            "Trusted one-time first-Admin bootstrap.",
        )

    def _build_employees(self) -> None:
        first = [
            "Aarav",
            "Diya",
            "Kabir",
            "Isha",
            "Vivaan",
            "Anaya",
            "Reyansh",
            "Myra",
            "Arjun",
            "Sara",
            "Vihaan",
            "Kiara",
            "Advait",
            "Zara",
            "Rohan",
            "Nisha",
            "Dev",
            "Tara",
            "Krish",
            "Aisha",
        ]
        last = [
            "Shah",
            "Nair",
            "Rao",
            "Menon",
            "Gupta",
            "Iyer",
            "Khan",
            "Patel",
            "Das",
            "Reddy",
            "Bose",
            "Joshi",
            "Verma",
            "Pillai",
            "Sinha",
            "Kaur",
            "Mehta",
            "Ghosh",
            "Banerjee",
            "Roy",
        ]
        count = self.config.employees
        # Availability edge cases: 2 busy, 2 absent, rest available.
        busy = {4, 11}
        absent = {7, 15}
        # One disabled account to exercise revoked-credential semantics.
        disabled = {18}
        for index in range(count):
            branch = self.branches[index % self.config.branches]
            key = f"emp-{index:02d}"
            name = f"{first[index % len(first)]} {last[index % len(last)]}"
            availability = "available"
            if index in busy:
                availability = "busy"
            elif index in absent:
                availability = "absent"
            status = "disabled" if index in disabled else "active"
            minute = 10 + index
            user = self._new_user(
                key=key,
                email=f"{key}@nfpl.test",
                display_name=name,
                kind="staff",
                branch_id=branch["id"],
                account_status=status,
                availability=availability,
                is_active=status != "disabled",
                created_minute=minute,
            )
            self.employees.append(user)
            # Account lifecycle history: pending -> active (-> disabled).
            self._account_event(
                user,
                None,
                "pending",
                self.admin["id"],
                minute,
                "Employee self-registration pending approval.",
            )
            self._account_event(
                user,
                "pending",
                "active",
                self.admin["id"],
                minute + 1,
                "Admin approved employee account.",
            )
            if status == "disabled":
                self._account_event(
                    user,
                    "active",
                    "disabled",
                    self.admin["id"],
                    minute + 2,
                    "Admin deactivated account; sessions revoked.",
                )
                self.ds.note("disabled employee account with append-only state history")
            if availability == "busy":
                self._availability_event(
                    user,
                    "available",
                    "busy",
                    user["id"],
                    minute + 3,
                    "Employee marked Busy; excluded from suggestions.",
                )
                self.ds.note("Busy employee excluded from assignment suggestions")
            if availability == "absent":
                self._availability_event(
                    user,
                    "available",
                    "absent",
                    user["id"],
                    minute + 3,
                    "Employee marked Absent; cannot act or receive work.",
                )
                self.ds.note("Absent employee cannot act or receive new assignments")

    def _build_client_and_service_users(self) -> None:
        for index in range(min(self.config.client_viewers, self.config.clients)):
            client = self.clients[index]
            key = f"client-viewer-{index:02d}"
            self._new_user(
                key=key,
                email=f"{key}@portal.test",
                display_name=f"{client['name']} Portal",
                kind="client",
                branch_id=None,
                account_status="active",
                availability="available",
                is_active=True,
                created_minute=40 + index,
            )
        self.ds.note("Client Viewer identities for sanitized client-facing views")
        self._new_user(
            key="parser-service",
            email="parser-service@nfpl.test",
            display_name="Parser Service Account",
            kind="service",
            branch_id=None,
            account_status="active",
            availability="available",
            is_active=True,
            created_minute=60,
        )
        self.ds.note("Parser Service identity limited to view/create/update")

    # -- role assignments -----------------------------------------------------

    def _assignment(
        self,
        *,
        user: dict,
        slug: str,
        minute: int,
        all_clients=True,
        client_id=None,
        all_branches=True,
        branch_id=None,
        all_directions=True,
        direction=None,
        all_modes=True,
        mode=None,
        valid_until_min=None,
        revoked_min=None,
        reason="Scoped operational grant.",
    ) -> dict:
        # ``minute`` is the grant's valid_from and keeps every assignment id
        # distinct even when scope and role repeat for one employee.
        key = (user["id"], slug, client_id, branch_id, direction, mode, minute)
        assignment = self.ds.add(
            "role_assignments",
            {
                "id": stable_id("assignment", *key),
                "user_id": user["id"],
                "role_id": ref.role_id(slug),
                "client_id": client_id,
                "all_clients": all_clients,
                "branch_id": branch_id,
                "all_branches": all_branches,
                "direction": direction,
                "all_directions": all_directions,
                "mode": mode,
                "all_modes": all_modes,
                "valid_from": _ts(minute),
                "valid_until": _ts(valid_until_min) if valid_until_min is not None else None,
                "revoked_at": _ts(revoked_min) if revoked_min is not None else None,
                "granted_by_user_id": self.admin["id"],
                "revoked_by_user_id": self.admin["id"] if revoked_min is not None else None,
                "grant_reason": reason,
                "revoke_reason": "Access no longer required." if revoked_min is not None else None,
                "version": 1,
                "created_at": _ts(minute),
                "updated_at": _ts(revoked_min if revoked_min is not None else minute),
            },
        )
        self.ds.add(
            "role_assignment_events",
            {
                "id": stable_id("assign-event", assignment["id"], "granted"),
                "assignment_id": assignment["id"],
                "event_type": "granted",
                "actor_user_id": self.admin["id"],
                "occurred_at": _ts(minute),
                "reason": reason,
            },
        )
        if revoked_min is not None:
            self.ds.add(
                "role_assignment_events",
                {
                    "id": stable_id("assign-event", assignment["id"], "revoked"),
                    "assignment_id": assignment["id"],
                    "event_type": "revoked",
                    "actor_user_id": self.admin["id"],
                    "occurred_at": _ts(revoked_min),
                    "reason": "Access no longer required.",
                },
            )
        return assignment

    def _build_role_assignments(self) -> None:
        # Global Admin (the bootstrapped first admin).
        self._assignment(
            user=self.admin,
            slug="admin",
            minute=100,
            reason="Trusted one-time first-Admin bootstrap.",
        )

        emp = self.employees
        future = 10_000_000  # far-future minute -> not-yet-effective / open end
        past_end = 50  # valid_until already elapsed -> expired

        # Stable demonstration identities used by API smoke tests and the
        # assignment fallback. Employee 0 is a global Maker whose Checker role
        # is limited to one client. Employee 1 demonstrates the stricter
        # client + branch + import-only Checker scope.
        self._assignment(
            user=emp[0],
            slug="maker",
            minute=100,
            reason="Global Maker coverage for demonstration jobs.",
        )
        self._assignment(
            user=emp[0],
            slug="checker",
            minute=101,
            all_clients=False,
            client_id=self.clients[0]["id"],
            reason="Checker access limited to selected client CL001.",
        )
        self._assignment(
            user=emp[1],
            slug="checker",
            minute=102,
            all_clients=False,
            client_id=self.clients[0]["id"],
            all_branches=False,
            branch_id=self.branches[0]["id"],
            all_directions=False,
            direction="import",
            reason="Checker limited to CL001, BR01, and import shipments.",
        )
        self._assignment(
            user=emp[2],
            slug="filing-officer",
            minute=103,
            reason="Global Filing Officer coverage for demonstration jobs.",
        )
        self._assignment(
            user=emp[3],
            slug="checker",
            minute=104,
            reason="Global Checker coverage for demonstration jobs.",
        )
        self._assignment(
            user=emp[10],
            slug="checker",
            minute=105,
            reason="Independent global Checker fallback for overlapping roles.",
        )

        # Remaining staff receive branch-scoped operational duties.
        for index, user in enumerate(emp[4:], start=4):
            if user["account_status"] == "disabled":
                continue
            branch = self.branches[index % self.config.branches]
            role_cycle = index % 3
            base_slug = ("maker", "checker", "filing-officer")[role_cycle]
            self._assignment(
                user=user,
                slug=base_slug,
                minute=100 + index,
                all_branches=False,
                branch_id=branch["id"],
                reason=f"{base_slug} duty for {branch['code']}.",
            )

        # Overlapping Maker scopes on top of emp[0]'s global grant.
        self._assignment(
            user=emp[0],
            slug="maker",
            minute=120,
            all_clients=False,
            client_id=self.clients[0]["id"],
            reason="Maker for key client CL001 across all branches.",
        )
        self._assignment(
            user=emp[0],
            slug="maker",
            minute=121,
            all_branches=False,
            branch_id=self.branches[0]["id"],
            reason="Maker for branch BR01 across all clients.",
        )
        self.ds.note("Overlapping scoped role assignments on the same employee")

        # Multi-role employee: emp[1] is also a Filing Officer in BR02.
        self._assignment(
            user=emp[1],
            slug="filing-officer",
            minute=122,
            all_branches=False,
            branch_id=self.branches[1]["id"],
            reason="Secondary Filing Officer coverage.",
        )
        self.ds.note("Employee holding multiple distinct operational roles")

        # Direction/mode narrowed secondary grant.
        self._assignment(
            user=emp[5],
            slug="checker",
            minute=123,
            all_directions=False,
            direction="import",
            all_modes=False,
            mode="air",
            reason="Checker limited to import air shipments.",
        )
        self._assignment(
            user=emp[6],
            slug="checker",
            minute=125,
            all_branches=False,
            branch_id=self.branches[1]["id"],
            reason="BR02 Checker cover used by the absence-conflict demonstration.",
        )
        self.ds.note("Direction- and mode-narrowed scoped grant")

        # Time-limited (still active) grant with an explicit end date.
        self._assignment(
            user=emp[3],
            slug="maker",
            minute=124,
            valid_until_min=future,
            reason="Temporary maker cover with explicit end date.",
        )
        self.ds.note("Time-limited grant with explicit valid_until")

        # Expired grant: valid_until already in the past.
        self._assignment(
            user=emp[5],
            slug="checker",
            minute=5,
            valid_until_min=past_end,
            reason="Short-term checker cover (now expired).",
        )
        self.ds.note("Expired grant (valid_until elapsed)")

        # Revoked grant with a revocation event.
        self._assignment(
            user=emp[6],
            slug="filing-officer",
            minute=110,
            revoked_min=200,
            reason="Filing cover, later revoked.",
        )
        self.ds.note("Revoked grant with append-only revocation event")

        # Not-yet-effective grant scheduled to start in the future.
        self._assignment(
            user=emp[9], slug="maker", minute=future, reason="Scheduled future maker onboarding."
        )
        self.ds.note("Not-yet-effective grant (future valid_from)")

        # A second independently granted Admin can approve exceptional
        # requests made by the bootstrap Admin without self-approval.
        self._assignment(
            user=emp[19],
            slug="admin",
            minute=150,
            reason="Independent operational Admin approved by the bootstrap Admin.",
        )

        # Client Viewer grants: one per client-viewer user, scoped to its client.
        for index in range(min(self.config.client_viewers, self.config.clients)):
            client = self.clients[index]
            viewer = {"id": stable_id("user", f"client-viewer-{index:02d}")}
            self._assignment(
                user=viewer,
                slug="client-viewer",
                minute=130 + index,
                all_clients=False,
                client_id=client["id"],
                reason=f"Sanitized visibility for client {client['code']}.",
            )

        # Parser Service grant (view/create/update across all scope).
        parser = {"id": stable_id("user", "parser-service")}
        self._assignment(
            user=parser,
            slug="parser-service",
            minute=140,
            reason="Automated parser ingest of shipment jobs.",
        )

    # -- jobs -----------------------------------------------------------------

    def _eligible_staff(
        self,
        *,
        slug: str,
        client_id: str,
        branch_id: str,
        direction: str,
        mode: str,
        minute: int,
        exclude_ids: set[str],
    ) -> list[dict]:
        role = ref.role_id(slug)
        users_by_id = {user["id"]: user for user in self.employees}
        eligible: dict[str, dict] = {}
        at = _ts(minute)
        for grant in self.ds.tables["role_assignments"]:
            user = users_by_id.get(grant["user_id"])
            if user is None or grant["role_id"] != role or user["id"] in exclude_ids:
                continue
            if user["account_status"] != "active" or user["availability"] == "absent":
                continue
            if grant["valid_from"] > at:
                continue
            if grant["valid_until"] is not None and grant["valid_until"] <= at:
                continue
            if grant["revoked_at"] is not None and grant["revoked_at"] <= at:
                continue
            if not grant["all_clients"] and grant["client_id"] != client_id:
                continue
            if not grant["all_branches"] and grant["branch_id"] != branch_id:
                continue
            if not grant["all_directions"] and grant["direction"] != direction:
                continue
            if not grant["all_modes"] and grant["mode"] != mode:
                continue
            eligible[user["id"]] = user
        return sorted(eligible.values(), key=lambda user: user["id"])

    def _responsibility(
        self, job: dict, responsibility: str, user: dict | None, minute: int
    ) -> None:
        self.ds.add(
            "job_responsibilities",
            {
                "id": stable_id("resp", job["id"], responsibility),
                "job_id": job["id"],
                "responsibility": responsibility,
                "user_id": user["id"] if user else None,
                "assigned_by_user_id": self.admin["id"],
                "assigned_at": _ts(minute),
                "version": 1,
            },
        )
        self.ds.add(
            "job_responsibility_events",
            {
                "id": stable_id("resp-event", job["id"], responsibility, "assigned"),
                "job_id": job["id"],
                "responsibility": responsibility,
                "event_type": "assigned",
                "previous_user_id": None,
                "new_user_id": user["id"] if user else None,
                "actor_user_id": self.admin["id"],
                "occurred_at": _ts(minute),
                "reason": f"Initial {responsibility} assignment.",
            },
        )

    def _job_version(
        self, job: dict, number: int, actor_id: str, action: str, minute: int, snapshot: dict
    ) -> None:
        full_snapshot = {
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
        full_snapshot.update(snapshot)
        self.ds.add(
            "job_versions",
            {
                "id": stable_id("job-version", job["id"], number),
                "job_id": job["id"],
                "version_number": number,
                "recorded_at": _ts(minute),
                "actor_user_id": actor_id,
                "action": action,
                "reason": f"{action} transition.",
                "snapshot": full_snapshot,
            },
        )

    def _audit(
        self,
        job: dict | None,
        actor_id: str,
        action: str,
        minute: int,
        version: int | None,
        denied: bool = False,
    ) -> None:
        after_state = None
        if job is not None:
            after_state = next(
                (
                    item["snapshot"]
                    for item in reversed(self.ds.tables.get("job_versions", []))
                    if item["job_id"] == job["id"] and item["version_number"] == version
                ),
                None,
            )
        self.ds.add(
            "audit_events",
            {
                "id": stable_id("audit", job["id"] if job else action, action, minute),
                "job_id": job["id"] if job else None,
                "actor_user_id": actor_id,
                "action": action,
                "occurred_at": _ts(minute),
                "reason": f"{action} recorded with authorization recheck.",
                "before_state": None,
                "after_state": after_state,
                "authorization_context": {
                    "action": action,
                    "scope": "job",
                    "allowed": not denied,
                    "reason_code": "allowed" if not denied else "denied",
                },
                "affected_job_version": version,
                "denied": denied,
            },
        )

    def _build_jobs(self) -> None:
        total = self.config.jobs
        for index in range(total):
            client = self.clients[index % self.config.clients]
            branch = self.branches[(index // self.config.clients) % self.config.branches]
            direction = ref.JOB_DIRECTION[index % 2]
            mode = ref.JOB_MODE[index % 3]
            # Distribute across the lifecycle deterministically.
            stage_pick = index % 10
            base_minute = 1000 + index * 3
            job = {
                "id": stable_id("job", index),
                "reference": f"NFPL-{branch['code']}-{index + 1:05d}",
                "client_id": client["id"],
                "branch_id": branch["id"],
                "direction": direction,
                "mode": mode,
                "stage": "confirmed",
                "assignee_id": None,
                "version": 1,
                "goods_description": f"Fictional consignment {index + 1} ({mode}/{direction}).",
                "container_reference": f"CONT-{index + 1:05d}" if mode != "air" else None,
                "checklist_data": {},
                "checklist_revision": 0,
                "maker_edit_locked": False,
                "maker_correction_required": False,
                "checker_correction_required": False,
                "last_return_category": None,
                "last_return_reason": None,
                "last_maker_justification": None,
                "last_checker_justification": None,
                "prepared_by_user_id": None,
                "prepared_at": None,
                "checked_by_user_id": None,
                "checked_at": None,
                "filed_by_user_id": None,
                "filed_at": None,
                "archived_at": None,
                "archived_by_user_id": None,
                "archive_reason": None,
                "created_at": _ts(base_minute),
                "updated_at": _ts(base_minute),
            }
            dimensions = {
                "client_id": client["id"],
                "branch_id": branch["id"],
                "direction": direction,
                "mode": mode,
                "minute": base_minute,
            }
            makers = self._eligible_staff(slug="maker", exclude_ids=set(), **dimensions)
            maker = makers[index % len(makers)]
            checkers = self._eligible_staff(slug="checker", exclude_ids={maker["id"]}, **dimensions)
            checker = checkers[index % len(checkers)]
            filers = self._eligible_staff(
                slug="filing-officer", exclude_ids={maker["id"], checker["id"]}, **dimensions
            )
            filer = filers[index % len(filers)]
            self.ds.add("jobs", job)
            self._responsibility(job, "maker", maker, base_minute)
            self._responsibility(job, "checker", checker, base_minute)
            self._responsibility(job, "filing_officer", filer, base_minute)
            self._job_version(
                job, 1, self.admin["id"], "created", base_minute, {"stage": "confirmed"}
            )
            self._audit(job, self.admin["id"], "job.create", base_minute, 1)
            self._apply_stage(
                job,
                stage_pick,
                maker,
                checker,
                filer,
                base_minute,
                reopen=(index // 10) % 2 == 0,
            )

    def _apply_stage(
        self,
        job: dict,
        pick: int,
        maker: dict,
        checker: dict,
        filer: dict,
        minute: int,
        *,
        reopen: bool = False,
    ) -> None:
        """Advance the job through a deterministic lifecycle slice."""

        def advance(stage: str, version: int, extra: dict, actor: dict, action: str) -> None:
            job.update(extra)
            job["stage"] = stage
            job["version"] = version
            job["updated_at"] = _ts(minute + version)
            self._job_version(job, version, actor["id"], action, minute + version, {"stage": stage})
            self._audit(job, actor["id"], f"job.{action}", minute + version, version)

        job["assignee_id"] = maker["id"]
        if pick == 0:
            return  # stays confirmed
        if pick in (1, 2):
            advance(
                "prepared",
                2,
                {
                    "prepared_by_user_id": maker["id"],
                    "prepared_at": _ts(minute + 2),
                    "maker_edit_locked": True,
                    "checklist_revision": 1,
                    "checklist_data": {"generated": True, "items": 6},
                },
                maker,
                "prepare",
            )
            return
        if pick in (3, 4):
            advance(
                "prepared",
                2,
                {
                    "prepared_by_user_id": maker["id"],
                    "prepared_at": _ts(minute + 2),
                    "maker_edit_locked": True,
                    "checklist_revision": 1,
                    "checklist_data": {"generated": True, "items": 6},
                },
                maker,
                "prepare",
            )
            advance(
                "checked",
                3,
                {
                    "checked_by_user_id": checker["id"],
                    "checked_at": _ts(minute + 3),
                },
                checker,
                "check",
            )
            return
        if pick in (5, 6):
            advance(
                "prepared",
                2,
                {
                    "prepared_by_user_id": maker["id"],
                    "prepared_at": _ts(minute + 2),
                    "maker_edit_locked": True,
                    "checklist_revision": 1,
                    "checklist_data": {"generated": True},
                },
                maker,
                "prepare",
            )
            advance(
                "checked",
                3,
                {"checked_by_user_id": checker["id"], "checked_at": _ts(minute + 3)},
                checker,
                "check",
            )
            advance(
                "filed",
                4,
                {"filed_by_user_id": filer["id"], "filed_at": _ts(minute + 4)},
                filer,
                "file",
            )
            return
        if pick == 7:
            # Filed and then archived (terminal + archived edge case).
            advance(
                "prepared",
                2,
                {
                    "prepared_by_user_id": maker["id"],
                    "prepared_at": _ts(minute + 2),
                    "maker_edit_locked": True,
                },
                maker,
                "prepare",
            )
            advance(
                "checked",
                3,
                {"checked_by_user_id": checker["id"], "checked_at": _ts(minute + 3)},
                checker,
                "check",
            )
            advance(
                "filed",
                4,
                {"filed_by_user_id": filer["id"], "filed_at": _ts(minute + 4)},
                filer,
                "file",
            )
            job["archived_at"] = _ts(minute + 6)
            job["archived_by_user_id"] = self.admin["id"]
            job["archive_reason"] = "Archived after filing per retention policy."
            self._audit(job, self.admin["id"], "job.archive", minute + 6, 4)
            self.ds.note("Filed job archived with reason and audit event")
            return
        if pick == 8:
            # Correction scenario: Filing Officer returns for Maker fault.
            advance(
                "prepared",
                2,
                {
                    "prepared_by_user_id": maker["id"],
                    "prepared_at": _ts(minute + 2),
                    "maker_edit_locked": True,
                },
                maker,
                "prepare",
            )
            advance(
                "checked",
                3,
                {"checked_by_user_id": checker["id"], "checked_at": _ts(minute + 3)},
                checker,
                "check",
            )
            job.update(
                {
                    "maker_correction_required": True,
                    "maker_edit_locked": False,
                    "last_return_category": "maker_fault",
                    "last_return_reason": "HS code mismatch on invoice line 3.",
                }
            )
            advance("prepared", 4, {}, filer, "return_for_correction")
            self._edit_request(job, maker, minute, status="approved")
            self.ds.note("Return-for-correction (maker fault) with correction flags")
            return
        if pick == 9:
            # Admin cancellation of an unfinished job (terminal 'cancelled').
            advance(
                "prepared",
                2,
                {"prepared_by_user_id": maker["id"], "prepared_at": _ts(minute + 2)},
                maker,
                "prepare",
            )
            advance("cancelled", 3, {}, self.admin, "cancel")
            self.ds.note("Admin-cancelled unfinished job (terminal cancelled stage)")
            # Every other cancelled job is reopened via an approved exceptional
            # transition, so both 'cancelled' and 'reopened' terminal states exist.
            if reopen:
                self._exception_request(job, "reopen", minute, status="executed")
                advance(
                    "reopened",
                    4,
                    {
                        "checker_correction_required": True,
                        "last_return_category": "checker_fault",
                        "last_checker_justification": "Re-verify origin certificate.",
                    },
                    self.admin,
                    "reopen",
                )
                self.ds.note("Cancelled job reopened via approved exceptional transition")
            return

    def _edit_request(self, job: dict, maker: dict, minute: int, status: str) -> None:
        self.ds.add(
            "job_edit_requests",
            {
                "id": stable_id("edit-request", job["id"]),
                "job_id": job["id"],
                "status": status,
                "requested_by_user_id": maker["id"],
                "requested_at": _ts(minute + 5),
                "reason": "Request to correct declared value after return.",
                "decided_by_user_id": self.admin["id"] if status != "pending" else None,
                "decided_at": _ts(minute + 6) if status != "pending" else None,
                "decision_reason": "Independent Admin approval."
                if status == "approved"
                else ("Denied; use workflow return." if status == "denied" else None),
                "consumed_at": _ts(minute + 7) if status == "consumed" else None,
            },
        )
        self.ds.note(f"Job edit request in '{status}' state")

    def _exception_request(self, job: dict, action: str, minute: int, status: str) -> None:
        self.ds.add(
            "exceptional_transition_requests",
            {
                "id": stable_id("exception", job["id"], action),
                "job_id": job["id"],
                "action": action,
                "status": status,
                "requested_by_user_id": self.admin["id"],
                "requested_at": _ts(minute + 5),
                "reason": f"Independent {action} of a terminal job.",
                "decided_by_user_id": self.employees[19]["id"] if status != "pending" else None,
                "decided_at": _ts(minute + 6) if status != "pending" else None,
            },
        )
        self.ds.note(f"Exceptional {action} request in '{status}' state")

    # -- absence / delegation -------------------------------------------------

    def _build_absence_flows(self) -> None:
        jobs = self.ds.tables.get("jobs", [])
        if len(jobs) < 6:
            return
        requester = self.employees[0]  # global Maker with existing assigned work
        nominee = self.employees[6]  # BR02 Maker and Checker
        responsibility_rows = self.ds.tables["job_responsibilities"]
        maker_by_job = {
            row["job_id"]: row["user_id"]
            for row in responsibility_rows
            if row["responsibility"] == "maker"
        }
        checker_by_job = {
            row["job_id"]: row["user_id"]
            for row in responsibility_rows
            if row["responsibility"] == "checker"
        }
        owned = [job for job in jobs if maker_by_job[job["id"]] == requester["id"]]
        eligible = [
            job
            for job in owned
            if job["branch_id"] == nominee["branch_id"]
            and checker_by_job[job["id"]] != nominee["id"]
        ]
        ineligible = next(job for job in owned if job["branch_id"] != nominee["branch_id"])
        delegated_job = eligible[0]
        conflict_job = next(job for job in eligible[1:] if job["stage"] == "confirmed")
        conflict_responsibility = next(
            row
            for row in responsibility_rows
            if row["job_id"] == conflict_job["id"] and row["responsibility"] == "checker"
        )
        conflict_responsibility["user_id"] = nominee["id"]
        conflict_event = next(
            row
            for row in self.ds.tables["job_responsibility_events"]
            if row["job_id"] == conflict_job["id"] and row["responsibility"] == "checker"
        )
        conflict_event["new_user_id"] = nominee["id"]

        override_job = next(
            job
            for job in owned
            if job["id"]
            not in {
                delegated_job["id"],
                conflict_job["id"],
                ineligible["id"],
            }
            and job["stage"] == "confirmed"
        )
        override_candidates = self._eligible_staff(
            slug="maker",
            client_id=override_job["client_id"],
            branch_id=override_job["branch_id"],
            direction=override_job["direction"],
            mode=override_job["mode"],
            minute=3000,
            exclude_ids={
                requester["id"],
                checker_by_job[override_job["id"]],
            },
        )
        override_nominee = override_candidates[0]

        # Approved nomination producing every outcome category.
        nom = self.ds.add(
            "absence_nominations",
            {
                "id": stable_id("absence", "approved"),
                "requester_user_id": requester["id"],
                "nominee_user_id": nominee["id"],
                "valid_from": _ts(3000),
                "valid_until": _ts(10_000_000),
                "reason": "Planned medical leave; nominate temporary cover.",
                "status": "approved",
                "requested_at": _ts(2900),
                "decided_by_user_id": self.admin["id"],
                "decided_at": _ts(2990),
                "decision_reason": "Approved with per-job eligibility evaluation.",
                "revoked_at": None,
                "version": 1,
            },
        )
        self._audit(
            None,
            self.admin["id"],
            "absence.nomination.approved",
            2990,
            None,
        )
        cases = (
            ("delegated", delegated_job, nominee),
            ("ineligible", ineligible, nominee),
            ("conflict", conflict_job, nominee),
            ("overridden", override_job, override_nominee),
        )
        for pos, (outcome, job, effective_nominee) in enumerate(cases):
            delegation_id = None
            if outcome in ("delegated", "overridden"):
                delegation_id = stable_id("delegation", nom["id"], job["id"])
                self.ds.add(
                    "job_delegations",
                    {
                        "id": delegation_id,
                        "job_id": job["id"],
                        "responsibility": "maker",
                        "delegator_user_id": requester["id"],
                        "delegate_user_id": effective_nominee["id"],
                        "valid_from": _ts(3000),
                        "valid_until": _ts(10_000_000),
                        "revoked_at": None,
                        "created_by_user_id": self.admin["id"],
                        "reason": "Absence-driven delegation of maker duty.",
                        "absence_nomination_id": nom["id"],
                    },
                )
                self._audit(
                    job,
                    self.admin["id"],
                    "responsibility.delegated",
                    3001 + pos,
                    job["version"],
                )
            self.ds.add(
                "absence_nomination_jobs",
                {
                    "id": stable_id("absence-job", nom["id"], job["id"]),
                    "nomination_id": nom["id"],
                    "job_id": job["id"],
                    "responsibility": "maker",
                    "nominee_user_id": effective_nominee["id"],
                    "outcome": outcome,
                    "reason": {
                        "delegated": "Nominee eligible; responsibility delegated.",
                        "ineligible": "Nominee lacks scope for this job.",
                        "conflict": "Nominee is the checker; maker/checker separation.",
                        "overridden": "Admin selected a different eligible per-job replacement.",
                    }[outcome],
                    "delegation_id": delegation_id,
                },
            )
            if delegation_id:
                self.ds.add(
                    "notifications",
                    {
                        "id": stable_id("notif", job["id"], "delegated"),
                        "recipient_user_id": effective_nominee["id"],
                        "job_id": job["id"],
                        "job_reference": job["reference"],
                        "event_type": "responsibility.delegated",
                        "message": f"You now cover maker duty for {job['reference']}.",
                        "target_path": f"/my-work?job={job['reference']}",
                        "dedupe_key": f"delegated:{job['id']}:{effective_nominee['id']}",
                        "created_at": _ts(3010 + pos),
                        "read_at": None,
                        "is_client_safe": False,
                    },
                )
                self._audit(
                    job,
                    self.admin["id"],
                    "notification.created",
                    3010 + pos,
                    job["version"],
                )
        self.ds.note(
            "Approved absence nomination with delegated/ineligible/conflict/overridden outcomes"
        )

        # Pending nomination awaiting Admin decision.
        self.ds.add(
            "absence_nominations",
            {
                "id": stable_id("absence", "pending"),
                "requester_user_id": self.employees[15]["id"],
                "nominee_user_id": self.employees[2]["id"],
                "valid_from": _ts(6000),
                "valid_until": _ts(10_000_000),
                "reason": "Conference travel; requesting cover.",
                "status": "pending",
                "requested_at": _ts(5900),
                "decided_by_user_id": None,
                "decided_at": None,
                "decision_reason": None,
                "revoked_at": None,
                "version": 1,
            },
        )
        # Rejected nomination.
        self.ds.add(
            "absence_nominations",
            {
                "id": stable_id("absence", "rejected"),
                "requester_user_id": self.employees[11]["id"],
                "nominee_user_id": self.employees[4]["id"],
                "valid_from": _ts(7000),
                "valid_until": _ts(10_000_000),
                "reason": "Short notice leave.",
                "status": "rejected",
                "requested_at": _ts(6900),
                "decided_by_user_id": self.admin["id"],
                "decided_at": _ts(6950),
                "decision_reason": "Nominee is also Busy; insufficient cover.",
                "revoked_at": None,
                "version": 1,
            },
        )
        self.ds.note("Pending and rejected absence nominations")
