# AARA AI Agent Guidelines

**Read this file first, before any other document, when working on this repository.** It is the persistent operating contract for AI coding agents (Claude Code or otherwise). It does not restate architecture content — it points to the documents that already hold that content and tells you which rules to apply while reading and editing.

---

## 1. Project Context

- **AARA / Sentinel Intelligence Platform** — a multi-product platform (Trading Intelligence, Wealth Intelligence) built on the shared **Sentinel Intelligence Engine**.
- **Decision intelligence system** — the platform's core function is producing auditable decisions backed by evidence, not just executing actions. See `docs/architecture/DECISION_INTELLIGENCE_ARCHITECTURE.md`.
- **Governance-first architecture** — evidence over emotion, auditability over automation, human governance over autonomous action. See `docs/architecture/TRADING_CONSTITUTION.md` and `docs/platform/SENTINEL_ENGINE_GOVERNANCE_ARCHITECTURE.md`.
- **Human-controlled investment decisions** — the platform surfaces evidence and recommendations; it does not execute trades autonomously. Execution stays under human governance per the Trading Constitution.

## 2. First Steps Before Any Work

Always, in order:

1. Read this file.
2. Read `docs/DOCUMENT_INDEX.md`.
3. Identify the relevant canonical document for the task from its Canonical Documents table (or `docs/DOCUMENT_GOVERNANCE_MATRIX.md` if the index doesn't cover it).
4. Avoid loading unrelated documentation — do not scan `docs/` broadly when a specific document already answers the question.

## 3. Architecture Principles

- `sentinel_engine/` is the domain core. Products do not reimplement its reasoning, evidence, or governance logic.
- Applications (`applications/trading_intelligence/`, `applications/wealth_intelligence/`, etc.) consume the engine through its defined capability API — they do not reach into its internals.
- UI does not access repositories or services directly. All reads and writes go through the application-service layer.
- CQRS separation: query services read from projections/views, command paths write through the ledger. Do not blend the two.
- Dependency injection (constructor injection) for all cross-layer dependencies — no service locators, no module-level singletons standing in for injected collaborators.
- Events and projections are authoritative — derived state views are rebuilt from the event/ledger record, not treated as a second source of truth.
- Avoid hidden coupling — depend on declared interfaces/contracts, not on another module's internal structure or side effects.

Detail lives in `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`, `docs/platform/SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md`, and `docs/architecture/GRADIO_IMPLEMENTATION_GUIDE.md` — read the relevant one before implementing, don't rely on this summary alone.

## 4. Protected Areas

- **ADR-controlled decisions** (`docs/decisions/`) — package structure, ledger ownership, identity/access model, platform hierarchy. Do not implement around an open or deferred ADR.
- **`dashboard/` is frozen** per ADR-002 (Bot Runtime Protection).
- **Bot runtime protection** — `bot/`, `scheduler/`, `.github/workflows/*.yml`, and the live trading entry points (CLI + watchdog HTTP trigger) documented in `docs/analysis/BOT_RUNTIME_BASELINE.md` are frozen under ADR-002.
- **Ledger ownership** — `database/` and `ledger/` are governed by ADR-004 (Sentinel Ledger Ownership Strategy).
- ADR-006 narrowly reopens 4 specific files for additive Confidence Integrity work — nothing else in the protected set.

**Rule: if a task conflicts with an ADR, stop and report before coding.** Full protected-path list: `docs/DOCUMENT_CONSOLIDATION_PLAN.md`, section "Documents That Must NOT Be Modified."

## 5. Coding Workflow

- Inspect existing code and architecture before modifying anything.
- Follow existing patterns — match the module's current conventions rather than introducing a new style.
- Make the smallest possible change that satisfies the task.
- Preserve tests — do not delete or weaken a test to make a change pass; fix the change instead.
- Add tests for new behavior.
- Avoid unrelated refactoring — don't restructure code that isn't part of the task just because you're already in the file.

## 6. Documentation Rules

Reference:

- `docs/DOCUMENT_INDEX.md` — canonical documents by area, reading order.
- `docs/DOCUMENT_GOVERNANCE_MATRIX.md` — full document inventory, authority levels, known conflicts.
- `docs/DOCUMENT_CONSOLIDATION_PLAN.md` — protected-document list, consolidation status.

Rules:

- ADRs define decisions — nothing overrides them except a superseding ADR.
- Architecture documents define systems (structure, boundaries, data model) — descriptive of design, not step-by-step execution.
- Implementation documents define execution (sequencing, phases, rollout) — non-authoritative for decisions.
- Avoid creating duplicate documents — check `docs/DOCUMENT_GOVERNANCE_MATRIX.md` for an existing document on the same topic first.
- Update the relevant index (`docs/DOCUMENT_INDEX.md`, `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s document-roles table) whenever a major document is added, merged, or archived.

## 7. Claude Code Efficiency Rules

- Do not read all docs by default — load only what the task needs.
- Follow the documentation hierarchy (Section 2 and `docs/DOCUMENT_INDEX.md` Section 1) instead of guessing which document wins.
- Summarize findings before coding — confirm the plan against the canonical document before making changes.
- Ask when architecture ambiguity exists — if two documents disagree or no canonical document covers the area, report it rather than guessing.
- Keep responses concise.
- Prefer commands over explanations when explanations aren't requested.
