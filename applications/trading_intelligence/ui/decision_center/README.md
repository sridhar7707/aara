# Decision Center

**Status:** Implemented and runnable (V4). Wired end-to-end to a real
Sentinel Engine read path through this package's own adapters/query
services -- no mock data in the wired application. No authentication or
role management exists. Backend is `bootstrap.py`'s deterministic in-memory
seed data; no persistent storage, live trading, or real market data exists
behind it.

## What this is

The primary intelligence review workspace for Trading Intelligence, and
currently the only implemented screen. Original design:
`docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` (written
before this V4 build; describes an earlier, less complete plan than what's
shipped -- see "Current state" below for what's actually here).

- **`screen.py`** — `DecisionListArea`/`DecisionDetailArea`/
  `DecisionCenterScreen`: framework-independent dataclasses the controller
  returns and the Gradio view renders.
- **`controller.py`** — `DecisionCenterController`, the only place in `ui/`
  allowed to call Trading Intelligence's query services
  (`DecisionQueryService`, `DecisionEvidenceQueryService`,
  `DecisionGovernanceQueryService`). Read failures in evidence/governance/
  approval are caught independently per concern and reported as
  `ReadStatus.ERROR`, never as an exception reaching the UI.
- **`gradio_view.py`** — `DecisionCenterUI`, the Gradio `Blocks` shell:
  application header/nav, decision list (mouse- and keyboard-selectable,
  with a refresh button), and decision detail (identity header,
  confidence shown as "Conviction", lifecycle journey, evidence,
  governance & policy, approval, and empty/error states for each section).
  The "Why?/Rationale" panel is a fixed, decision-independent placeholder
  string -- no rationale/thesis data model exists anywhere in this codebase.
- **`theme.py`** — CSS for the above, built from `brand/design_system/`'s
  existing design tokens; introduces no new brand colors.
- **`mock_data.py`** — a standalone set of hardcoded `DecisionView` objects,
  kept available for demos. Not used by the wired application -- `controller.py`
  never imports it, enforced by `ui/tests/test_ui_structure.py`'s
  `test_controller_does_not_import_mock_data`.

## Current state

- Runnable via `python -m applications.trading_intelligence.main` (or
  `bootstrap.build_application()`), which seeds three illustrative decisions
  through the real Sentinel Engine write path
  (`DecisionService`/`EvidenceService`/`GovernanceService`) and reads them
  back through the adapter/query-service chain above -- the same path a real
  data source would use.
- Decision list, decision detail, confidence/conviction, lifecycle journey,
  evidence, governance & policy, approval, refresh, and mouse/keyboard
  decision selection are all implemented and covered by tests.
- Portfolio Intelligence and Risk Intelligence are navigation-bar-only
  "Coming Soon" placeholders (see `ui/README.md`); Risk Intelligence has no
  `RiskEvaluation` contract or reader anywhere in this codebase.
- Rationale/thesis ("Why?") is a fixed placeholder string, not
  decision-specific content.

## Known gaps

- **No persistent backend.** `bootstrap.py`'s `ProjectionRepository`/
  `LedgerStore` are in-memory only; the real backend choice remains a
  separately governed decision
  (`docs/decisions/ADR-004-sentinel-ledger-ownership-strategy.md`).
- **No "list all decisions" capability.** The UI shows exactly the decision
  ids its composition root was constructed with -- see
  `services/decision_query_service.py`'s own docstring.
- **No live trading, real market data, or production-readiness claim.**
  The seeded decisions are illustrative, not real trading output.
