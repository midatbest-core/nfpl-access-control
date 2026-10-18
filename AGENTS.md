# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.12+ modular monolith. Application code lives under
`src/nfpl_access_control/`: HTTP concerns in `api/`, configuration and
cryptographic helpers in `core/`, SQLAlchemy setup in `db/`, persistence
models in `models/`, Pydantic contracts in `schemas/`, and use-case logic in
`services/`. Alembic migrations live in `alembic/`; tests live in `tests/`.
The Vite/React/TypeScript client lives in `frontend/`, with application code
under `frontend/src/` and frontend tests under `frontend/src/test/`.
Keep authorization and workflow decisions out of routers.

## Build, Test, and Development Commands

Create a virtual environment and install development dependencies with
`python -m pip install -e ".[dev]"`. Apply the schema with `alembic upgrade
head`, run the API with `uvicorn nfpl_access_control.main:app --reload`, run
tests with `pytest`, and run static checks with `ruff check .`. Prefer these
checked-in commands over machine-specific instructions.
For the frontend, run `npm install` once in `frontend/`, then use `npm run
dev`, `npm run typecheck`, `npm run lint`, `npm test`, and `npm run
build`.

## Coding Style & Naming Conventions

Use Python type hints, four-space indentation, `PascalCase` classes, and
`snake_case` functions and variables. Ruff is the formatter/linter authority;
do not introduce a second style tool without a project need. Keep modules small,
use SQLAlchemy 2.x typed declarative mappings, and use Pydantic v2 APIs.
Frontend code uses strict TypeScript, functional React components, native
`fetch`, Tailwind CSS, and ESLint. Keep API contracts typed and avoid adding
state-management or UI-framework dependencies without an approved need.

## Testing Guidelines

Pytest is the test framework. Add tests for new behavior and regressions, keep
test names explicit, and default to isolated temporary SQLite databases. Security
tests must exercise denial paths as well as allowed paths. Never weaken an
invariant to satisfy a test. PostgreSQL compatibility must be considered even
when local tests use SQLite.
Frontend behavior uses Vitest and React Testing Library. Cover validation,
session lifecycle, route denial, role-aware navigation, and safe API errors;
route guards are UX only and never replace backend authorization.

## Commit & Pull Request Guidelines

No Git history is available, so this guide cannot establish existing commit conventions. Use short, imperative commit subjects (for example, `Add role validation`) until a project convention is adopted. Pull requests should explain the change and its rationale, link related issues when applicable, and include test results. Add screenshots for user-facing visual changes.

## Security & Configuration

Do not commit credentials, tokens, or local environment files. Provide safe example configuration (such as `.env.example`) when needed, and document required settings without including secret values.

## Approved Architecture & Security Invariants

- Treat visibility and action authorization as separate decisions. A visible job
  is not implicitly editable or actionable.
- Use scoped RBAC with multiple independent grants per user. Client, branch,
  direction, and mode wildcards mean all only when explicitly stored.
- Keep predefined safe actions separate from configurable role definitions.
  The unified Admin role remains subject to system invariants.
- Resolve the actor from authenticated credentials, never mutation-supplied user
  IDs. Missing, inconsistent, expired, revoked, or unsupported policy data denies.
- Employee registration creates a Pending account without roles. Passwords use
  scrypt; logins create hashed, expiring, revocable server-side sessions.
  Disabled accounts fail immediately even when a session was already issued.
- Account transitions and availability changes are atomic with audit and
  effective-time history. Public responses never expose password/session hashes.
- Responsibility is separate from eligibility. Delegation is temporary and
  expiring; reassignment is permanent; both require eligibility and auditing.
- The actual preparer can never check the same version, including after
  promotion, delegation, or Admin access. Relevant edits invalidate checking.
- Maker submission locks shipment editing. A correction requires a job-specific
  independently approved Admin edit request or a Checker/Filing return. Maker
  and Checker correction resubmissions require recorded justification.
- Checklist definitions are generated from the immutable job mode/direction and
  are owned by the Checker. Complete, Incomplete, and justified Not Applicable
  are the only decisions; any Incomplete item routes work back to the Maker.
- Filing Officers may file an independently checked revision or return it with
  a written Maker/Checker/Both category. Maker changes always require a fresh
  independent check; filed work still uses the exceptional reopen process.
- Access changes apply to subsequent operations immediately. Recheck policy and
  state inside each mutation transaction and use optimistic job versions.
- Filed cancel/reopen is an exceptional Admin-authorized flow with a reason,
  independent approval where required, immutable prior versions, and audit.
- Client viewers receive only client-scoped shipment data and a sanitized
  incremental status feed. Parser identities have narrowly scoped field/action
  permissions and cannot check, file, cancel, reopen, or administer access.
- Changes and important denials are append-only audited atomically. Historical
  eligibility uses UTC half-open effective intervals (`valid_from <= t <
  valid_until`, with null `valid_until` meaning open-ended) and is distinct
  from the record of actual actors.
- Full shipment/audit history is limited to a scoped Admin. A scoped Filing
  Officer receives operational history without full snapshots or policy
  context; Client Viewers receive sanitized own-client updates; Makers and
  Checkers do not receive complete shipment history.
- Application ORM guards enforce append-only history for normal service code.
  Database owners can bypass application guards, so document least-privilege
  database roles and the absence of portable trigger/tamper-evidence controls.
- Work queue list and count queries must use the same policy predicates as
  mutations, bounded keyset pagination, suitable indexes, and no N+1 queries.
- Self-grants and sensitive self-approval are forbidden. The first Admin is
  created by the trusted, single-use offline bootstrap command, which refuses
  any existing marker or Admin assignment and records an audit event.

## Delivery Phases

Implement only the approved phase. Phases 1 through 4 and Phases 5A-5C cover the skeleton,
database/Alembic, core models, identity/authentication, scoped RBAC, policy
explanations, role management, effective grant history, transactional shipment
workflow, responsibility/reassignment, expiring delegation, employee
availability, deterministic assignment suggestions, exceptional transitions,
atomic append-only audit/version history, point-in-time eligibility, and
client-safe updates, employee registration/login, account approval and
deactivation, Admin directory, availability self-service, and first-Admin
bootstrap, absence nomination and bounded bulk delegation, audited actionable
notifications, keyset-paginated work queues, and restricted Admin operations
views. Later phases add permission requests and remaining employee operations;
then deterministic seed, scale benchmarks, and final
documentation. Do not claim unexecuted tests or benchmark figures.

Phase 5C notifications are database-backed and request-driven. Each created
notification has an audit event, but ordinary audit events do not imply a
notification. Job notifications are re-filtered through current authorization;
delegation expiry and absence remain authorization-time checks with no worker.

Phase 6A provides only the frontend authentication, shared shell, typed API
foundation, and role-aware route structure. Dashboard data/actions remain
explicit placeholders until an approved later phase. Browser sessions use
`sessionStorage`, clear on protected 401 responses, and never log credentials
or tokens.

Phase 6B Admin pages use the real protected dashboard, job, employee, scoped
role-assignment, urgent-request, reference-data, and audit APIs. Client and
branch selectors display names but submit identifiers. Role changes require
reasons, revocation confirmation, and a directory refresh; frontend guards and
controls never replace backend scope, self-escalation, independent-approval, or
optimistic-version enforcement. The disposable HTTP smoke script must use only
a temporary database and must not claim browser coverage.

Phase 6C-A operational pages use the SQL-backed My Work response as the source
of actionable jobs and preserve its opaque keyset cursor. Maker controls require
current backend responsibility context, send the server's optimistic version,
and never expose full audit history. Shipment responses include authorized
client and branch display names; direction and mode remain immutable. The
notification center is request-driven and job links always re-enter protected
routes. Its disposable HTTP smoke uses a migrated temporary database and does
not claim browser coverage.

Completed Phase 6 operational pages keep Checker and Filing actions in the
shared authorized shipment detail. Checklist controls submit every
server-generated key exactly once, require N/A and reevaluation explanations,
and never calculate eligibility in place of backend checks. Filing returns use
the approved Maker/Checker/Both categories and an optimistic job version.
Client pages use only the sanitized client directory, status, history, update,
and notification contracts; they never consume staff details or internal audit
responses. All pagination cursors remain opaque to the browser.

Phase 7 sample data is generated only by the explicit
nfpl_access_control.sample_data CLI. Standard seeds target an empty,
fully migrated, explicitly disposable database; they must never touch the
default local database or run at application startup. SQLite seeding remains
file-only and refuses nfpl.db. PostgreSQL seeding reads DATABASE_URL only from
the environment, requires its PostgreSQL-specific disposable confirmation,
does not run migrations, and requires exact Alembic head 20261017_0007. Import
is atomic, schema-checked, never deletes data, and refuses reruns into populated
data; SQLite additionally runs its explicit foreign-key check.
Demo passwords enter through NFPL_DEMO_PASSWORD, are stored only as unique
scrypt encodings, are never printed, and are not issued to service identities.
The 500-employee/200,000-job dataset is streamed to files and is never loaded
into the regular demo database.

## Zero-Cost Deployment Constraints

- Keep the backend as one lightweight FastAPI/Uvicorn web process. Do not add
  Celery, Redis, brokers, worker processes, paid schedulers, or mandatory AI
  services without an approved, documented need.
- Use SQLite only for zero-friction local development. Deployment uses
  environment-configured PostgreSQL through `DATABASE_URL`; never depend on
  persistent local files in a cloud web service.
- Target the checked-in Render Blueprint (or an equivalent Railway web service)
  for the API, a free PostgreSQL provider such as Neon, and Vercel for the
  checked-in `frontend/` on Vercel.
- Delegation expiry is evaluated synchronously during authorization. Client
  status updates are request-driven and cursor/timestamp based. Expensive seed,
  load, benchmark, and audit-verification commands never run at app startup.
- Keep `/health` lightweight. Startup migration must be idempotent, and
  restarts must not weaken transaction boundaries, authorization, audit
  atomicity, or optimistic locking.
- Keep runtime dependencies minimal and separate development/test tooling.
  Bound database pools and API results, avoid N+1 queries, and measure before
  making performance claims.
- CORS remains disabled unless explicit frontend origins are configured.
  Wildcard origins and browser-exposed database or bearer secrets are forbidden.
- Zero cost is a deployment objective, never a reason to weaken isolation,
  fail-closed behavior, maker/checker separation, or audit correctness.
