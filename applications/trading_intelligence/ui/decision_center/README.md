# Decision Center

**Status:** V1 prototype — mock data only. No `sentinel_engine`, `bot`,
`dashboard`, `database`, or `ledger` connection; no real service wiring; no
authentication or role management.

## What this is

The primary intelligence review workspace for Trading Intelligence. Full
design: `docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`.

- **`screen.py`** — `DecisionListArea` (decision list + empty state),
  `DecisionDetailArea` (confidence/status/timestamp display formatting),
  `DecisionCenterScreen` (composes the two). Framework-independent dataclasses,
  no rendering engine.
- **`mock_data.py`** — `get_mock_decisions()` (3 hardcoded `DecisionView`
  objects) and `build_mock_screen()` (assembles a ready-to-use
  `DecisionCenterScreen` from them).

## Implementation phases

Per the design document's Section 8:

1. **Mock UI — done (this V1).** Hardcoded `DecisionView` objects, no real
   service wiring.
2. **Connect `DecisionQueryService`** — not started. Blocked on a
   `ProjectionRepository` backend existing (ADR-004) and on the "list all
   decisions" gap noted in the design document's Section 7 (`DecisionQueryService`
   currently requires known decision IDs, not a query-all).
3. **Add evidence/risk/governance** — not started. Blocked on the missing
   `RiskEvaluation` contract, the evidence cardinality question, and
   `approval_events` having no real writer anywhere.
