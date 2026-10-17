# NFPL Access Control Service

Security-focused authorization for NFPL customs-brokerage shipment jobs. This
repository currently implements **Phases 1 through 4 and Phases 5A-5C**: the project skeleton,
database and authentication foundation, deployment configuration, scoped RBAC,
central authorization explanations, Admin-controlled grants/revocations, and
configurable safe roles, plus transactional shipment workflow, responsibility,
delegation, deterministic assignment suggestions, append-only audit history,
immutable shipment versions, historical eligibility reconstruction,
client-safe incremental updates, employee registration/password login,
Admin-controlled account lifecycle, and the first-Admin bootstrap.
Phase 5B adds Maker submission locks, Checker-owned generated checklists,
job-specific Admin-approved correction requests, Filing returns, mandatory
correction justification, and fresh independent verification.
Phase 5C adds approved absence replacement and authorization-bounded bulk
delegation, audited in-app notifications, an actionable keyset-paginated My
Work queue, and a restricted Admin operations dashboard.

The original `NFPL_Access_Control_Assignment.pdf` is retained as the source
brief. The approved expanded requirements govern the phased implementation.

## Architecture

The service is a Python 3.12+ modular monolith:

- `api/` owns HTTP routing and dependency wiring.
- `services/` owns application use cases; authentication already lives here.
- `authorization/` owns permissions, predefined roles, structured decisions,
  scope matching, and the fail-closed policy engine.
- `models/` owns SQLAlchemy persistence models and closed domain values.
- `schemas/` owns Pydantic v2 API contracts.
- `db/` owns engine and session lifecycle.
- `alembic/` owns schema history.

One Uvicorn web process serves the request-driven API. There is no Celery,
Redis, broker, worker, scheduler, or mandatory third-party AI service. Future
delegation expiry is checked during authorization, client updates are fetched
through bounded HTTP APIs, and load generation or audit verification runs only
as explicit offline commands.

SQLite is the zero-configuration local database. PostgreSQL is selected through
`DATABASE_URL` for deployment. The schema uses portable strings, explicit
foreign keys, bounded field lengths, constraints, and conventional indexes.
SQLite foreign-key enforcement is enabled on every application connection.
PostgreSQL pools are bounded at five connections with no overflow to keep memory
and free-provider connection use predictable.

The database is the durable source of truth. The application does not rely on a
cloud instance's local filesystem, in-memory authorization state, or background
processes. Alembic migrations are restart-safe. Job mutations combine
authorization rechecks, responsibility and state checks, optimistic locking,
state changes, and append-only audit inserts in one database transaction.

Authentication and authorization are separate. Employee passwords use uniquely
salted, memory-hard scrypt encodings. Successful login issues a random
eight-hour bearer session whose SHA-256 digest, not plaintext, is stored.
Sessions can be logged out or revoked, and disabling an account immediately
revokes every outstanding credential. Five failed password attempts create a
database-backed 15-minute lockout evaluated during login; no worker is needed.
Visibility and action permissions are evaluated separately. A job action first
requires visibility and then its specific permission. Public explanations redact
nonexistent and unauthorized jobs identically, while internal policy decisions
retain precise scope, expiry, and revocation reasons.

## Setup

Use a real Python 3.12+ interpreter rather than a Windows Store alias.

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
~~~

On macOS/Linux, invoke `.venv/bin/python` instead. Runtime dependencies and
test/development dependencies are separate in `pyproject.toml`.

Configuration is read from the process environment:

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Deployment only | SQLite or PostgreSQL connection string; defaults to `sqlite:///./nfpl.db` locally. |
| `NFPL_SQL_ECHO` | No | SQL logging; defaults to `false`. |
| `NFPL_CORS_ALLOWED_ORIGINS` | Frontend only | Comma-separated explicit browser origins, for example `https://nfpl.vercel.app`. Wildcards are rejected. |

`NFPL_DATABASE_URL` remains a lower-priority compatibility fallback, but new
deployments should use `DATABASE_URL`. Provider URLs beginning with
`postgres://` or `postgresql://` are normalized to SQLAlchemy's
`postgresql+psycopg://` dialect. Keep `sslmode=require` in a Neon connection
string. Copy `.env.example` only as a reference; the application does not
implicitly load local environment files.

## Migrate, Run, and Verify

~~~powershell
.venv\Scripts\alembic upgrade head
.venv\Scripts\nfpl-bootstrap-admin --email admin@example.test --name "NFPL Admin" --branch-code HQ --branch-name "Head Office"
.venv\Scripts\uvicorn nfpl_access_control.main:app --reload
.venv\Scripts\pytest
.venv\Scripts\ruff check .
~~~

The bootstrap command prompts twice for the password without accepting it on
the command line. It works only when no bootstrap marker and no Admin assignment
exist, creates one globally scoped Admin atomically, records account/grant/audit
history, and cannot overwrite an existing email or branch. Later Admin grants
remain blocked until the independent sensitive-access approval flow is added.

The available endpoints are:

- `GET /health`: lightweight, unauthenticated process liveness check.
- `POST /v1/auth/register`: creates a Pending staff account from name, email,
  password, and branch. Registration never accepts a role.
- `POST /v1/auth/login` and `POST /v1/auth/logout`: issue and revoke expiring
  employee bearer sessions.
- `GET /v1/identity/me`: requires `Authorization: Bearer <token>` and returns
  the database-resolved actor. Client-supplied actor IDs are ignored.
- `GET /v1/employees/me` and `PATCH /v1/employees/me/availability`: show the
  authenticated employee profile and update Available/Busy/Absent state.
- `GET /v1/admin/employees` and `GET /v1/admin/employees/{id}`: searchable,
  paginated Admin directory with roles/scopes, availability, account state, and
  current pending workload.
- `POST /v1/admin/employees/{id}/approve|reject|activate|deactivate`:
  reasoned, audited account-state transitions. Disabled sessions stop working
  immediately.
- `POST /v1/authorization/jobs/{job_id}`: explains an authenticated actor's
  job permission without leaking hidden job existence.
- `POST /v1/admin/roles`: creates a configurable role from safe permissions.
- `POST /v1/admin/role-assignments`: grants a scoped, optionally time-limited
  role using an encompassing built-in Admin assignment.
- `POST /v1/admin/role-assignments/{id}/revoke`: immediately revokes an
  assignment and appends a revocation event.
- `POST /v1/jobs` and `GET/PATCH /v1/jobs/{id}`: create, view, and edit a
  shipment using the authenticated actor and scoped policy. Client Viewer GETs
  use a separate safe response that omits descriptions, checklist decisions,
  employee identities, return feedback, and correction justifications.
- `POST /v1/jobs/{id}/prepare|check|file|cancel`: guarded, versioned workflow
  actions. Maker-supplied `checklist_data` is retained only for request
  compatibility and is ignored; the server generates the Checker checklist.
- `POST /v1/jobs/{id}/return-for-correction`: Filing Officer return with a
  required Maker fault, Checker fault, or Both category and explanation.
- `POST /v1/jobs/{id}/edit-requests` and
  `POST /v1/admin/edit-requests/{id}/decision`: job-specific Maker correction
  request and independent Admin approval/denial.
- `PUT /v1/admin/jobs/{id}/assignment`: assign, reassign, or unassign a
  Maker, Checker, or Filing Officer.
- `GET /v1/admin/jobs/{id}/assignment-suggestions`: deterministic,
  workload-ranked Available candidates.
- `POST /v1/admin/jobs/{id}/delegations` and
  `POST /v1/admin/delegations/{id}/revoke`: time-bounded delegation.
- `POST /v1/admin/jobs/{id}/exception-requests` and
  `POST /v1/admin/exception-requests/{id}/approve`: independently approved
  filed cancellation or reopening.
- `PATCH /v1/admin/employees/{id}/availability`: reasoned staff availability.
- `GET /v1/admin/jobs/{id}/versions|state-at|diff|field-changes|audit`:
  Admin-only full version and audit inspection for an authorized shipment.
- `GET /v1/admin/jobs/{id}/historical-eligibility`: reconstructs who could
  perform a requested action at an exact aware timestamp, separately from who
  actually changed the recorded version.
- `GET /v1/jobs/{id}/operational-history`: bounded operational history for a
  scoped Filing Officer or Admin. It omits snapshots and authorization context.
- `GET /v1/client/jobs/{id}/status|history` and `GET /v1/client/updates`:
  client-scoped, sanitized, read-only status and cursor-based updates.
- `POST/GET /v1/absence-nominations`: employees nominate a temporary
  replacement and review their own requests. Global Admin decision/revocation
  endpoints activate or end eligible job delegations; per-job override handles
  flagged replacements without broadening the replacement's authority.
- `GET /v1/notifications`, `GET /v1/notifications/unread-count`, and
  `POST /v1/notifications/{id}/read`: bounded database-backed notifications.
  Job-linked items are filtered again through current visibility, and client
  identities receive only explicitly sanitized items.
- `GET /v1/my-work`: current actionable responsibilities using the same role,
  scope, responsibility/delegation, absence, stage, and separation predicates
  as mutations. Pagination uses an opaque composite keyset cursor; `count`
  applies the same union query as the list.
- `GET /v1/admin/dashboard/overview|urgent-requests` and `GET /v1/admin/jobs`:
  global Admin operations views for stage/availability counts, pending absence,
  correction and exceptional requests, reassignment flags, and bounded job
  search. `POST /v1/admin/jobs/{id}/archive` archives only filed/cancelled jobs
  with optimistic locking, an immutable version, reason, and audit event.

The health endpoint intentionally avoids a database query so platform probes do
not keep a free PostgreSQL compute awake. Database readiness is established by
successful startup migration and ordinary request failures remain visible.

## Zero-Cost Demonstration Deployment

### 1. Neon PostgreSQL

1. Create a free Neon project and database.
2. In Connection Details, select the pooled connection string. The hostname
   contains `-pooler`.
3. Preserve its TLS parameters and store the complete value as Render's secret
   `DATABASE_URL`. Never expose it to the frontend or commit it.

Neon documents pooled connections for applications with connection constraints:
<https://neon.com/docs/manage/endpoints/>. Free-tier quotas and cold starts can
change, so confirm provider limits before a demonstration.

### 2. Render backend

The checked-in `render.yaml` defines one free Python web service, installs only
runtime dependencies, runs `alembic upgrade head` before serving, binds to
Render's `$PORT`, and probes `/health`.

1. Push this repository to a Git provider.
2. In Render, choose **New > Blueprint** and select the repository.
3. Enter the pooled Neon URL when prompted for `DATABASE_URL`.
4. Deploy and confirm `https://<service>.onrender.com/health` returns
   `{"status":"ok"}`.
5. After the frontend has a stable Vercel URL, add that exact origin to
   `NFPL_CORS_ALLOWED_ORIGINS` in the Render service and redeploy.

The Blueprint follows Render's documented Python web-service, free-plan, and
health-check fields: <https://render.com/docs/blueprint-spec>. Render explicitly
describes free services as demonstration/testing resources rather than
production infrastructure: <https://render.com/docs/free>.

Railway can be used instead of Render: install with `pip install .`, start with
`alembic upgrade head && uvicorn nfpl_access_control.main:app --host 0.0.0.0
--port $PORT`, set the same environment variables, and configure `/health`.
No Railway-specific service is required by the application.

### 3. Vercel frontend

No frontend source exists through Phase 5A, so a speculative Vercel project file is
not checked in. When the frontend is introduced:

1. Import its directory as a Vercel project and keep framework auto-detection.
2. Add a public API-base variable appropriate to the chosen framework, such as
   `VITE_API_BASE_URL` or `NEXT_PUBLIC_API_BASE_URL`, containing the Render
   HTTPS URL. Do not place database URLs or API bearer credentials in public
   variables.
3. Configure Preview and Production separately, deploy, then allow their exact
   origins in the backend CORS setting.

Vercel documents framework-aware public variable prefixes and environment
scopes at <https://vercel.com/docs/environment-variables/framework-environment-variables>
and <https://vercel.com/docs/environment-variables>.

## Scoped RBAC and Authorization

Six system roles are installed by migration:

| Role | Core permissions |
| --- | --- |
| Maker | View and prepare jobs |
| Checker | View and check jobs |
| Filing Officer | View and file jobs |
| Admin | Operational permissions plus role/grant management |
| Client Viewer | View jobs and client-visible history |
| Parser Service | View, create, and update jobs only |

Users may hold multiple assignments. Each assignment independently selects one
client or explicit all-clients, one branch or explicit all-branches, one
direction or explicit all-directions, and one mode or explicit all-modes.
Database checks reject ambiguous null-as-wildcard records.

Assignments use UTC half-open intervals: `valid_from <= t < valid_until`.
Revocation becomes effective at `revoked_at <= t`; rows remain historical and
grant/revoke operations append `role_assignment_events`. Authorization checks
these timestamps synchronously, so no expiry worker is required.

Configurable roles require no application-code change but can contain only
predefined operational permissions. Access grant/revoke and role management are
reserved for the built-in Admin. Admins cannot grant roles to themselves, grant
beyond their scope, or directly grant the Admin role; the latter remains
reserved for the later independent-approval flow.

## Core Data Model

- `User`: staff, client, or service identity with Pending/Active/Disabled state,
  optional home branch, and Available/Busy/Absent employee availability.
- `ApiCredential`: unique token digest with expiry and revocation timestamps.
- `PasswordCredential`: one scrypt password encoding plus database-backed
  failed-attempt and temporary-lockout state.
- `AccountStateEvent`: immutable effective-time registration, approval,
  rejection, activation, and deactivation evidence.
- `AdminBootstrap`: durable single-use marker for the trusted first Admin.
- `Branch` and `Client`: job scope reference data.
- `Job`: shipment scope and fields, generated checklist revision, Maker edit
  lock, correction-routing flags and feedback, actual preparer/checker/filer
  evidence, stage, and an SQLAlchemy optimistic-lock version. The Phase 1
  generic assignee remains for migration compatibility but is not the workflow
  responsibility source.
- `Role` and `RolePermission`: system or configurable role composition.
- `RoleAssignment`: explicit four-dimensional scope, effective interval,
  revocation metadata, reasons, actors, and optimistic version.
- `RoleAssignmentEvent`: append-oriented grant and revocation history.
- `JobResponsibility` and `JobResponsibilityEvent`: current responsibility
  plus append-oriented assignment/reassignment history.
- `JobDelegation`: reasoned UTC half-open delegation with early revocation.
- `ExceptionalTransitionRequest`: independently approved filed cancellation
  or reopening.
- `JobEditRequest`: job-specific Pending/Approved/Denied/Consumed correction
  request with requester, independent decision actor, reasons, and UTC times.
- `AuditEvent`: action, actor, time, reason, authorization context, and job
  before/after snapshots, affected version, and denial marker stored atomically
  with mutations.
- `JobVersion`: immutable shipment snapshots keyed by job and optimistic
  version, including the actual actor, action, reason, and UTC event time.
- `UserAvailabilityEvent`: effective-time evidence used when reconstructing
  historical action eligibility.

Jobs follow `confirmed -> prepared -> checked -> filed`. Maker submission
generates and locks a mode/direction-specific checklist. The Checker records
Complete, Incomplete, or Not Applicable for every item; Not Applicable needs a
written justification and any Incomplete item returns actionable feedback to
the Maker. The actual preparer cannot verify the revision.

A locked Maker can edit only after a job-specific request is approved by a
different scoped Admin, or after a Checker/Filing return routes work to the
Maker. Correction resubmission requires justification, creates immutable new
versions, and requires fresh checking. A Filing Officer can return an approved
revision for Maker fault, Checker fault, or Both with a written explanation;
Checker-only returns remain Maker-locked and permit checklist reconsideration.
Reasoned Admin cancellation is allowed for unfinished jobs. Filed cancellation
and reopening from `filed` or `cancelled` require the established independent
exceptional flow; reopening unlocks correction work and never rewrites history.

Role eligibility never creates responsibility automatically. Maker, Checker,
and Filing actions require both current scoped permission and current assignment
or effective delegation. Absent staff cannot act or receive new assignments;
Busy staff can be manually assigned but are excluded from suggestions.
Delegation uses `valid_from <= now < valid_until` and is evaluated per request.

Suggestions are database-driven and deterministic: only active Available staff
with an effective matching permission are selected, then ordered by current
open responsibility count, display name, and ID. The first suggested Maker is
excluded from Checker suggestions. Saved assignments are revalidated through
the same authorization engine.

All application timestamps represent UTC instants. Historical policy intervals
use half-open semantics: `valid_from <= timestamp < valid_until`, with a null
end meaning open-ended. Point-in-time reconstruction combines the latest job
version, effective role scopes, responsibility/reassignment events, active
delegations, account-state and availability events, stage restrictions, and maker/checker
separation. If required job-version or responsibility evidence is absent, the
response sets `complete=false` and explains the limitation instead of
inventing an eligible actor. Actual version actors are reported separately.

History access is enforced in the API:

| Actor | History access |
| --- | --- |
| Admin | Full authorized versions, diffs, audit context, and reconstruction |
| Filing Officer | Bounded operational history for shipments in filing scope |
| Client Viewer | Sanitized status/history for its own client only |
| Maker / Checker | No complete shipment-history endpoint |

Client feeds contain only reference, stage/progress, safe status text, time,
version, and cursor. They never expose employee identities, reasons, checklist
contents, role data, or internal authorization context.

## Security Direction

The non-bypassable direction is recorded in `AGENTS.md`: separate visibility
and action decisions, multidimensional scoped grants, fail-closed policy,
maker/checker separation based on the actual preparer, immediate revocation,
transactional rechecks, atomic append-only auditing, independent approval for
sensitive operations, restricted client/parser identities, and consistent
queue/action predicates.

The first-Admin bootstrap is a trusted one-time offline command. It operates
only when no Admin grant or prior bootstrap marker exists and records its
account, role-grant, marker, and audit evidence in one transaction. Public
Admin registration does not exist. Subsequent Admin grants remain reserved for
the independent sensitive-access approval flow and cannot use the bootstrap.

## Inspect with DBeaver

Use the backend PostgreSQL `DATABASE_URL` only in a trusted administrator
environment; never copy it into Vercel or browser code. In DBeaver, create a
PostgreSQL connection with the provider host, database, user, password, and TLS
requirement. Useful read-only inspection queries are:

~~~sql
SELECT id, email, display_name, kind, account_status, availability, is_active
FROM users ORDER BY email;
SELECT user_id, previous_status, status, effective_at, actor_user_id, reason
FROM account_state_events ORDER BY effective_at DESC LIMIT 100;
SELECT r.slug, rp.permission FROM roles r JOIN role_permissions rp ON rp.role_id = r.id
ORDER BY r.slug, rp.permission;
SELECT ra.user_id, r.slug, ra.client_id, ra.branch_id, ra.direction, ra.mode,
       ra.valid_from, ra.valid_until, ra.revoked_at
FROM role_assignments ra JOIN roles r ON r.id = ra.role_id ORDER BY ra.valid_from;
SELECT id, reference, client_id, branch_id, direction, mode, stage, version
FROM jobs ORDER BY created_at DESC LIMIT 100;
SELECT job_id, responsibility, user_id, assigned_at
FROM job_responsibilities ORDER BY job_id, responsibility;
SELECT job_id, status, requested_by_user_id, requested_at, decided_by_user_id,
       decided_at, reason, decision_reason
FROM job_edit_requests ORDER BY requested_at DESC LIMIT 100;
SELECT job_id, action, actor_user_id, occurred_at, reason
FROM audit_events ORDER BY occurred_at DESC LIMIT 100;
SELECT job_id, version_number, recorded_at, actor_user_id, action, reason, snapshot
FROM job_versions ORDER BY job_id, version_number DESC LIMIT 100;
SELECT user_id, previous_availability, availability, effective_at, actor_user_id, reason
FROM user_availability_events ORDER BY effective_at DESC LIMIT 100;
~~~

ORM update/delete operations on audit rows, job versions, role-assignment
events, responsibility events, availability events, account-state events, and
the bootstrap marker are rejected.
Immutability is application-level: a database owner can still alter rows using
direct SQL. Production deployments should restrict the application's database
role from destructive history operations; portable database triggers or an
external tamper-evident archive remain possible defense-in-depth work.

## Current Limitations

Phase 5C intentionally does **not** include general permission requests or
independent Admin-role grant approval, deterministic seed/load generation,
benchmarks, frontend source, or the final design document/demo. Notifications
are in-app and request-driven only; email, push delivery, and a background
dispatcher are outside the frozen scope. Audit events and notifications remain
distinct: each created notification is audited, but most audit events do not
create notifications.

Absence approval currently requires a globally scoped Admin because it may
transfer responsibilities across multiple clients and branches. A concurrent
override is serialized with row locks on PostgreSQL and optimistic nomination
versions; SQLite retains its single-writer development semantics. The Admin
All Jobs search uses bounded offset pagination, while the action-sensitive My
Work queue uses keyset pagination. Scale latency remains unmeasured until the
approved benchmark phase.

SQLite is for local development, not Render/Railway persistence. PostgreSQL has
not yet been exercised by this local test run. No latency or scale claim is made
until the Phase 6 benchmark is executed.
