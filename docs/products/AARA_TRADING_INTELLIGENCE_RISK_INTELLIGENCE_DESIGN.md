# AARA Trading Intelligence — Risk Intelligence Design

**Status:** Design proposal. Documentation only. No code was created or
modified. `applications/trading_intelligence/`, `sentinel_engine/`, `ledger/`,
`bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`
untouched, confirmed via `git status` before and after.

**Authority:** `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`,
`TRADING_INTELLIGENCE_EVENT_MODEL.md`, `TRADING_INTELLIGENCE_BOUNDARY.md`.

**A naming tension, stated up front rather than glossed over:** the UI
specification already defines **"Risk Intelligence"** as one of six
standalone workspace screens (`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md`
Section 2), portfolio-scoped: current risk-governor state, trigger reason,
recommended vs. actual sizing — not tied to any one decision. This task asks
for Risk Intelligence "as a Decision Center capability," which is a narrower,
decision-scoped concept. These are related but not identical, and this
document treats them as two things, not one:

- **Risk Intelligence (screen)** — already specified elsewhere, portfolio-scoped,
  out of scope for this document except where it shares a data source.
- **Risk Intelligence (Decision Center capability)** — this document's actual
  subject: what risk context a single decision's detail view can show, given
  that decision was made under some portfolio-level risk state at the time.

## 1. Current Risk State

Four genuinely separate places carry a notion of "risk" in this codebase
today — verified by reading each directly, not assumed to be one system:

### Risk models

- **`bot/risk/risk_manager.py`'s `RiskManager`** — the real, live enforcement
  layer. Hard-coded gates the RL agent cannot bypass: `check_daily_loss`,
  `check_weekly_loss`, `check_portfolio_drawdown` (all-time-high drawdown),
  `check_stop_loss` (ATR-aware, flat-percentage fallback), `check_trailing_stop`,
  `check_pdt` (pattern day trading), `sector_check` (concentration limit), and
  `approve_buy()` (the buy-approval gate combining daily/weekly/drawdown/sizing/
  position-count/sector checks). Also `kelly_fraction()` — half-Kelly position
  sizing from recent closed trades. This is the actual risk *enforcement*
  running in production today.
- **`bot/trust_ledger/risk.py`'s `classify()`** — a **read-only, Phase 1A
  Observation Mode** overlay on top of `RiskManager`. Derives a 3-state
  classification (`NORMAL`/`WARNING`/`DEFENSIVE`) from `RiskManager`'s
  existing check methods, with zero new enforcement logic of its own — its
  own docstring states "zero changes to `bot/risk/risk_manager.py`." Writes
  once per cycle (portfolio-scoped, not per-symbol) to `risk_evaluation_events`.
  Explicitly "Observation Mode has zero enforcement authority (FR-1.10a)" —
  `recommend_position_size()` computes what the governor *would* apply, purely
  for later comparison against what actually happened.
- **`dashboard/components/risk.py`'s `render_risk_panel()`** — a **third,
  independent** classification. Computes its own "overall risk" (Low/Medium/High)
  from a simple point-score (`vix > 25`, `max_dd > 8`, `cash_pct < 15`,
  `max_conc > 20`), unrelated to and non-overlapping with `RiskManager`'s gates
  or `bot/trust_ledger/risk.py`'s NORMAL/WARNING/DEFENSIVE states. This is the
  actual, currently-rendered dashboard risk view — display-only, not consulted
  by any enforcement code.
- **`sentinel/backend/domain/enums.RiskGovernorState`** +
  **`sentinel/backend/domain/governance.RiskState`** (`current_state`,
  `drawdown_pct`, `buffer_pct`) + **`sentinel/backend/services/risk_governor_service.RiskGovernorService`**
  — a **fourth**, separate model living in the unrelated `sentinel/` brand/design-system
  scaffold (not `sentinel_engine/`). Reuses the same three state names
  (`NORMAL`/`WARNING`/`DEFENSIVE`) as `bot/trust_ledger/risk.py` by coincidence,
  not by any shared definition — `current_state()` and `check_threshold()` are
  both `raise NotImplementedError` stubs. No relationship exists in code
  between this and any of the three models above, or to `sentinel_engine`, or
  to `applications/trading_intelligence/`.

**None of these four is "the" risk model** — nothing in this codebase has
ever unified them, and this document does not attempt to here either. Section
4 records this as an unresolved-ownership gap rather than picking a winner.

### Risk-related events

- **`sentinel_engine.events.event_types.EventType.RISK_EVALUATED`** — an enum
  value only, verified directly (`sentinel_engine/events/event_types.py`). No
  emitter exists anywhere.
- **`risk_evaluation_events`** (`ledger/schema.sql`) — the real, currently-written
  table backing `bot/trust_ledger/risk.py`. Group A: immutable, hash-chained,
  append-only (update/delete both raise via triggers), with a
  `previous_record_hash` chain-integrity trigger. Columns: `event_id`,
  `timestamp`, `from_state`, `to_state`, `trigger_reason`, `validation_mode`
  (`NATURAL`/`REPLAY_FORCED`), `replay_scenario_id` (nullable),
  `recommended_position_size` (nullable), `actual_position_size` (nullable).
  Per `TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 7, this conceptually
  aligns with `RISK_EVALUATED` but **no code translates one into the other.**

### `sentinel_engine` risk capabilities

**None**, verified by direct search — no `risk` subpackage, no
`RiskEvaluation` dataclass, no risk-bearing service. The only two risk-adjacent
things anywhere in `sentinel_engine` are `Decision.risk_reference: str` /
`DecisionProjection.risk_reference: str` (a plain string pointer, no
structure) and the `RISK_EVALUATED` enum value above. This matches
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section 3's finding:
"no `RiskEvaluation` contract exists anywhere in `sentinel_engine`... a
bigger gap than Evidence: there's no data model to build a reader against
yet, not just a missing reader." Still true, unchanged by this document.

### Dashboard risk components

- **`dashboard/components/risk.py`** — real, live, registered
  (`register(ComponentSpec("risk_panel_out", ...))`,
  `register(ComponentSpec("mkt_intel_out", ...))`). Renders portfolio risk
  cards, a sector-exposure bar chart, and a "Bot Safety Limits" tracker
  (open positions, cash reserve, VIX, today's losses vs. their hard caps).
  This is the actual thing a user sees today.
- **`sentinel/frontend/components/risk_governor_badge.py`** — structure-only
  stub (`raise NotImplementedError`), takes a `risk_state_view: dict`. Docstring
  ties it to `sentinel/backend/domain/enums.RiskGovernorState`, not to
  `bot/trust_ledger/risk.py` or `dashboard/components/risk.py`.

### Existing contracts

- **`Decision.risk_reference: str`** (`sentinel_engine/domain/decision.py`),
  **`DecisionProjection.risk_reference: str`**
  (`sentinel_engine/projections/decision_projection.py`),
  **`DecisionContract.risk_reference: str`**
  (`applications/trading_intelligence/contracts/decision_contract.py`) — the
  only risk-shaped field anywhere in the Decision Center's real data path,
  passed through unchanged end-to-end. `DecisionView`
  (`applications/trading_intelligence/projections/decision_view.py`)
  deliberately excludes it, same as `evidence_reference`, per that module's
  own documented reasoning (risk shown in a separate panel, not the card).
- **`TRADING_INTELLIGENCE_EVENT_MODEL.md` Section 7 already settled**
  `risk_reference`'s cardinality: **many-to-one**. `RISK_EVALUATED` is written
  once per cycle, not once per decision; every decision made within a cycle
  shares that cycle's single `risk_reference`. This is a decided design, not
  an open question — Section 4 below does not re-open it.
- **`sentinel.backend.domain.governance.RiskState`** — a real, typed dataclass
  (`current_state: RiskGovernorState`, `drawdown_pct: float`,
  `buffer_pct: float`) that could structurally resemble a future
  `sentinel_engine` `RiskEvaluation` contract, but lives in the wrong,
  unrelated tree and is not wired to anything.

## 2. Risk Display Model

Defined conceptually only — no contract or field name below is created by
this document.

- **Position risk** — per-symbol exposure: `RiskManager.check_stop_loss()`
  (ATR-aware, flat-percentage fallback), `check_trailing_stop()`, and sector
  concentration (`sector_check()`). Scoped to one open position, not the whole
  portfolio. No `sentinel_engine` contract exists for this today.
- **Portfolio risk** — account-wide state: `RiskManager`'s daily loss,
  weekly loss, all-time-high drawdown, PDT compliance, and max-open-positions
  gates, plus `dashboard/components/risk.py`'s independently-computed
  Low/Medium/High overall score. This is what `bot/trust_ledger/risk.py`'s
  `classify()` distills into `NORMAL`/`WARNING`/`DEFENSIVE` once per cycle —
  the same scope `RISK_EVALUATED` already models (Section 1).
- **Decision risk** — the risk context *a specific decision was made under*.
  Given `risk_reference`'s already-settled many-to-one cardinality (Section 1),
  this is **not** a per-decision risk score — it does not exist and this
  document does not propose inventing one. "Decision risk" can only mean
  "the portfolio risk state of the cycle this decision belongs to," surfaced
  by dereferencing `risk_reference` back to that cycle's single
  `RISK_EVALUATED` event. A UI must not imply a finer-grained score than
  that, per the UI specification's own caution
  (`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` Section 2: "must not imply
  a per-decision risk score that doesn't exist").
- **Risk warnings** — the `WARNING` state itself (`bot/trust_ledger/risk.py`'s
  `check_daily_loss_warning()`: 50-100% of the daily limit, unsent) and
  `dashboard/components/risk.py`'s amber thresholds in its Bot Safety Limits
  tracker (e.g., cash reserve approaching its floor). Conceptually a
  "not yet breached, but approaching" signal, distinct from an actual gate
  block.
- **Risk explanations** — `risk_evaluation_events.trigger_reason` (e.g.,
  "daily loss limit breached", "approaching daily loss limit") is the only
  place a machine-readable *reason* already exists for a risk classification.
  `dashboard/components/risk.py`'s limit-bar `note_str` values (e.g., "Bot
  halts all new buys if daily losses hit 5%") are the closest existing
  analogue to a human-readable explanation, but they're static UI copy, not
  data driven by any event's `trigger_reason`.

## 3. Decision Center Integration

```
Decision
    |
    +-- Evidence Intelligence   (per AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md)
    |
    +-- Risk Intelligence       (this document)
```

Both are proposed as siblings under a decision's detail view, matching how
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section 4 already scopes
Decision Center's future "Evidence section" and "Risk section" as two
separate, independently-blocked additions to `DecisionDetailArea` — not a
single combined "supporting data" concept. Concretely, if built, "Risk
Intelligence" here would be:

- A single portfolio-scoped risk snapshot (Section 2's "decision risk"),
  dereferenced via the decision's `risk_reference`.
- **Not** a duplicate of the standalone Risk Intelligence screen — that
  screen shows the *current* risk state; this capability would show the risk
  state *as of the referenced decision's cycle*, which may be historical.
- Structurally: a new `RiskArea` alongside `DecisionListArea`/`DecisionDetailArea`
  in `applications/trading_intelligence/ui/decision_center/screen.py`,
  following the same framework-independent-dataclass pattern already used
  there — a description of the shape implied by the existing pattern, not a
  commitment or a code change.

## 4. Gaps

- **Missing contracts** — no `RiskEvaluation` (or equivalently-named) dataclass
  exists in `sentinel_engine`. This is the single largest gap: Evidence at
  least has a contract (`sentinel_engine.evidence.Evidence`) even without a
  reader; risk has neither. `sentinel.backend.domain.governance.RiskState`
  (Section 1) is structurally close but lives in an unrelated, unwired tree —
  reusing it as-is (rather than defining a fresh `sentinel_engine` contract)
  is an open option this document does not choose.
- **Missing data sources** — `sentinel_engine` has no path to
  `risk_evaluation_events` at all: no `ProjectionRepository`-equivalent, no
  read method, nothing. Unlike `DecisionProjection` (which at least has an
  abstract `ProjectionRepository.get()` to eventually back), there is no
  equivalent abstraction for risk data to flow through even once a contract
  existed.
- **Missing adapters** — `TRADING_INTELLIGENCE_BOUNDARY.md` Section 6 already
  names a "Risk adapter" as a *future possibility, not designed, not
  implemented* — translating `bot/risk/risk_manager.py` output into
  `RISK_EVALUATED`. Still true. No adapter shape is proposed by this
  document either; Section 5 states why not yet.
- **Unresolved ownership** — which of Section 1's four risk models is
  authoritative for a future Sentinel-side `RiskEvaluation`? Candidates, none
  chosen: (a) `bot/trust_ledger/risk.py`'s NORMAL/WARNING/DEFENSIVE classifier
  — closest to production-real, but itself a Phase 1A observation-only
  overlay, not a settled design; (b) `dashboard/components/risk.py`'s
  Low/Medium/High heuristic — currently user-visible, but ad hoc and
  independently computed, no ledger backing; (c) `sentinel/backend`'s
  `RiskState`/`RiskGovernorState` — typed and structurally closer to a real
  contract, but disconnected from both Trading Intelligence and
  `sentinel_engine`, and itself unimplemented. Picking one is a design
  decision this document deliberately does not make.

## 5. Implementation Readiness

**Can implement now (documentation/design only, no protected-path change):**
- Further design-only work: naming and shaping a candidate `RiskEvaluation`
  contract in prose (not code), resolving the Section 4 ownership question
  as a documented decision, or specifying the exact `RiskArea` fields a
  future Decision Center screen would need. None of this was done here beyond
  what Section 2/3 already state conceptually, since choosing among Section
  4's candidates is itself a decision this document intentionally leaves
  open rather than making unilaterally.

**Requires ADR approval:**
- Adding a `RiskEvaluation` (or equivalent) dataclass to `sentinel_engine/` —
  `sentinel_engine/` is a protected path; any change to it needs a dedicated
  ADR, the same gate `ADR-004` already applies to ledger ownership.
- Building a risk adapter translating `bot/risk/risk_manager.py` or
  `bot/trust_ledger/risk.py` output into a Sentinel contract — crosses the
  one-way boundary `TRADING_INTELLIGENCE_BOUNDARY.md` Section 7 describes;
  `bot/` and `ledger/`/`database/` (schema/writers for `risk_evaluation_events`)
  are both protected paths.
- Choosing which of Section 1's four risk models becomes authoritative — an
  architectural decision with downstream effects on both `sentinel_engine`
  and `bot/trust_ledger/`, not a documentation-only call.

**Blocked by Phase 1A validation:**
- `risk_evaluation_events` itself is Phase 1A Observation Mode data, per
  `bot/trust_ledger/risk.py`'s own docstring: "Observation Mode has zero
  enforcement authority (FR-1.10a)," written specifically to answer "would
  the governor's calls have helped" — a graduation question the data itself
  is still accumulating evidence toward, not a settled classification.
  Building a permanent, user-facing "Risk Intelligence" capability on top of
  a classifier whose own correctness is still under evaluation would present
  unvalidated, observation-only data as if it were authoritative risk
  guidance. This is the clearest reason Section 4's ownership question and
  any adapter work should wait for Phase 1A's validation window to conclude,
  not just for an ADR to be written.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No adapter was created. This document only reads and cites existing
code and prior documentation.
