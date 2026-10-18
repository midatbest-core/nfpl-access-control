# NFPL Access Control Service - Test Report

Report date: 2026-10-18
Scope: Phases 1 through 7 and the zero-cost deployment amendment

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

## Live Workflow Integration Repair (2026-10-18)

Commands actually executed:

~~~powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
cd frontend
npm test -- --run
npm run typecheck
npm run lint
npm run build
~~~

Verified results:

- Backend: **132 passed, 0 failed, 0 skipped**; one third-party
  Starlette/httpx deprecation warning.
- Ruff lint passed; all **96** Python files were formatted.
- Frontend: **37 passed** across five Vitest files; TypeScript and ESLint
  passed; the production Vite build passed with 42 transformed modules.
- A disposable migrated SQLite demo database completed Admin login, shipment
  creation, assignment suggestions, and Maker, Checker, and Filing Officer
  assignment through the real API contracts. Neon was not mutated.
- Read-only Neon diagnostics confirmed Alembic head 20261017_0007, active and
  unlocked sampled demo accounts, no duplicate active identical grants, and
  421 jobs (the standard 420 plus one later-created shipment). The later job
  had Checker and Filing Officer assignments but no Maker assignment.
- Regression coverage verifies precise duplicate-grant conflicts, exclusion
  of the actual Maker from Checker suggestions, persistent privacy-safe login
  failure guidance, refreshed assignment suggestions, duplicate-submit
  prevention, and searchable/paginated Admin job selection for audit history.
- Coverage was not rerun for this integration repair. No schema or migration
  changed, and no live login or mutation was issued against Neon.

## PostgreSQL Demo Import Guard Verification (2026-10-18)

Commands actually executed:

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_sample_data.py -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\nfpl-sample-data.exe seed-postgres --help
~~~

Verified results:

- Phase 7 focused tests: **15 passed, 0 failed**; one third-party
  Starlette/httpx deprecation warning.
- Full backend regression: **130 passed, 0 failed, 0 skipped**; the same
  third-party warning.
- Ruff lint passed; all **96** Python files were already formatted.
- CLI help exposed the PostgreSQL-specific disposable confirmation flag.
- Targeted tests verify that `seed-postgres` refuses a missing confirmation,
  refuses a non-PostgreSQL URL, normalizes a provider-style PostgreSQL URL,
  builds the 420-job standard dataset, calls the existing `import_dataset`,
  disposes its engine, and does not print the URL host or either test secret.
- An isolated migrated-database test verifies that a pre-existing custom role
  is treated as application data: import is refused and no users or jobs are
  inserted.
- The PostgreSQL test uses an isolated fake engine/import boundary. No live
  PostgreSQL or Neon connection was opened, and no import was executed.
- No migration or application schema changed. Statement coverage was not
  rerun for this narrow CLI change; the most recent measured coverage remains
  the baseline result below.

## Phase 7 Baseline Verification (2026-10-17)

Commands actually executed:

~~~powershell
.venv\Scripts\python.exe -m pytest --cov=nfpl_access_control --cov-report=term-missing
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
cd frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
cd ..
.venv\Scripts\python.exe scripts\phase7_http_smoke.py
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m alembic downgrade base
.venv\Scripts\python.exe -m alembic upgrade head
~~~

Verified results:

- Backend Pytest: **127 passed, 0 failed, 0 skipped**; one third-party
  Starlette/httpx deprecation warning.
- Statement coverage: **85%** (4,558 statements, 691 missed).
- Phase 7 focused tests: **12 passed**. They cover exact dataset counts,
  deterministic build/files, live-schema column parity, scoped-responsibility
  eligibility, absence/delegation semantics, audited notifications,
  output-directory safety, large-data stream counts, atomic import,
  foreign-key integrity, rerun refusal, unique scrypt hashes, role-specific
  API access, no-self-check, client isolation, historical eligibility, and
  authoritative system roles.
- Ruff lint and format: pass across the repository.
- Frontend: TypeScript pass; ESLint pass; **33 Vitest tests passed** across
  five files; production build pass (42 modules, 338.10 kB JS/99.93 kB gzip,
  35.69 kB CSS/6.88 kB gzip).
- Migration verification on a unique temporary SQLite file: upgrade to
  20261017_0007, current-head check, no schema drift, full downgrade to base,
  and re-upgrade to head all passed. Phase 7 adds no migration.
- Standard import: a fresh migrated SQLite database accepted 5,803 generated
  rows plus 31 unique password-credential rows and one bootstrap marker
  (5,835 total inserted rows). SQLite PRAGMA foreign_key_check returned no
  violations. A repeat import was rejected without changing counts.
- Real HTTP/Uvicorn smoke: health and Admin login passed; Admin dashboard
  reported 378 non-archived jobs from 420 total; Maker update, Checker
  verification, and Filing Officer filing passed; an adversarial Checker
  delegation to the actual preparer was denied with self_check_forbidden;
  Client Viewer own-client status passed and cross-client status returned 404.
  This was API-only verification, not browser automation.
- Full benchmark file generation: **1,002,212 rows** across seven data tables
  generated as NDJSON in **42.617 seconds**, totaling **629,221,039 bytes**,
  on this Windows/Python 3.12.10 environment. Counts were 501 identities
  (500 operational employees plus one Admin), 1,501 scoped role assignments,
  200,000 jobs, 600,000 responsibilities, and 200,000 versions. Output was
  generated in a marked temporary directory, verified, and removed; it was
  not imported into the regular demo database. These are generation figures,
  not API or database latency claims.

Phase 7 corrected incompatibilities found in the supplied generator before
import: role_slug was not a live role_assignments column; role-assignment
timestamps were absent; version snapshots lacked historical scope fields;
responsibilities were not consistently backed by role scope; absence cases
did not correspond to actual responsibility holders; exceptional decisions
self-approved; notification events lacked audit counterparts; the manifest
used a nondeterministic wall clock; and benchmark responsibilities did not
match grants. Corrections preserve the live schema and security invariants.

Remaining risks and limitations:

- PostgreSQL/Neon import and query performance were not exercised; the guarded
  PostgreSQL CLI path has unit coverage, while migration and full import
  verification used SQLite.
- The full 200,000-job files were generated but deliberately not imported, so
  authorization, queue, count, listing, and historical-query database latency
  at that scale remains unmeasured.
- Append-only protection remains application-level and can be bypassed by a
  database owner, as documented.
- Browser automation, accessibility audit, and deployed Render/Vercel/Neon
  verification were not performed.
- The shared demo password is suitable only for disposable local data. It is
  supplied out-of-band through NFPL_DEMO_PASSWORD, never committed or printed,
  and the Parser Service intentionally has no password credential.

## Previous Phase 6C-A Verification

Commands executed:

~~~powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest --cov=nfpl_access_control --cov-report=term
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
cd ..
.venv\Scripts\python scripts\phase6b_http_smoke.py
.venv\Scripts\python scripts\phase6ca_http_smoke.py
~~~

Additional Python assertions loaded the ASGI app, generated OpenAPI, checked
the Phase 5C operations paths, and called the hidden-from-schema `/health` route. The
Phase 6B smoke script also started a real Uvicorn server on loopback with a
disposable migrated SQLite database and used real HTTP requests. Earlier
Phase 3 verification parsed `render.yaml` and checked its free-plan and health
configuration.
The Phase 6C-A smoke independently started the real Uvicorn application against
a disposable migrated SQLite database and exercised Admin setup plus the Maker
queue, detail, edit, submit, edit-request, and notification journey.

Final results:

- Ruff lint: pass, 0 errors
- Ruff format check: pass
- Dependency consistency: pass, no broken requirements
- Render YAML parse/config assertions: pass
- Pytest: **114 passed, 0 failed, 0 skipped**, 1 third-party deprecation warning
- Statement coverage: **85%** (3,795 statements, 571 missed)
- Alembic upgrade to head: pass through the Phase 6C-A disposable HTTP smoke.
  Phase 6C-A changes no tables, columns, constraints, or indexes, so the prompt's
  conditional full downgrade/schema-drift checks were not rerun. The preserved
  Phase 6B baseline passed both, and no file under `alembic/` changed.
- Import/OpenAPI smoke check: pass; 58 documented API paths
- Benchmarks: **not run**; benchmark implementation is Phase 6
- Frontend TypeScript: pass
- Frontend ESLint: pass, 0 errors/warnings
- Frontend Vitest: **26 passed, 0 failed, 0 skipped** across 4 files
- Frontend production build: pass; 40 modules transformed
- Frontend production bundle: 322.81 kB JavaScript (97.33 kB gzip) and
  34.95 kB CSS (6.74 kB gzip)
- Frontend runtime dependency audit: pass, 0 known vulnerabilities
- Real HTTP Admin smoke: pass for health, login, reference data, dashboard,
  employee listing, scoped grant/revoke, job create/get, assignment
  suggestions, job audit, and urgent-request retrieval. The fixture contained
  no pending urgent request, so decision mutation was covered by mocked UI and
  backend service/API tests rather than this HTTP smoke.
- Real HTTP Maker smoke: pass for health, employee login, My Work list/count,
  named job detail, responsibility context, optimistic edit, submission lock,
  post-submit queue removal, edit-request creation, notification listing/count,
  and mark-read. This was API-level HTTP integration, not a browser run.
- Browser automation: not run; no browser automation tool is installed.

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

## Phase 6B Admin Scenarios Verified

- The active creation route loads protected client/branch reference data,
  handles loading/error/empty states, submits selected IDs, then loads live
  assignment suggestions and supports assignment or leaving a role unassigned.
- Admin Overview, All Jobs, Job Details, Employee Directory, Urgent Requests,
  and Audit History are active routes. Archive, ordinary cancellation,
  filed-job exceptional cancellation, reopening requests, account actions, and
  supported request decisions use their existing secured API contracts.
- Employee pages embed scoped role management for client, branch, direction,
  and mode. Grants require a reason; revocations require a reason plus explicit
  confirmation; successful mutations refresh directory data. Admin is
  deliberately not offered as a direct grant option.
- Request decisions transmit the backend request version. Stale/conflict and
  authorization explanations are surfaced without weakening backend checks.
- Six targeted React tests cover reference selections and job creation, scoped
  grants, confirmed revocation, stale urgent decisions, versioned
  cancellation, and archival authorization failure. Route-level Admin
  protection remains covered by the preserved Phase 6A suite.
- One backend regression verifies that reference data is Admin-only, sorted,
  and that urgent responses expose the optimistic request version required by
  decision endpoints.
- The disposable real-HTTP run exercised a running Uvicorn application rather
  than ASGI-only TestClient calls. It is not a browser UI test.

## Phase 6C-A My Work and Maker Scenarios Verified

- The operational landing route uses the real SQL-backed My Work response,
  displays the server count, workflow metadata, direct/delegated context and
  feedback, and preserves opaque keyset Next/Previous navigation.
- The shared staff detail displays authorized client/branch names and assigned
  operational employees. It deliberately exposes no complete audit/history
  endpoint to Makers or Checkers.
- Maker edits send the current optimistic version. Direction and mode are
  read-only. Submission requires confirmation, refreshes the returned version,
  locks editing, and removes the submitted item from the actionable queue.
- Returned corrections display server feedback and require a correction
  justification before resubmission. Locked Prepared/Checked work offers the
  existing reasoned edit-request flow; Admin approval remains independent.
- Notifications use only the signed-in actor's bounded list/count/read APIs.
  Job links are navigation hints and re-enter protected job routes.
- Seven targeted React tests cover queue count/metadata/keyset paging,
  empty/revoked access, Maker edit/submission lock, correction justification,
  post-submission edit requests, stale-version feedback, and notification
  unread/read/navigation behavior. Existing authentication tests were updated
  to model the newly active queue request rather than a placeholder route.
- Backend regression assertions cover direct/delegated queue metadata and the
  staff-only responsibility context response. The full backend suite remains
  114 tests because these assertions extend existing test cases.
- The disposable real-HTTP run exercised the actual Uvicorn application and
  temporary migrated SQLite database. It did not exercise a browser.

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
23. The first Phase 6B full lint pass found import ordering and long lines only
    in the new HTTP smoke script. Ruff formatting fixed them before final
    verification.
24. The first real-HTTP smoke completed every API assertion but exited nonzero
    because Windows briefly retained the temporary SQLite handle. The harness
    now waits after Uvicorn termination; the repeated run passed and cleaned up.
25. The first full Phase 6B backend run had 113 passes and one historical
    eligibility failure. The production rule was correct: fixture users used
    the real creation clock, which had moved past the test's fixed historical
    timestamp. Giving synthetic users an explicit earlier creation timestamp
    made the test deterministic; the final 114-test run passed.
26. The first Phase 6C-A full frontend run passed all 26 assertions, but Vitest
    reported an asynchronous logout rejection because the newly active My Work
    request consumed a sequential legacy mock. URL-specific queue/logout mocks
    removed the race; the repeated run passed with no unhandled errors.
27. The first Phase 6C-A HTTP smoke passed every API assertion, while the
    combined command also reported import/line formatting in the new harness.
    Ruff applied only mechanical formatting; repository-wide lint and format
    checks then passed.

## Not Yet Verified

General permission requests and independent approval for future Admin-role
grants remain deferred. External notification delivery is outside the frozen
scope; in-app notification retrieval is request-driven. Phase 7 now provides
deterministic seed/load generation and measured full-scale file generation,
but not a 200,000-job database performance benchmark.

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
should be supplemented at the reverse proxy in production. The measured
42.617-second result applies only to NDJSON generation on the reported local
environment and is not an API latency claim. Phase 7 has real loopback HTTP API
verification but no browser automation, accessibility audit, or deployed
Vercel smoke test.
