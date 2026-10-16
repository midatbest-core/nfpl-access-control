# NFPL Access Control Service

Security-focused authorization for NFPL customs-brokerage shipment jobs. This
repository currently implements **Phases 1 through 3**: the project skeleton,
database and authentication foundation, deployment configuration, scoped RBAC,
central authorization explanations, Admin-controlled grants/revocations, and
configurable safe roles, plus transactional shipment workflow, responsibility,
delegation, deterministic assignment suggestions, and audit foundations.

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

Authentication and authorization are separate. A protected route resolves its
actor from a random bearer credential whose SHA-256 digest, not plaintext, is
stored. Credentials and users can be disabled, and credentials can expire.
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
.venv\Scripts\uvicorn nfpl_access_control.main:app --reload
.venv\Scripts\pytest
.venv\Scripts\ruff check .
~~~

The available endpoints are:

- `GET /health`: lightweight, unauthenticated process liveness check.
- `GET /v1/identity/me`: requires `Authorization: Bearer <token>` and returns
  the database-resolved actor. Client-supplied actor IDs are ignored.
- `POST /v1/authorization/jobs/{job_id}`: explains an authenticated actor's
  job permission without leaking hidden job existence.
- `POST /v1/admin/roles`: creates a configurable role from safe permissions.
- `POST /v1/admin/role-assignments`: grants a scoped, optionally time-limited
  role using an encompassing built-in Admin assignment.
- `POST /v1/admin/role-assignments/{id}/revoke`: immediately revokes an
  assignment and appends a revocation event.
- `POST /v1/jobs` and `GET/PATCH /v1/jobs/{id}`: create, view, and edit a
  shipment using the authenticated actor and scoped policy.
- `POST /v1/jobs/{id}/prepare|check|file|cancel`: guarded workflow actions
  with an expected job version.
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

No frontend source exists through Phase 3, so a speculative Vercel project file is
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

- `User`: staff, client, or service identity with active/inactive status,
  optional home branch, and Available/Busy/Absent employee availability.
- `ApiCredential`: unique token digest with expiry and revocation timestamps.
- `Branch` and `Client`: job scope reference data.
- `Job`: shipment scope and fields, checklist revision, actual preparer/checker/
  filer evidence, stage, and an SQLAlchemy optimistic-lock version. The Phase 1
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
- `AuditEvent`: action, actor, time, reason, authorization context, and job
  before/after snapshots stored atomically with Phase 3 mutations.

Jobs follow `confirmed -> prepared -> checked -> filed`. A Checker rejection
returns a job to `confirmed`. A relevant edit after checking returns it to
`prepared`, clears the prior check, increments the checklist revision, and
requires fresh independent verification. Reasoned Admin cancellation is allowed
for unfinished jobs. Filed cancellation and reopening from `filed` or
`cancelled` require a pending exceptional request and approval by a different
scoped Admin. Reopened jobs return through preparation and checking.

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
will use half-open semantics: `valid_from <= timestamp < valid_until`, with a
null end meaning open-ended.

## Security Direction

The non-bypassable direction is recorded in `AGENTS.md`: separate visibility
and action decisions, multidimensional scoped grants, fail-closed policy,
maker/checker separation based on the actual preparer, immediate revocation,
transactional rechecks, atomic append-only auditing, independent approval for
sensitive operations, restricted client/parser identities, and consistent
queue/action predicates.

The planned first-Admin bootstrap is a trusted one-time offline command. It will
only operate when no Admin grant exists, record a bootstrap audit event, and
become unavailable afterward. It is documented but remains deferred until the
generalized audit and independent-approval phase. Phase 2 tests use an explicit
trusted bootstrap fixture; a real deployment cannot administer grants until the
bootstrap command is implemented.

## Inspect with DBeaver

Use the backend PostgreSQL `DATABASE_URL` only in a trusted administrator
environment; never copy it into Vercel or browser code. In DBeaver, create a
PostgreSQL connection with the provider host, database, user, password, and TLS
requirement. Useful read-only inspection queries are:

~~~sql
SELECT id, email, display_name, kind, availability, is_active FROM users ORDER BY email;
SELECT r.slug, rp.permission FROM roles r JOIN role_permissions rp ON rp.role_id = r.id
ORDER BY r.slug, rp.permission;
SELECT ra.user_id, r.slug, ra.client_id, ra.branch_id, ra.direction, ra.mode,
       ra.valid_from, ra.valid_until, ra.revoked_at
FROM role_assignments ra JOIN roles r ON r.id = ra.role_id ORDER BY ra.valid_from;
SELECT id, reference, client_id, branch_id, direction, mode, stage, version
FROM jobs ORDER BY created_at DESC LIMIT 100;
SELECT job_id, responsibility, user_id, assigned_at
FROM job_responsibilities ORDER BY job_id, responsibility;
SELECT job_id, action, actor_user_id, occurred_at, reason
FROM audit_events ORDER BY occurred_at DESC LIMIT 100;
~~~

`job_versions` is intentionally not present yet; immutable version
reconstruction is Phase 4. Phase 3 before/after snapshots can be inspected in
`audit_events`. ORM update/delete operations on audit rows are rejected;
database-trigger enforcement against direct SQL remains a Phase 4 portability
decision.

## Current Limitations

Phase 3 intentionally does **not** yet include employee password registration/
login and account approval, the employee directory, immutable job-version rows
and historical eligibility reconstruction, client-safe incremental feeds,
general permission requests or independent Admin-role grant approval, the
production first-Admin bootstrap command, My Work queue/count endpoints,
deterministic seed/load generation, benchmarks, frontend source, or the final
design document/demo. The audit table is the transactional foundation, not the
completed Phase 4 historical reconstruction feature.

SQLite is for local development, not Render/Railway persistence. PostgreSQL has
not yet been exercised by this local test run. No latency or scale claim is made
until the Phase 6 benchmark is executed.
