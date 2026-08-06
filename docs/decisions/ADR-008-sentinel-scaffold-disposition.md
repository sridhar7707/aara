# ADR-008: Sentinel Scaffold Disposition

**Status:** Proposed
**Date:** 2026-08-06

## Context

Two packages both use the name "Sentinel" today:

- **`sentinel_engine/`** — the ADR-001-authoritative Sentinel Intelligence Engine.
  Real, working, tested code: `Decision`, `Event`/`EventType`, `Evidence`,
  `Policy`/`Approval` domain contracts; `DecisionService.create_decision()`
  actually builds events and projections and persists them via repository
  abstractions; a `SentinelEngine` facade genuinely coordinates the three
  services; `adapters/decision_adapter.py` performs real field validation
  (raises `ValueError` on malformed input). 82 tests passing (per ADR-001). A
  structural self-enforcement test (`tests/test_package_imports.py`) AST-scans
  every production file and asserts zero imports of `bot`/`dashboard`/
  `scheduler`/`ledger`/`database`/`applications`. Currently has exactly one
  external consumer: `applications/trading_intelligence/adapters/
  sentinel_projection_decision_source.py` imports `sentinel_engine.projections`
  and `sentinel_engine.repositories` directly (read-only, not wired to a live
  backend).

- **`sentinel/`** — a pre-ADR-001 scaffold (commits `ff30f1c`, `0bcd5cb`),
  never updated after `sentinel_engine/` superseded it. `sentinel/README.md`:
  *"Scaffolding only. No business logic, no persistence, no execution. Every
  service, repository, and API function raises `NotImplementedError`."*
  Verified directly across every layer — `backend/services/approval_service.py`,
  `backend/events/hash_chain.py`/`event_writer.py`, `frontend/app.py`,
  `frontend/workspaces/governance_status.py`, `frontend/components/
  governance_badge.py` — every method body is `raise NotImplementedError`,
  including `frontend/app.py`'s `if __name__ == "__main__": raise
  NotImplementedError`. Its 18 test files under `tests/unit/` are uniformly
  `pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")`
  with empty (docstring-only) test bodies — zero assertions exist anywhere in
  the package.

  `sentinel/` has zero external dependents: `grep` for
  `sentinel.frontend`/`sentinel.backend`/`from sentinel import`/`import
  sentinel` outside the package returns nothing in the active working tree
  (only a stale git worktree,
  `.claude/worktrees/sentinel-phase2a-governance-freeze/`, contains a
  duplicate copy — not part of this repository's active tree).
  `.github/workflows/ci.yml` runs `pytest sentinel_engine/tests` only, never
  `sentinel/tests`. No root `requirements.txt`/`requirements_space.txt`
  references it; `sentinel/requirements.txt` is a separate, unwired manifest.

  Two soft, non-breaking references exist: `tools/validators/
  code_scan_validator.py` lists `sentinel/frontend` as a brand/UI scan target
  (degrades safely if the path is absent — `if not os.path.exists(directory):
  continue`), and `docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md` cites
  specific `sentinel/frontend/` file paths as evidentiary grounding for a
  navigation decision.

ADR-001 already settled the structural question — `sentinel_engine/` is
authoritative, and reorganizing `sentinel/` in place was explicitly named and
rejected ("Rejected Alternative" section) — but never stated what should
happen to the `sentinel/` scaffold itself now that its replacement exists and
is built out. It has sat ungoverned since.

## Decision

**Archive `sentinel/`.** It contains no working functionality (§Context), has
no hard dependents (§Context), and its structural role has already been
superseded by `sentinel_engine/` per ADR-001. Archiving means relocating it
out of the active package path (e.g. under an `archive/` location) or marking
it `ARCHIVE` status in place per `CODEBASE_MIGRATION_MATRIX.md`'s own status
vocabulary — "preserve, no active development" — not deleting it. Git history
preserves the content identically either way, so archiving costs nothing in
data safety while removing dead weight from the active tree.

**This ADR does not perform the archive.** Like ADR-005, this is a decision
record, not an executed action — no file under `sentinel/`, `sentinel_engine/`,
or elsewhere has been moved, renamed, or modified to produce it.

## Preservation of Vocabulary

`sentinel/backend/domain/enums.py` defines five enums with no code behind
them, but with design value not fully duplicated elsewhere. Before or
alongside archiving, this vocabulary must be captured somewhere committed and
discoverable — its only current documentation (`docs/architecture/
IMPLEMENTATION_HANDOFF.md`, `GRADIO_IMPLEMENTATION_GUIDE.md`) is gitignored
per `AARA_ARCHITECTURE_AUTHORITY.md`'s own hierarchy ("local working drafts...
not the project's controlled source of truth").

- **`GovernanceAction`** (`APPROVE_DECISION`/`DEFER_DECISION`/
  `DECLINE_DECISION`/`ESCALATE_REVIEW`) — fills a real gap:
  `sentinel_engine/governance/approval.py`'s `Approval.status` is an untyped
  `str` today.
- **`RiskGovernorState`** (`NORMAL`/`WARNING`/`DEFENSIVE`) — no equivalent
  state-machine concept exists anywhere in `sentinel_engine/` today.
- **`DecisionState`** (`IDENTIFIED`/`EVALUATED`/`GOVERNED`/`APPROVED`/
  `DISPATCHED`/`EXECUTED`/`REVIEWED`/`CLOSED`) — a second, differently-grained
  decision-lifecycle vocabulary alongside `sentinel_engine/events/
  event_types.py`'s `EventType` (`CANDIDATE_EVALUATED`/`DECISION_CREATED`/
  `RISK_EVALUATED`/`DECISION_EXECUTED`/`DECISION_OUTCOME_RECORDED`). The two
  are adjacent, not equal — `GOVERNED` and `REVIEWED` have no `EventType`
  counterpart.
- **`SentinelRole`** (`INVESTOR`/`ADVISOR`/`RISK_OFFICER`/
  `COMPLIANCE_OFFICER`/`ADMINISTRATOR`) — self-marked "Placeholder... Not
  enforced in Phase 2A." A different axis from
  [ADR-003](ADR-003-aara-identity-and-product-access.md)'s role model
  (`Trading Intelligence User`/`Wealth Intelligence User`/`AARA Super User /
  Platform Administrator`): ADR-003 answers "which product can this user
  open" (product entitlement); `SentinelRole` answers "in what governance
  capacity is this user acting on a decision." Neither subsumes the other.
- **`OperationalMode`** (`RESEARCH`/`PAPER`/`SUPERVISED`/
  `GOVERNED_AUTOMATION`) — no equivalent in `sentinel_engine/` or
  `applications/platform/`. Adjacent to, but not the same as, `bot/`'s
  paper-vs-live execution distinction (a governance-supervision mode, not the
  trading execution backend).

## Explicit Mapping

**Engine concepts** (product-agnostic, belong in `sentinel_engine/`'s
domain/governance layers if and when implemented):
- `GovernanceAction` — types `Approval.status`. Direct, ready adoption.
- `RiskGovernorState` — the state enum itself (state is reusable across any
  future product with a governed risk posture).
- `OperationalMode` — carried forward as a placeholder; nothing consumes it
  yet, no existing conflict to resolve.

**Product concepts** (belong in `applications/trading_intelligence/` because
the triggering logic is Trading-Intelligence-specific, even where the state
enum itself lives in the engine):
- `RiskGovernorState`'s triggering logic — concrete drawdown-percentage
  threshold checks are portfolio/trading-specific
  (`sentinel/backend/services/risk_governor_service.py`'s
  `check_threshold(drawdown_pct)`), matching
  `TRADING_INTELLIGENCE_BOUNDARY.md`'s existing pattern of a
  Trading-Intelligence-owned risk adapter feeding engine-level state.

**Unresolved — require their own future decision before any code destination
is chosen:**
- `DecisionState` vs. `EventType` — needs a reconciliation decision (extend
  `EventType`, keep both at different granularities with an explicit mapping,
  or something else) before `DecisionState` is adopted anywhere as code.
- `SentinelRole` vs. ADR-003's role model — needs a reconciliation decision
  (additive layers — product entitlement plus governance capacity — or a
  merged model) before it is placed in `applications/platform/identity/` or
  anywhere else. Until resolved, this vocabulary is **documentation only**:
  recorded here, not implemented.

## Boundaries

- **ADR-001 remains authoritative and unchanged.** `sentinel_engine/`'s
  package structure (domain/events/evidence/governance/ledger/projections/
  repositories/services/adapters) is not altered, renamed, or restructured by
  this ADR. This ADR only decides the disposition of the scaffold ADR-001
  already superseded.
- **ADR-002 remains unchanged.** `bot/`, `dashboard/`, `scheduler/`,
  `.github/workflows/`, `database/`, and top-level `ledger/` are untouched —
  this ADR does not reference, move, or modify any file in those paths.
- **ADR-007's hierarchy remains unchanged.** Sentinel Intelligence Engine
  stays the sole, permanent layer between AARA Systems and every product; this
  ADR does not rename, demote, or restructure that identity. Archiving the
  unrelated `sentinel/` scaffold has no bearing on the engine's name or role —
  they are different packages with a coincidentally similar name (see
  §Context).

## Rejected Alternatives

**Delete `sentinel/` outright.** Rejected: no benefit over archiving (git
history preserves content identically either way), and outright deletion
risks losing the one committed copy of the vocabulary in §Preservation of
Vocabulary before it is confirmed captured elsewhere.

**Leave `sentinel/` as-is, undecided.** Rejected: it has already sat
ungoverned since ADR-001 with zero active development and zero external
dependents — leaving it undecided invites exactly the ambiguity ADR-001 itself
was written to resolve for the engine's structure, now recurring for the
scaffold's disposition.

## Consequences

- `sentinel/` is marked for archival; the two soft references
  (`tools/validators/code_scan_validator.py`'s `SCAN_TARGETS` entry and
  `AARA_PLATFORM_SHELL_ARCHITECTURE.md`'s file-path citations) will need a
  one-line update at archive time — not performed by this ADR.
- `GovernanceAction`, `RiskGovernorState`, and `OperationalMode` are cleared
  for future adoption into `sentinel_engine/` (and, for `RiskGovernorState`'s
  trigger logic, `applications/trading_intelligence/`) without requiring
  further disposition debate — only implementation, whenever that work is
  scheduled.
- `DecisionState` and `SentinelRole` remain open questions, explicitly not
  resolved by this ADR, pending their own reconciliation decisions.
- No code, test, workflow, or deployment change results from this ADR.
