# AI Assistance Disclosure (LLM.md)

This document discloses the role, extent, and boundaries of Large Language Model (LLM) and generative AI assistance in the research, design, implementation, testing, and documentation of the **NFPL Access Control Service**.

---

## 1. Tooling & Models Used

During the development lifecycle, AI assistance was utilized via the following primary tools and models:

*   **Google DeepMind / Google Antigravity (Gemini Pro):** Used extensively through the Antigravity pair-programming environment for code scaffolding, rapid refactoring, architectural constraint analysis, TypeScript component development, and test authoring.
*   **OpenAI ChatGPT (GPT-4 / GPT-4o) & OpenAI Codex:** Used during initial exploratory phases for brainstorming policy representations, analyzing role-based access control (RBAC) vs. attribute-based access control (ABAC) trade-offs, drafting database schema options, and generating synthetic data strategies.

---

## 2. Areas of AI Involvement

### A. Requirements Interpretation & Edge Case Discovery
*   **Deconstruction of the Assignment Brief:** The original `NFPL_Access_Control_Assignment.pdf` contains nuanced operational constraints (e.g., overlapping Maker/Checker grants, absence coverage, filed-job emergency transitions, and immutable audit trails). AI models assisted in cataloging the 14 core questions and generating edge-case matrices.
*   **Invariants Formulation:** AI helped formalize key security invariants, such as separating visibility from mutation authority, preventing Maker self-verification, and enforcing half-open UTC effective intervals (`valid_from <= t < valid_until`).

### B. Architecture & Policy Engine Exploration
*   **Authorization Formula:** Exploration of the composite access evaluation equation:
    $$\text{Identity} + \text{Role} + \text{Scope} + \text{Job Responsibility} + \text{Workflow State} + \text{Separation of Duties} + \text{Effective Time} = \text{Decision}$$
*   **SQLAlchemy 2.0 & Keyset Pagination:** Assisted in formulating optimized SQL queries for work queues and audit histories, ensuring no $N+1$ query issues, strict index utilization, and bounded memory footprints under zero-cost deployment constraints.

### C. Backend & Frontend Implementation
*   **FastAPI & Alembic:** Scaffolding routers, Pydantic v2 validation contracts, and database migrations.
*   **React 19, TypeScript & Tailwind CSS (Frontend V2):** Drafting modern, accessible UI components (custom dropdowns, search tables, confirmation modals, notification popovers, and status badges) without heavy UI library dependencies.
*   **Deterministic Sample Data Generator:** Assisting with the pure mathematical deterministic generator (`DatasetBuilder`) that emits reproducible sample datasets with fixed UUIDv5 identifiers from natural keys.

### D. Automated Testing & Debugging
*   **Test Suite Generation:** Authoring unit and integration tests across both Pytest (backend services, authorization engine, workflow transitions, migrations) and Vitest / React Testing Library (frontend route guards, demo logins, form validation).
*   **Bug Diagnosis:** Pinpointing race conditions, CORS headers misconfigurations, and SQLite vs. PostgreSQL dialect discrepancies during local and staging execution.

---

## 3. Human Decisions, Invariants & Manual Verification

While AI tools provided code generation and drafting acceleration, **all core architectural decisions, security boundaries, and operational invariants were directed, reviewed, and finalized by humans**:

1.  **Fail-Closed Security Posture:** Deciding that any missing, expired, revoked, or unsupported policy parameter must deny access immediately by default.
2.  **Segregation of Duties Enforcements:** Hardcoded system invariants ensuring that even an Admin or delegated user cannot check a checklist revision they originally prepared as a Maker.
3.  **Removal of Unapproved Workflows:** Identifying and removing features that compromised operational segregation (such as arbitrary in-place Maker edit requests) in favor of Checker/Filing correction return cycles and audited Admin exceptional transitions.
4.  **No Hallucinated Infrastructure:** Enforcing strict zero-cost deployment rules (single lightweight web process, no Redis, no Celery, no unmanaged background workers, synchronous evaluation).

---

## 4. Verification & Quality Assurance Methodology

No AI-generated code or text was accepted without rigorous, independent automated and manual validation:

*   **Automated Pytest Suite:** 136 backend integration and unit tests covering all denial and allowed paths.
*   **Automated Vitest Suite:** 28 frontend component and flow tests exercising authentication, routing, and operational workspaces.
*   **Real Database Validation:** Live tests against both file-backed SQLite and cloud PostgreSQL (Neon), validating connection pooling, optimistic locking, foreign-key constraints, and schema migration roll-forwards.
*   **Manual Interactive Testing:** Human manual walkthroughs using evaluator personas on the Vite frontend, validating responsive layouts, toast feedback, notification dismissals, and concurrency protections.

---

## 5. Limitations of AI Assistance & Critical Reflection

1.  **Propensity to Overcomplicate:** AI suggestions frequently defaulted to heavy enterprise stacks (e.g., suggesting Celery workers, Redis pub/sub, or external policy engines like OPA). Human intervention was required to keep the architecture minimal, zero-cost, and maintainable as a single modular monolith.
2.  **Context Truncation & Hallucination:** In long iterative sessions, LLMs occasionally assumed routes or flags existed that had not been implemented or were removed. Every API contract, CLI parameter, and test assertion was cross-referenced directly against active source files.
3.  **UI Detail Nuances:** AI-generated CSS occasionally had visual edge cases (e.g. truncated tooltips, inconsistent modal layering, or missing focus states) which required hands-on refinement to achieve an audit-grade aesthetic.
