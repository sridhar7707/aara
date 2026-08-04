# Trading Intelligence Contract Gap Analysis

**Purpose:** Read-only comparison of `bot/`'s actual trading-lifecycle data
structures against `sentinel_engine`'s `Decision`/`Event`/`EventType` contracts and
`decision_adapter.to_decision()`. Answers unresolved question #1 from
`TRADING_INTELLIGENCE_BOUNDARY.md`. **No code was modified to produce this
document** — confirmed via `git status` on all protected paths before and after.

**Method:** Direct reading of `bot/trust_ledger/*.py` (writer functions define the
actual row shapes, more reliable than inferring from `schema.sql`), `bot/risk/risk_manager.py`,
`bot/capital/pool.py`, `bot/execution/base.py`, `bot/strategy/ensemble.py`. Not
exhaustive of every field in every file — flagged where deeper reading would be
needed.

---

## 1. Current Bot Data Structures

### `bot/trust_ledger/` (writes through top-level `ledger/` package — `ledger.ledger.append_ledger_row`, `ledger.db.init_db`, DB file `data/trust_ledger.db`)

| Table | Written by | Fields |
|---|---|---|
| `candidate_evaluation_events` | `candidates.py` | `candidate_event_id`, `timestamp`, `asset`, `screening_version`, `screening_results` (dict), `data_available`, `required_models_available`, `evaluation_requested`, `evaluation_completed` |
| `decision_events` | `decisions.py` | `decision_id`, `candidate_event_id` (FK), `timestamp`, `asset`, `action`, `event_type` (`EXECUTED` \| `QUALIFIED_REJECTION`), `portfolio_snapshot` (dict), `market_context` (dict), `model_outputs` (dict), `risk_checks` (dict), `final_confidence`, `deployment_manifest_id`, `intent` (dict: `primary_intent`, `contributing_modules`, optionally `thesis`/`invalidation_point`/`expected_return_basis_points`/`override_reason`), `data_completeness` (dict) |
| `risk_evaluation_events` | `risk.py` | `event_id`, `timestamp`, `from_state`, `to_state` (`NORMAL`\|`WARNING`\|`DEFENSIVE`), `trigger_reason`, `validation_mode`, `replay_scenario_id`, `recommended_position_size`, `actual_position_size`. **No `decision_id` or `asset` column — written once per cycle, portfolio-level, not per-decision.** |
| `decision_outcome_events` | `outcomes.py` | `outcome_id`, `decision_id` (FK, references the original BUY), `exit_timestamp`, `gross_return`, `net_return`, `holding_period_days`, `cost_breakdown` (dict), `cost_model_id` |
| `constitution_enforcement_events` | `constitution.py` | `event_id`, `decision_id` (FK), `rule_id`, `rule_name`, `check_timestamp`, `check_result` (`PASS`\|`ESCALATED`\|`FAIL`), `action_taken`, `reason`. Six rows written per decision (one per Trading Constitution rule). |
| `data_quality_events` | `data_quality.py` | `event_id`, `timestamp`, `source`, `status` (`HEALTHY`\|`DEGRADED`\|`DOWN`), `detail`. Plain insert, explicitly **not** part of the hash chain (not in `ledger._LEDGER_TABLES`, per the module's own docstring). |

### `bot/capital/pool.py` (separate SQLite tables, in the *operational* trades DB, not `data/trust_ledger.db`)

| Table | Fields |
|---|---|
| `capital_pools` | `id`, `name`, `status`, `allocated_amount`, `available_cash`, `invested_amount`, `reserve`, `realized_profit`, `profit_withdrawn` |
| `capital_ledger` | `id`, `pool_id`, `event_type` (`deposit`\|`buy`\|`sell`\|`withdrawal`), `amount`, `balance_after`, `symbol`, `notes`, `created_at` |

This is a **fourth** distinct ledger-like structure in this codebase (alongside
top-level `ledger/`, `bot/trust_ledger/`'s use of it, and `sentinel_engine/ledger/`'s
still-unimplemented abstraction) — not previously inventoried in
`TRADING_INTELLIGENCE_BOUNDARY.md` or `BOT_DEPENDENCY_MAP.md`.

### `bot/risk/risk_manager.py`

`RiskManager` is a stateful object (`daily_start_value`, `weekly_start_value`,
`portfolio_high`, `halted`, `day_trade_log`), not a data record — it's queried via
methods (`check_daily_loss`, `check_portfolio_drawdown`, `check_weekly_loss`,
`check_daily_loss_warning`) that `bot/trust_ledger/risk.py`'s `classify()` calls to
*derive* the `risk_evaluation_events` row. There is no persisted "risk evaluation
for this decision" object — only the portfolio-level state machine described above.

### `bot/execution/base.py`

`Executor` Protocol (structurally satisfied by `AlpacaClient` and `PaperExecutor`,
no shared base class): `buy(symbol, notional, limit_price) -> dict | None`,
`sell(...)`, `sell_market(...)`, `wait_for_fill(order_id, timeout_secs) -> float`,
`get_fill_price(order_id) -> float | None`. The exact shape of the `dict` returned
by `buy`/`sell` was not read in this pass (would require reading
`alpaca_client.py`/`paper_executor.py` implementations, not just the Protocol) —
flagged, not assumed.

### `bot/strategy/ensemble.py`

`ensemble_signal(...)` returns actions including `"STRONG_BUY"` and `"BUY"` (not
just `BUY`/`SELL`/`HOLD` as seen at the decision layer) — a richer action
vocabulary than what reaches `decision_events.action`. `ensemble_confidence(...)`
computes confidence separately. Not traced in this pass whether/where
`STRONG_BUY` collapses to `BUY` before reaching `bot/trust_ledger/decisions.py`.

---

## 2. Mapping to `sentinel_engine.domain.decision.Decision`

`Decision`: `decision_id`, `symbol`, `action`, `timestamp`, `confidence`, `evidence_reference`, `risk_reference`

| `Decision` field | `decision_events` equivalent | Fit |
|---|---|---|
| `decision_id` | `decision_id` | Direct match. Bot's format (`DEC-<ts>-<symbol>-<hex>`) is a valid `str`. |
| `symbol` | `asset` | Direct match, name differs only. |
| `action` | `action` | Direct match as a plain `str` — but see Section 5 on vocabulary richness upstream. |
| `timestamp` | `timestamp` | **Type mismatch** — bot stores an ISO-format `str` (`datetime.now(timezone.utc).isoformat()`); `decision_adapter.to_decision()` requires `isinstance(timestamp, datetime)` and raises `ValueError` on a plain string. Needs `datetime.fromisoformat()` conversion — see Section 5. |
| `confidence` | `final_confidence` | Direct match, both numeric. |
| `evidence_reference` | **No direct equivalent** | `decision_events` embeds `market_context`, `model_outputs`, `data_completeness` directly rather than referencing an external evidence record, plus a `candidate_event_id` FK to `candidate_evaluation_events`. See Section 4/5. |
| `risk_reference` | **No direct equivalent** | `decision_events.risk_checks` is an embedded dict, not a reference. The separate `risk_evaluation_events` table is not decision-scoped at all (no `decision_id` column) — see Section 6. |

## 3. Mapping to `EventType` Lifecycle

`EventType`: `CANDIDATE_EVALUATED`, `DECISION_CREATED`, `RISK_EVALUATED`, `DECISION_EXECUTED`, `DECISION_OUTCOME_RECORDED`

| `EventType` | Bot equivalent | Fit |
|---|---|---|
| `CANDIDATE_EVALUATED` | `candidate_evaluation_events` row | Conceptually direct — one row per (symbol, trading day). |
| `DECISION_CREATED` | `decision_events` row (any `event_type`) | Partial — see below, bot doesn't separate "created" from "executed" as two events. |
| `RISK_EVALUATED` | `risk_evaluation_events` row | Conceptually direct, but **scope mismatch**: bot's version is once-per-cycle/portfolio-level, not once-per-decision. Sentinel's `EventType` implies a per-decision event given `Decision.risk_reference` exists. |
| `DECISION_EXECUTED` | `decision_events` row where `event_type == "EXECUTED"` | Partial — see below. |
| `DECISION_OUTCOME_RECORDED` | `decision_outcome_events` row | Conceptually direct, `decision_id` FK present and correctly scoped. |

**Structural mismatch, not just naming:** sentinel's model implies `DECISION_CREATED`
and `DECISION_EXECUTED` are two separate events in a decision's lifeline. Bot writes
**exactly one** `decision_events` row per (symbol, cycle) — its `event_type` field
(`EXECUTED` vs `QUALIFIED_REJECTION`) is a *classification of that single row*, not
a second event. A `QUALIFIED_REJECTION` never gets an `EXECUTED` follow-up event —
it's terminal. Collapsing bot's one row into sentinel's two-event model isn't a
field-rename; it's a decision about whether to always emit `DECISION_CREATED` and
conditionally also emit `DECISION_EXECUTED`, or something else. Not resolved here.

**Event types with no `EventType` equivalent at all:**
- `constitution_enforcement_events` (6 rows/decision, rule-level pass/escalate results)
- `data_quality_events` (portfolio-level health log, explicitly non-hash-chained)
- `capital_ledger` (deposit/buy/sell/withdrawal — pool balance events)

None of these map onto any of the 5 existing `EventType` values. An adapter that
only handles the 5 known types would silently drop these three categories
entirely, not raise an error — worth flagging explicitly given `decision_adapter`'s
existing pattern is to validate and reject, not silently ignore.

## 4. Missing Fields

- `Decision.timestamp` needs a `datetime` object; bot provides an ISO `str`.
  Missing: the parsing step, not the data itself.
- `Decision.evidence_reference` has no populated source field in `decision_events`.
  The closest candidates (`candidate_event_id`, or the embedded `market_context`/
  `model_outputs`/`data_completeness` dicts) are different *shapes* of "evidence" —
  one is a foreign key to a single upstream table, the others are inline data that
  would need to become a `sentinel_engine.evidence.Evidence` record first, with its
  own `evidence_id` that `evidence_reference` could then point to. No such
  record-creation step exists anywhere today.
- `Decision.risk_reference` has no populated source field either, and per Section 3,
  the underlying `risk_evaluation_events` data isn't even scoped to individual
  decisions today — there's no per-decision risk-evaluation identifier to
  reference, only a per-cycle one.

## 5. Fields Requiring Adapters

- **Timestamp parsing** — `datetime.fromisoformat(decision_events["timestamp"])`
  before calling `decision_adapter.to_decision()`. Mechanical, but currently absent
  anywhere in the codebase (nothing calls `to_decision()` at all yet).
- **Action vocabulary normalization** — `bot/strategy/ensemble.py` produces
  `STRONG_BUY`/`BUY`/etc.; `decision_events.action` and
  `bot/trust_ledger/decisions.py`'s `_PRIMARY_INTENT` mapping only recognize
  `BUY`/`SELL`/`HOLD`/`REJECT`. Whatever normalization already happens between
  those two layers (not traced in this pass) determines what actually reaches
  `decision_adapter` — worth verifying before assuming `action` is a clean pass-through.
- **`evidence_reference` construction** — requires a decision (not made here) on
  whether it should point at `candidate_event_id` as-is, or at a newly-synthesized
  `sentinel_engine.evidence.Evidence` record built from `market_context` +
  `model_outputs` + `data_completeness`.
- **`risk_reference` construction** — requires a decision on whether to (a) leave
  it pointing at nothing meaningful given the scope mismatch, (b) change
  `bot/trust_ledger/risk.py` to also write a per-decision risk record (a change to
  protected code, out of scope here), or (c) accept that `risk_reference` maps to
  the *most recent* portfolio-level `risk_evaluation_events` row rather than a
  decision-specific one.

## 6. Migration Risks

- **`risk_evaluation_events` is portfolio/cycle-scoped, not decision-scoped.** This
  is a structural mismatch, not a mapping exercise — `Decision.risk_reference`'s
  implicit assumption (one risk evaluation per decision) doesn't hold in the
  current data model. Any adapter design that assumes otherwise will produce
  incorrect or misleading references.
- **`DECISION_CREATED`/`DECISION_EXECUTED` collapse.** Bot's single-row-per-decision
  model vs. sentinel's two-event model is a real semantic difference that a naive
  1:1 adapter would get wrong (e.g., always firing both events for every decision
  would misrepresent `QUALIFIED_REJECTION` rows, which never execute).
- **Three whole event categories have no `EventType` equivalent** (constitution
  enforcement, data quality, capital ledger). If Phase 2 wiring only targets the 5
  existing `EventType` values, this data either needs new `EventType` additions or
  is left out of the Sentinel-side audit trail entirely — a scope decision, not
  a technical blocker.
- **A fourth, previously uncounted ledger** (`capital_ledger`, in the operational
  trades DB) adds to the "which ledger is authoritative" question already open in
  `TRADING_INTELLIGENCE_BOUNDARY.md`'s Data Ownership section.
- **`decision_outcome_events.decision_id`** only references the original BUY, per
  `outcomes.py`'s own docstring — a SELL is its own independent `decision_events`
  row. Any adapter connecting outcomes back to decisions needs to preserve this
  asymmetry, not assume outcome-to-decision is always 1:1 in the naive sense.
- **This analysis did not verify `alpaca_client.py`/`paper_executor.py`'s actual
  fill-data shape** (Section 1) — `DECISION_EXECUTED` mapping design would need
  that before being finalized.

## 7. Recommendations

(Documented for a future design pass — none of these are decided or implemented
here.)

1. Resolve the `DECISION_CREATED`/`DECISION_EXECUTED` collapse question before
   building any adapter beyond `decision_adapter` — it affects every other event
   type's design, not just this one.
2. Decide `evidence_reference`'s shape (FK-passthrough vs. synthesized `Evidence`
   record) before designing a candidate/evidence adapter — this determines whether
   `sentinel_engine.evidence.Evidence` needs to exist as real data or just be
   referenced by an existing bot ID.
3. Treat `risk_reference`'s scope mismatch as a data-model question first,
   adapter-design question second — no adapter can invent a per-decision risk
   record that doesn't exist upstream.
4. If constitution/data-quality/capital-ledger events are meant to appear in the
   Sentinel audit trail eventually, that requires extending `EventType` (a
   `sentinel_engine/` change, permitted under ADR-001/ADR-002 since it doesn't
   touch protected paths) — worth deciding whether that's in scope before Phase 2
   adapter work begins, not after.
5. Read `alpaca_client.py`/`paper_executor.py`'s fill-dict shape before designing
   the execution adapter mentioned in `TRADING_INTELLIGENCE_BOUNDARY.md` — this
   document deliberately stopped short of that to stay within its inspection list.
6. None of the above requires touching `bot/`, `scheduler/`, or any protected path
   — all of it can be resolved as `sentinel_engine/` design work (new dataclasses,
   expanded `EventType`, adapter functions) with `bot/` treated as a read-only data
   source throughout.
