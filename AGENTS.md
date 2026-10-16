# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.12+ modular monolith. Application code lives under
`src/nfpl_access_control/`: HTTP concerns in `api/`, configuration and
cryptographic helpers in `core/`, SQLAlchemy setup in `db/`, persistence
models in `models/`, Pydantic contracts in `schemas/`, and use-case logic in
`services/`. Alembic migrations live in `alembic/`; tests live in `tests/`.
Keep authorization and workflow decisions out of routers.

## Build, Test, and Development Commands

Create a virtual environment and install development dependencies with
`python -m pip install -e ".[dev]"`. Apply the schema with `alembic upgrade
head`, run the API with `uvicorn nfpl_access_control.main:app --reload`, run
tests with `pytest`, and run static checks with `ruff check .`. Prefer these
checked-in commands over machine-specific instructions.

## Coding Style & Naming Conventions

Use Python type hints, four-space indentation, `PascalCase` classes, and
`snake_case` functions and variables. Ruff is the formatter/linter authority;
do not introduce a second style tool without a project need. Keep modules small,
use SQLAlchemy 2.x typed declarative mappings, and use Pydantic v2 APIs.

## Testing Guidelines

Pytest is the test framework. Add tests for new behavior and regressions, keep
test names explicit, and default to isolated temporary SQLite databases. Security
tests must exercise denial paths as well as allowed paths. Never weaken an
invariant to satisfy a test. PostgreSQL compatibility must be considered even
when local tests use SQLite.

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
- Responsibility is separate from eligibility. Delegation is temporary and
  expiring; reassignment is permanent; both require eligibility and auditing.
- The actual preparer can never check the same version, including after
  promotion, delegation, or Admin access. Relevant edits invalidate checking.
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
- Work queue list and count queries must use the same policy predicates as
  mutations, bounded keyset pagination, suitable indexes, and no N+1 queries.
- Self-grants and sensitive self-approval are forbidden. The first Admin will be
  created by a trusted, single-use offline bootstrap command that only works
  when no Admin grant exists, records an audit event, and is then disabled.

## Delivery Phases

Implement only the approved phase. Phases 1 through 3 now cover the skeleton,
database/Alembic, core models, identity/authentication, scoped RBAC, policy
explanations, role management, effective grant history, transactional shipment
workflow, responsibility/reassignment, expiring delegation, employee
availability, deterministic assignment suggestions, exceptional transitions,
and atomic audit foundations. Later phases add complete audit/version history
and client feeds; admin requests, bootstrap, parser/queues and employee account
operations; then deterministic seed, scale benchmarks, and final documentation.
Do not claim unexecuted tests or benchmark figures.

## Zero-Cost Deployment Constraints

- Keep the backend as one lightweight FastAPI/Uvicorn web process. Do not add
  Celery, Redis, brokers, worker processes, paid schedulers, or mandatory AI
  services without an approved, documented need.
- Use SQLite only for zero-friction local development. Deployment uses
  environment-configured PostgreSQL through `DATABASE_URL`; never depend on
  persistent local files in a cloud web service.
- Target the checked-in Render Blueprint (or an equivalent Railway web service)
  for the API, a free PostgreSQL provider such as Neon, and Vercel for the
  frontend when it exists.
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
