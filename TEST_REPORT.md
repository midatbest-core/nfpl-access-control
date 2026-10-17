# NFPL Access Control Service - Test Report

Report date: 2026-10-17  
Scope: Phases 1 through 4 plus zero-cost deployment amendment

## Environment

- Windows, Python 3.12.10
- FastAPI 0.143.3
- SQLAlchemy 2.1.4
- Alembic 1.20.0
- Pydantic 2.14.1
- Psycopg 3.3.6
- Pytest 9.1.1
- SQLite temporary databases

Dependencies were installed from `pyproject.toml` into the repository-local
`.venv`. The Windows Store `python` alias was unusable, so setup used the
installed Python 3.12 interpreter directly.

## Final Verification

Commands executed:

~~~powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\python.exe -m pip check
.venv\Scripts\pytest.exe --cov=nfpl_access_control --cov-report=term-missing
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\alembic.exe check
.venv\Scripts\alembic.exe downgrade base
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m compileall -q src tests alembic
~~~

Additional Python assertions loaded the ASGI app, generated OpenAPI, checked
all Phase 4 paths, and called the hidden-from-schema `/health` route. Earlier
Phase 3 verification parsed `render.yaml` and checked its free-plan and health
configuration.

Final results:

- Ruff lint: pass, 0 errors
- Ruff format check: pass
- Dependency consistency: pass, no broken requirements
- Render YAML parse/config assertions: pass
- Pytest: **71 passed, 0 failed, 0 skipped**, 1 third-party deprecation warning
- Statement coverage: **87%** (2,101 statements, 272 missed)
- Alembic upgrade, full downgrade, and re-upgrade: pass through a disposable
  canonical `DATABASE_URL`
- Alembic model/schema drift check: pass, no new upgrade operations detected
- Compile/import/OpenAPI/health checks: pass; 29 documented API paths
- Benchmarks: **not run**; benchmark implementation is Phase 6

The warning comes from FastAPI's installed test-client compatibility layer:
`StarletteDeprecationWarning` recommends a future `httpx2` transition. It
does not affect application runtime or test correctness, but dependency updates
should track it.

## Phase 1 Scenarios Verified

- Public liveness and protected identity endpoint behavior.
- Authenticated actor comes from the bearer credential; an attacker-controlled
  `X-User-Id` header does not select the actor.
- Missing and invalid credentials return the same generic 401 response.
- Revoked, expired, exactly-at-expiry, and inactive-user credentials deny.
- Only a SHA-256 token digest is persisted by the tested credential setup.
- Job scope fields and enum values round-trip; new jobs start at `confirmed`
  with version 1.
- API timestamps retain an explicit UTC offset, naive security timestamps are
  rejected, and identity/job enum values have database check constraints.
- SQLite foreign keys are actually enforced.
- Concurrent stale ORM updates raise `StaleDataError`; the winning update
  increments the optimistic-lock version.
- The initial migration upgrades and downgrades all Phase 1 domain tables.
- The checked-in migration matches current SQLAlchemy metadata.
- `DATABASE_URL` overrides the legacy name, PostgreSQL provider schemes select
  Psycopg 3, empty URLs and invalid flags fail fast, and local SQLite remains
  the default.
- PostgreSQL engine construction succeeds without connecting and uses a
  five-connection pool with zero overflow.
- CORS origins are explicit, normalized, and deduplicated; wildcard, malformed,
  credential-bearing, and path-bearing origins fail closed.
- A configured Vercel origin receives the expected preflight response.

## Phase 2 Security Scenarios Verified

- Job visibility and each job action are separate decisions.
- A global Maker plus client-restricted Checker receives the union of grants
  without broadening the Checker scope.
- Client, branch, direction, and mode mismatches return distinct internal reason
  codes without including private job identifiers in explanations.
- Invisible and nonexistent job IDs produce identical public responses.
- Maker, Checker, Filing Officer, Admin, Client Viewer, and Parser Service
  definitions are deterministically installed with 23 permission mappings.
- Parser Service lacks check, file, cancel, reopen, and access-management
  permissions.
- Missing permissions, inactive actors, invalid timestamps, malformed scopes,
  future grants, expiry boundaries, and revocation all fail closed.
- Effective intervals use half-open UTC semantics; historical checks immediately
  before and at revocation/expiry boundaries are covered.
- Admin grants must be within the Admin assignment's own scope.
- Non-Admins cannot grant roles; Admin self-grants are rejected; direct Admin
  grants require the later independent-approval flow.
- Safe configurable roles work without an application-code change, while
  configurable access-management permissions are rejected.
- Grant and revoke events are retained with actors, timestamps, and reasons;
  revocation increments the assignment's optimistic version.
- Authenticated Admin API creation and authenticated non-Admin denial are both
  exercised.

## Phase 3 Security and Workflow Scenarios Verified

- The normal Maker -> Checker -> Filing Officer path requires current scoped
  permission and distinct current responsibility at every transition.
- The actual preparer cannot check the same checklist revision after receiving
  Checker permission or a manually constructed conflicting responsibility.
- Mid-job role revocation immediately blocks the assigned employee while the
  unfinished job remains intact.
- Temporary delegation is effective only in its UTC half-open interval and can
  be explicitly revoked with assignment history and audit.
- Absent staff cannot act or receive a new assignment; Available candidates are
  suggested deterministically by pending workload, name, and ID.
- Maker and Checker suggestions are separated, and manual assignments recheck
  underlying multidimensional permission eligibility.
- Shipment edits after checking clear verification, return the job to prepared,
  increment the checklist revision, and require a fresh check.
- Filing requires recorded independent verification.
- A filed cancellation requires an exceptional request approved by a different
  scoped Admin; self-approval is denied and audited.
- Parser Service can create and update the two exposed parser-safe shipment
  fields, but cannot prepare/check/file. Strict request models reject unknown
  protected keys rather than silently accepting them.
- Explicit expected versions reject stale workflow requests, while SQLAlchemy
  optimistic locking remains the final concurrent-write backstop.
- Successful workflow mutations and before/after audit events share one
  transaction. An explicit rollback test restores the job and removes its
  uncommitted audit event.
- ORM update and delete operations against audit events are rejected as an
  append-only invariant.
- Authenticated API job creation uses the bearer-derived actor, and a protected
  stage-field injection attempt is rejected with HTTP 422.
- Migration upgrade, model/schema drift, and full downgrade cover the five new
  workflow/audit tables and additive user/job columns.

## Phase 4 Audit, History, and Client Scenarios Verified

- Every successful shipment mutation that changes shipment state writes an
  immutable `JobVersion` with the same transaction as its audit event. Explicit
  rollback removes the mutation, version, and audit together.
- Role grants/revocations, responsibility changes, delegations, availability
  changes, parser modifications, workflow transitions, and relevant denials
  have append-oriented evidence. Stale-version and invalid-stage denials record
  structured reason codes without creating false shipment versions.
- Historical state, version differences, field-change attribution, and actual
  approval/rejection actors are reconstructable from immutable snapshots.
- Historical eligibility applies effective role scope, visibility,
  responsibility or delegation, availability, stage, and maker/checker
  separation at exact UTC half-open boundaries. Missing job-version or
  responsibility evidence produces `complete=false` with limitations.
- Actual actors are returned separately from people who could have acted.
- Admin full history, Filing Officer operational history, Client Viewer
  sanitized own-client history, and Maker/Checker full-history denial are
  enforced by authenticated backend endpoints.
- Cross-client client status/history returns the same generic 404 as a missing
  job. Cursor feeds use bounded keyset pagination and expose no actor, reason,
  checklist, role, or authorization-context fields.
- ORM update/delete attempts against audits, versions, role-assignment events,
  responsibility events, and availability events are rejected as append-only.
- Revision `20261017_0004` adds affected-version and denial metadata plus
  `job_versions` and `user_availability_events` with history lookup indexes.

## Failed Attempts and Corrections

Results are recorded rather than hidden:

1. The first combined verification stopped during test setup. Ruff reported
   three import-order issues and formatting changes; application import exposed
   a slotted-dataclass default lookup bug. No test pass was claimed. The default
   database URL was moved to a module constant and Ruff fixes were applied.
2. The next run collected 14 tests: 13 passed and 1 failed. The migration
   round-trip showed that SQLite's foreign-key PRAGMA had opened an implicit
   transaction, causing the Alembic revision row to roll back. The setup
   transaction is now explicitly committed before Alembic owns the migration
   transaction.
3. After 14/14 tests passed, the first Alembic drift check failed because the
   model described `token_hash` as a unique constraint while the migration
   used a unique index. The migration was aligned to the model. The full suite
   still passed and the repeated drift check reported no changes.
4. The zero-cost deployment amendment introduced no failing test run. Its final
   expanded suite completed with 28/28 tests passing.
5. The first Phase 2 run collected 45 tests: 42 passed and 3 failed. All three
   exposed one explanation defect: an expired or revoked view grant caused an
   action decision to replace the precise temporal reason with generic missing
   visibility. Decisions now track visibility separately, preserving internal
   reasons while public responses still redact hidden jobs.
6. The first independent Phase 2 migration verification passed schema drift but
   failed a manually supplied expected seed count of 27. The six reviewed role
   definitions contain 23 permission mappings. The assertion was corrected and
   added to the automated migration test; upgrade, seed, drift, downgrade, and
   re-upgrade then passed.
7. The first Phase 3 regression run failed before test execution in 32 fixtures
   and one model test because new preparer/checker/filer foreign keys made the
   legacy `User.assigned_jobs` relationship ambiguous. Both sides now specify
   `Job.assignee_id`; the preserved 47-test suite then passed.
8. The first Phase 3 migration drift check reported only a unique-constraint
   name mismatch. The migration name was aligned with model metadata; fresh
   upgrade, drift check, and full downgrade then passed.
9. The first combined final command found one import-order lint error while all
   58 tests passed. The import was reordered; after the audit immutability test
   was added, the final lint command and 59-test suite passed.
10. The resumed Phase 4 focused run found one missing
    `RoleAssignmentEvent` test import: 9 passed and 1 failed. The import was
    restored; no application behavior was changed to satisfy it.
11. The first combined smoke command incorrectly expected `/health` in
    OpenAPI, but the liveness route is intentionally excluded from the schema.
    A corrected check separately generated OpenAPI and called `/health`; both
    passed.

## Not Yet Verified

The complete security matrix for original questions Q1-Q14 is not yet claimed.
Permission requests and independent Admin-role grants, production first-Admin
bootstrap, work queue list/count parity, employee registration/password login
and account approval, employee directory, deterministic seed/load generation,
and scale benchmarks belong to later approved phases. Finalized correction/
return locks, three-state Checker-owned checklist behavior, and notifications
also remain deferred.

No live Render, Railway, Vercel, or Neon deployment was performed, and no real
PostgreSQL server was available for integration testing. Current remaining risks
include lack of a PostgreSQL CI target and no production credential
issuance/first-Admin bootstrap command yet. Append-only enforcement is at the
SQLAlchemy application layer; a database owner or direct SQL client can still
alter history because portable triggers or a tamper-evident archive are not
implemented. Historical account activation/deactivation events do not exist
until employee management is implemented. No latency or scale figure has been
measured or claimed.
