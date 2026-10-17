# NFPL Access Control Service - Test Report

Report date: 2026-10-17  
Scope: Phases 1 through 4, Phases 5A-5C, Phase 6A, and zero-cost deployment amendment

## Environment

- Windows, Python 3.12.10
- FastAPI 0.143.3
- SQLAlchemy 2.1.4
- Alembic 1.20.0
- Pydantic 2.14.1
- Psycopg 3.3.6
- Pytest 9.1.1
- SQLite temporary databases
- Node.js 25.8.1 and npm 11.11.0 (frontend verification)
- React 19.3.1, Vite 8.3.4, TypeScript 6.0.3, Vitest 4.1.12

Dependencies were installed from `pyproject.toml` into the repository-local
`.venv`. The Windows Store `python` alias was unusable, so setup used the
installed Python 3.12 interpreter directly.

## Final Verification

Commands executed:

~~~powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\python.exe -m pip check
.venv\Scripts\pytest.exe --cov=src/nfpl_access_control --cov-report=term-missing -q
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\alembic.exe check
.venv\Scripts\alembic.exe downgrade base
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m compileall -q src tests alembic
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
npm audit --omit=dev
~~~

Additional Python assertions loaded the ASGI app, generated OpenAPI, checked
the Phase 5C operations paths, and called the hidden-from-schema `/health` route. Earlier
Phase 3 verification parsed `render.yaml` and checked its free-plan and health
configuration.

Final results:

- Ruff lint: pass, 0 errors
- Ruff format check: pass
- Dependency consistency: pass, no broken requirements
- Render YAML parse/config assertions: pass
- Pytest: **113 passed, 0 failed, 0 skipped**, 1 third-party deprecation warning
- Statement coverage: **85%** (3,750 statements, 579 missed)
- Alembic upgrade, full downgrade, and re-upgrade: pass through a disposable
  canonical `DATABASE_URL`
- Alembic model/schema drift check: pass, no new upgrade operations detected
- Import/OpenAPI smoke check: pass; 56 documented API paths
- Benchmarks: **not run**; benchmark implementation is Phase 6
- Frontend TypeScript: pass
- Frontend ESLint: pass, 0 errors/warnings
- Frontend Vitest: **13 passed, 0 failed, 0 skipped** across 2 files
- Frontend production build: pass; 35 modules transformed
- Frontend production bundle: 288.03 kB JavaScript (90.12 kB gzip) and
  33.03 kB CSS (6.41 kB gzip)
- Frontend runtime dependency audit: pass, 0 known vulnerabilities

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

## Phase 5A Employee and Authentication Scenarios Verified

- Registration requires a normalized unique email, validated branch, strong
  password, and name; it creates a Pending staff account with no role.
- Passwords are stored as unique salted scrypt encodings and never returned.
  Login issues an eight-hour random bearer token while persisting only its
  SHA-256 digest.
- Pending and Disabled accounts cannot log in or use protected endpoints.
  Admin approval enables login; deactivation atomically revokes all sessions.
- Logout, legacy revoked/expired credentials, and exact expiry boundaries deny.
- Database-backed failed-attempt counters impose a temporary lockout without
  Redis, a scheduler, or a background worker.
- Non-Admins cannot list or inspect employees. Valid and nonexistent targets
  remain indistinguishable to unauthorized account-transition callers.
- Admin directory search/pagination returns role scopes, availability, account
  status, and pending workload without password or token hashes.
- Existing role-management tests continue to verify non-Admin denial, scope
  limits, Admin self-escalation prevention, and blocked direct Admin grants.
- Self availability changes and Admin account transitions are audited in the
  same transaction. Account-state events are append-only and historical
  eligibility applies exact activation/deactivation boundaries.
- The first-Admin bootstrap is single-use, refuses an existing Admin or marker,
  stores no plaintext secret, creates its branch/Admin grant atomically, and
  records immutable bootstrap evidence.
- Revision `20261017_0005` adds account status, password credentials,
  account-state events, the one-time bootstrap marker, normalized-email
  constraint, and employee-directory indexes. A migration test verifies legacy
  mixed-case email normalization before that constraint is installed.

## Phase 5B Finalized Workflow Scenarios Verified

- Maker submission generates an Air/FCL/LCL and import/export-specific
  checklist, locks Maker edits, records the actual preparer, and creates an
  immutable version. Maker-supplied legacy checklist content is ignored.
- A locked revision rejects direct Maker edits with `submission_locked`.
  A reasoned job-specific request requires an independent scoped Admin decision;
  stale approval and requester self-approval are denied and audited.
- Approved corrections clear prior verification, unlock only that job, preserve
  old versions, and require a Maker justification when resubmitted. The request
  moves to Consumed on resubmission.
- Checker decisions require every generated item exactly once. Invalid states,
  missing items, and unjustified Not Applicable decisions fail closed. Any
  Incomplete item returns actionable feedback and Maker correction routing.
- Existing maker/checker separation continues to reject the actual preparer,
  including after promotion or delegation. Checker reapproval after a returned
  correction requires its own justification.
- Filing can act only on an independently checked revision. Reasoned returns
  route Maker fault, Checker fault, or Both correctly; Checker-only returns keep
  Maker editing locked, while Maker/Both returns require fresh verification.
- Stale versions, invalid workflow states, missing correction reasons,
  unauthorized actions, and submitted edits are covered as denial paths.
- A simulated audit persistence failure followed by transaction rollback leaves
  the shipment stage, checklist revision, lock, audit, and version unchanged.
- Historical eligibility uses the recorded Maker lock, and client feeds map new
  versioned actions to sanitized progress messages without exposing internal
  reasons or checklist decisions.
- The generic visible-job endpoint returns a separate safe detail shape to
  Client Viewers, preventing checklist decisions, correction feedback,
  descriptions, and employee evidence from leaking across the staff boundary.
- Revision `20261017_0006` adds job lock/correction/feedback columns and indexed
  `job_edit_requests`. Upgrade, downgrade to 0005, re-upgrade, full downgrade,
  and model/schema drift checks passed on a disposable SQLite database.

## Phase 5C Operations Scenarios Verified

- Employee replacement nomination requires active staff identities, an aware
  bounded interval, a reason, and independent global Admin approval. Eligible
  open responsibilities become temporary delegations; ineligible or conflicting
  jobs remain explicitly flagged for Admin review.
- Per-job Admin overrides recheck current scoped eligibility and separation of
  duties. Nomination revocation ends every linked delegation immediately and
  records responsibility events, per-job audit events, and actionable alerts.
- Nomination creation locks the requesting employee and all delegation paths
  lock the shared job-responsibility row before checking interval overlap;
  duplicate active delegation intervals are rejected.
- Delegation and absence intervals use exact UTC half-open boundaries without a
  scheduler. During absence the original employee leaves My Work, an eligible
  delegate enters it, and responsibility returns at expiry or revocation.
- My Work list/count use one database-filtered authorization union covering
  scope, responsibility/delegation, account state, absence, stage, archive state,
  and maker/checker separation. Busy staff retain existing work; role revocation
  removes it immediately. Composite priority/time/ID keyset pages do not repeat
  jobs.
- Assignment, submission, correction, checking, filing, delegation, and client
  milestones create deduplicated database notifications in the same transaction.
  Notification creation is audited; rollback removes both records. Reads recheck
  current job visibility and Client Viewers see only client-safe messages.
- Historical eligibility applies approved absence and delegation evidence at
  exact start/expiry boundaries. Concurrent nomination approval produces one
  winning delegation set and rejects the stale decision through optimistic
  locking.
- The Admin dashboard is denied to non-Admins, reports bounded operational
  counts and urgent requests, lists/searches jobs without N+1 assignee loads,
  flags reassignment-required jobs, and archives only filed/cancelled jobs with
  a new immutable job version and atomic audit.
- Revision `20261017_0007` adds absence nominations/outcomes, delegation
  provenance, notifications, job archival fields, and supporting queue/dashboard
  indexes. Upgrade, drift check, full downgrade, and re-upgrade passed on a
  disposable SQLite database.

## Phase 6A Frontend Scenarios Verified

- Login validates email/password locally, calls only the documented login and
  current-profile endpoints, stores an expiring bearer credential only in
  tab-scoped `sessionStorage`, and routes Admin and operational identities to
  their approved landing pages.
- Registration validates name, email, branch ID, and password confirmation,
  submits exactly the backend registration contract, and offers no role or
  privilege field. Successful requests show the Pending approval state.
- Pending and Disabled login denials share a privacy-safe account-unavailable
  screen rather than exposing account-state details.
- Logout calls the documented revocation endpoint, clears local authentication
  state even if that request fails, and returns to login. Locally expired
  sessions and server-revoked sessions receiving a protected 401 are cleared.
- Protected routes deny role mismatches without shipment disclosure. Navigation
  combines multiple currently effective role assignments and excludes grants at
  exact expiry/revocation boundaries.
- Structured authorization explanations and reason codes reach the error UI;
  network failures use a safe message without leaking low-level details.
- The shared responsive shell, loading/error/empty states, status badges,
  confirmation dialog, search field, pagination component, and notification
  placeholder compile in the production build. Non-authentication dashboard
  routes are explicitly labeled placeholders rather than mock live data.
- API behavior was tested with controlled `fetch` responses. A live
  browser-to-running-FastAPI integration was not executed and is not claimed.

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
12. The first Phase 5A regression run preserved 70 tests and failed only the
    migration downgrade: SQLite still reflected the new account-status check
    while rebuilding `users` without that column. The downgrade now drops the
    check before the column; focused and full migration tests pass.
13. A post-test security review found account-transition routes loaded a target
    before checking Admin authority. Authorization now occurs first, and a
    negative test verifies unauthorized valid/missing targets both return 403.
14. The first Phase 5B focused regression run had 23 passes and 2 expected
    policy mismatches: the Phase 3 test allowed direct post-check Maker edits,
    and one history assertion expected the older rejection action name. The
    superseded edit expectation was replaced with Admin-approved correction
    coverage; the legacy rejection event name remains compatible.
15. The first full Phase 5B run had 85 passes and 1 failure because historical
    eligibility still expected a submitted Maker to remain actionable. The
    reconstruction now applies the recorded submission lock, and the separate
    availability-boundary assertion uses visibility eligibility.
16. An intermediate test edit introduced one indentation collection error and
    Ruff found one import-order issue. Both were corrected before final results;
    no passing result was claimed for that run.
17. The first resumed Phase 5C run preserved all 93 prior tests but Ruff found
    formatting/import issues in interrupted files. Formatting was applied before
    behavioral verification.
18. The first focused Phase 5C test run exposed a test-fixture identity omission;
    the corrected run then exposed that absence provenance had been placed on a
    responsibility event instead of `JobDelegation`. The column was moved to the
    model matching migration `0007`; no security check was weakened.
19. The first combined smoke command passed lint, format, dependencies, and
    compilation but its inline Python expression had a PowerShell quoting error.
    The smoke check was rerun separately and passed with 56 OpenAPI paths and a
    successful `/health` response.
20. The keyset pagination lint pass found a missing `and_` import while its
    focused tests passed. The import and a two-page no-duplicates regression test
    were added before final verification.
21. The first frontend install rejected TypeScript 7 because the current
    TypeScript ESLint peer range ends below 6.1. The project now uses TypeScript
    6.0.3; no peer checks were bypassed. Vitest/jsdom were also aligned to
    releases supporting the local Node runtime.
22. The first frontend verification compiled all application code but found two
    unsupported `expect.stringEndingWith` assertions in tests; 11 of 13 tests
    passed. The assertions now use supported regex matchers. The repeated
    typecheck, lint, all 13 tests, and production build passed.

## Not Yet Verified

The complete security matrix for original questions Q1-Q14 is not yet claimed.
Permission requests and independent Admin-role grants, deterministic seed/load
generation, and scale benchmarks belong to later approved phases. External
notification delivery is outside Phase 5C; in-app notification retrieval is
request-driven.

No live Render, Railway, Vercel, or Neon deployment was performed, and no real
PostgreSQL server was available for integration testing. Current remaining risks
include lack of a PostgreSQL CI target and no email-verification or password
reset/recovery flow (not requested in Phase 5A). Append-only enforcement is at the
SQLAlchemy application layer; a database owner or direct SQL client can still
alter history because portable triggers or a tamper-evident archive are not
implemented. PostgreSQL row-lock behavior was designed but not exercised against
a live PostgreSQL server; local concurrency coverage uses SQLite's single-writer
behavior plus SQLAlchemy optimistic locking. The database-backed lockout is per known account rather than a
distributed IP/device rate limiter; this avoids mandatory infrastructure but
should be supplemented at the reverse proxy in production. No latency or scale
figure has been measured or claimed. Phase 6A has no live browser/backend
end-to-end run, accessibility audit, or deployed Vercel smoke test. Dashboard
data/actions remain deferred to Phase 6B.
