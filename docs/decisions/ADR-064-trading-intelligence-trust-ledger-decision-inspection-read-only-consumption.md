# ADR-064 — Trading Intelligence: Read-Only Consumption of the Published `trust_ledger.db` Snapshot for a Decision Ledger Inspection Surface

**Status:** Accepted
**Date Proposed:** 2026-09-03
**Date Accepted:** 2026-09-03
**Decision Type:** Architecture / Governance — External Data-Source Admission (read-only consumer); narrow exception to ADR-055 §5.6 for this ADR's scope only
**Related ADRs:** ADR-055 (the sibling `trades.db` snapshot decision — this ADR authorizes a narrow exception to its §5.6 read prohibition for this ADR's scope only; ADR-055 itself is **not** modified and every other clause of ADR-055 remains in force), ADR-054 (the first read-only external-data-provider admission for Trading Intelligence — same consumer pattern), ADR-043 (precedent: a narrow, read-only Trust Ledger decision read authorized without reopening ADR-004), ADR-004 (`Deferred` — this ADR does not select, prefer, constrain, reopen, or reinterpret Option A/B/C), ADR-002 (`bot/` / `ledger/` / `scheduler/` / `dashboard/` / `database/` / `.github/workflows/*.yml` / managed SQLite files frozen — this ADR requires **no** exception), ADR-059 (canonical production decision identity `decision_id` — cited, unchanged), ADR-061 (generalized `ReadResult` / `IntegrationHealth` tri-state contract — reused), ADR-019 (`Accepted — Implementation Deferred`; bot-side asset-universe / `screener_log` screening funnel — acknowledged, not modified or depended on), ADR-022 (`Accepted`; product-facing governance/audit/evidence/decision-chain UI belongs inside the owning product's application package — this ADR's UI surface is consistent with it), ADR-058 (ratification rule D1–D4 — this ADR is authoritative only once landed under D2)

---

## 1. Context

### 1.1 The gap

Trading Intelligence's inspection surfaces today can show, from the ADR-055
`trades.db` snapshot, a trade and its realized outcome (Wave 2A / Wave 2B).
They cannot show **what AARA actually decided** — the recorded candidate
evaluations, the BUY / SELL / HOLD / REJECT decisions the live governed
write path produced, and the one recorded reason (a failing entry gate, or
"no exit condition met") attached to each. That information exists,
deterministically and append-only, in the Trust Ledger
(`data/trust_ledger.db`), in two hash-chained tables:

- `candidate_evaluation_events` — one row per `(asset, trading day)`,
  keyed by `candidate_event_id`, carrying the screener's own factor scores
  (`screening_results`) and four evaluation-status booleans.
- `decision_events` — one row per BUY / SELL / HOLD / REJECT a symbol
  reached in a cycle, keyed by `decision_id`, referencing its
  `candidate_event_id` via a real, DB-enforced foreign key, and carrying
  `action`, `event_type` (`EXECUTED` / `QUALIFIED_REJECTION`),
  `final_confidence`, `model_outputs`, `risk_checks` (which contains the
  recorded `gate_trace` for a rejection, or `exit_reason` for a HOLD/SELL),
  `intent`, `market_context`, and `data_completeness`.

The deterministic relationship
`candidate_evaluation_events.candidate_event_id`
→ `decision_events.candidate_event_id` → `decision_events.decision_id`
is real, FK-enforced (`ledger/schema.sql`), and further guarded by
`trg_decision_events_requires_completed_evaluation` (a `decision_events`
row may only cite a candidate whose `evaluation_completed = 1`).

### 1.2 Why this is not already permitted

**ADR-055 §5.6** explicitly places `candidate_evaluation_events`,
`decision_events`, and `decision_outcome_events` (and the other
hash-chained event tables) **out of scope** for the Trading Intelligence
`trades.db` snapshot consumer: *"those remain gated behind ADR-004 /
'Q1'. The four in-scope adapters read only the plain application-state
tables (`trades`, `screener_log`, capital/regime/position tables)."*
**ADR-055 §5.11** prohibits that ADR's implementation from amending,
reopening, or reinterpreting that boundary. A separate, accepted
governance instrument is therefore required for Trading Intelligence to
read any part of the Trust Ledger event tables.

### 1.3 Why the mechanism is already available

The raw `trust_ledger.db` file is **already published** by the existing bot
mechanism: `bot/monitor/sync_db.py::push_ledger_db()` uploads it, every
trading cycle, to the **same** HuggingFace *dataset* repository identified
by `config.HF_DB_REPO_ID` (today `ksri77/ai-trading-bot-db`), `repo_type
= "dataset"`, filename `trust_ledger.db` — sitting alongside the `trades.db`
file ADR-055 already authorizes Trading Intelligence to pull. No new
producer, no new repository, no new secret, and no `bot/` change is needed
to obtain it.

`applications/trading_intelligence/adapters/trades_db_snapshot.py`
(authorized by ADR-055 §2) is the proven, product-owned, consumer-only
fetch primitive for this exact situation: `SPACE_ID`-gated,
`hf_hub_download(repo_id=config.HF_DB_REPO_ID, filename=..., repo_type=
"dataset")` inside a daemon thread with a hard 20-second timeout, atomic
`os.replace` finalize, fail-closed `ReadResult` / `IntegrationHealth`, a
local copy inside the product's own `.runtime/` area — never the bot's
working DB path.

### 1.4 Precedent for a narrow read of the ledger

**ADR-043** (Accepted) authorized a narrow, read-only, in-memory,
diagnostic read of a **single named `decision_id`** from
`data/trust_ledger.db`, and its §5 explicitly excludes "ADR-004 Option
A/B/C selection or amendment" from its grant. ADR-043 establishes that a
scoped, read-only Trust Ledger read can be authorized **without** touching
ADR-004. ADR-043 does not authorize a product surface, automation, a
snapshot consumer, persistence, or UI wiring — this ADR does not extend
ADR-043's implementation; it defines its own product read scope from the
published snapshot.

### 1.5 The product this authorizes

A single additive **"Decision Ledger Inspection"** section inside the
existing Performance & Learning screen: for each `candidate_event_id`, its
evaluation status and screener provenance; grouped under it, each
`decision_id` with its `action` / `event_type` / recorded confidence /
model signals / the one recorded gate-or-exit fact / decision-time data
completeness. It exposes **no** outcome data of any kind and makes **no**
attempt to connect a Trust Ledger `decision_id` to a `trades.db` trade
row.

---

## 2. Decision

**Trading Intelligence may consume the already-published `trust_ledger.db`
dataset artifact as a read-only, ephemeral local snapshot, for the sole
purpose of a Decision Ledger Inspection surface, subject to every
constraint in this section.**

This **authorizes a narrow exception to ADR-055 §5.6 for the exact scope
defined in this ADR only.** ADR-055 itself is **not** modified, and every
other clause of ADR-055 — including the remainder of §5.6 for every Trust
Ledger table and every column outside the §2.4 allowlists — remains in
full force. No other Trust Ledger read by Trading Intelligence is
authorized by this ADR.

### 2.1 Acquisition — runtime fetch only

1. **Source.** The existing published dataset repo identified by
   `config.HF_DB_REPO_ID`, file `trust_ledger.db`, `repo_type =
   "dataset"`. No new repo, no new secret, no new producer.
2. **Mechanism.** A Trading-Intelligence-owned fetch primitive that
   **duplicates** the `adapters/trades_db_snapshot.py` shape (never
   imports it or any `bot/` / `dashboard/` / `scheduler/` module),
   parametrised on `filename = "trust_ledger.db"` and a distinct
   product-owned local path under
   `applications/trading_intelligence/.runtime/` (e.g.
   `trust_ledger_snapshot.db`). It is **`SPACE_ID`-gated** (no fetch, no
   `config` import, no `huggingface_hub` import, no network when not
   running inside a HuggingFace Space), runs the transfer inside a daemon
   thread with a **hard timeout**, finalises via **atomic `os.replace`**,
   and returns a **fail-closed `ReadResult`** (`value = None` plus an
   `IntegrationHealth` naming the reason on any failure).
3. **Consumer only.** The primitive never calls `upload_file`,
   `upload_folder`, `create_commit`, `HfApi` write, or any write/delete
   operation against any HuggingFace repo, and never uses a push-target
   repo id. The bot (`bot/monitor/sync_db.py`) remains the sole
   producer/publisher of `trust_ledger.db`.
4. **Never the managed file.** The fetch target is a **separate
   product-owned copy**. It is **never** `data/trust_ledger.db`, never the
   bot's working ledger path, and never any path managed by `bot/` or
   top-level `ledger/`.
5. **Ephemerality.** The local copy is a cache for the running Space
   process only; it carries no persistence guarantee and may be re-fetched
   or discarded between restarts.
6. **Deploy-time fetch is explicitly out of scope.** This ADR authorizes
   only the Space-**runtime** placement (the option ADR-055 §2 states
   "requires no ADR-002 exception"). Staging a `trust_ledger.db` pull into
   `deploy_trading_intelligence.yml`, or any other deploy-time acquisition,
   is **not** authorized here and would require its own separate
   governance review (the ADR-056 / ADR-062 pattern).

### 2.2 Read-only SQLite

Every connection to the local snapshot is opened
`sqlite3.connect("file:<snapshot>?mode=ro", uri=True)`. The implementation
issues **no** `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`,
`REPLACE`, `VACUUM`, write-mode `PRAGMA`, `-wal`/`-shm` handling, or
checkpoint. No Trust Ledger write of any kind is authorized. The snapshot
is treated as an immutable file for the life of the process.

### 2.3 Exactly two tables

Only `candidate_evaluation_events` and `decision_events` may be read. Every
other table in `ledger/schema.sql` — including, explicitly,
`decision_outcome_events`, `constitution_enforcement_events`,
`risk_evaluation_events`, `deployment_manifest_events`,
`decision_confidence_events`, `approval_events`, `cost_models`,
`deployment_manifests`, and the `decision_state` view — is **out of
scope** and must not be read.

### 2.4 Explicit column allowlist

No `SELECT *`. The reader's SQL enumerates **only** the columns positively
named in the two allowlists below (the authoritative names are from
`ledger/schema.sql`). These two lists are the authoritative and exhaustive
statement of what may be consumed; nothing outside them is in scope.

**`candidate_evaluation_events` — authorized columns (complete list):**

| Column | Purpose |
|---|---|
| `candidate_event_id` | Candidate identity; the sole join key; addressable unit. |
| `timestamp` | Candidate-time; evaluation instant; freshness bound. |
| `asset` | Symbol. |
| `screening_version` | Provenance of the screen (e.g. `screen_universe_v1`). |
| `screening_results` | Candidate-time JSON. Rendered field-by-field (`rank`, `composite_score`, `sector`, screening-time `regime`) or, when it carries the `{"note": ...}` fallback shape, rendered verbatim. |
| `data_available` | Candidate-time evaluation-status sub-fact. |
| `required_models_available` | Candidate-time evaluation-status sub-fact. |
| `evaluation_requested` | Candidate-time evaluation-status sub-fact. |
| `evaluation_completed` | Candidate-time; drives the primary evaluation-status label (§2.7). |
| `sequence_number` | **Read for derivation only — never displayed.** Deterministic append order; stable tiebreaker for candidate ordering. |

**`decision_events` — authorized columns (complete list):**

| Column | Purpose |
|---|---|
| `decision_id` | Canonical production decision identity (ADR-059). Addressable unit; displayed on detail. |
| `candidate_event_id` | The **only** permitted link to the candidate (FK). Used for grouping; not shown as a primary field. |
| `timestamp` | Decision-time; "Decided at". |
| `asset` | Symbol. |
| `action` | `BUY` / `SELL` / `HOLD` / `REJECT` (§2.7). |
| `event_type` | `EXECUTED` / `QUALIFIED_REJECTION` (§2.7). |
| `final_confidence` | Recorded ensemble confidence (0–1). Labelled "Recorded confidence" — never "AI confidence" or a quality score. |
| `model_outputs` | Decision-time JSON. Only the per-model `signal` and `confidence` for the `xgboost` / `lstm` / `finbert` keys are surfaced. **Model `metadata` (`shap_drivers`, `val_loss`, `is_degraded`, `raw_score`) is not surfaced.** |
| `risk_checks` | Decision-time JSON. Only the recorded `gate_trace` entry (`gate` + `passed` + `detail`) for a rejection, or `exit_reason` for a HOLD/SELL, is surfaced. **`fill_price`, `fill_shares`, `notional` and any other execution-time sibling keys are not surfaced.** |
| `intent` | Decision-time JSON. `primary_intent` always; `thesis` and `invalidation_point` for `EXECUTED`. `expected_return_basis_points` is not surfaced. |
| `market_context` | Decision-time JSON. `regime` and the recorded data timestamps (`decision_timestamp`, `price_data_timestamp`, `news_data_timestamp`). **`macro_score` is not surfaced.** |
| `data_completeness` | Decision-time JSON. `status`, `missing_inputs`, `stale_inputs`. |
| `sequence_number` | **Read for derivation only — never displayed.** Authorized specifically for: deterministic ordering of the multiple decisions under one candidate; multiple-decision handling; and latest-decision (`MAX(sequence_number)`) default expansion (§2.7). |

**Any Trust Ledger column not named in one of the two allowlists above is
not authorized for consumption under this ADR** — the reader must not
`SELECT` it, parse it, derive from it, or surface it, whether or not it is
also named in the illustrative note that follows. The two positive
allowlists are authoritative and exhaustive; the note below is for
clarity only and is not the source of the boundary.

**For clarity, columns and JSON sub-fields excluded by the allowlists
above include** (non-exhaustive): `record_hash`,
`previous_record_hash` on either table; `portfolio_snapshot` and
`deployment_manifest_id` on `decision_events`; the `risk_checks`
sub-fields `fill_price` / `fill_shares` / `notional`; the `model_outputs`
per-model `metadata`; the `market_context` sub-field `macro_score`; the
`intent` sub-field `expected_return_basis_points`;
`decision_outcome_events` in its entirety; every other Trust Ledger table.

The four JSON columns `risk_checks`, `intent`, `market_context`, and
`data_completeness` are authorized **only as verbatim recorded facts** for
display. They must **not** be translated, adapted, or mapped into any
`sentinel_engine` domain contract, evidence record, governance record, or
projection. (ADR-043 §9 declined to translate exactly these four; this ADR
does not extend ADR-043 — it authorizes a distinct, TI-owned, verbatim
read model that performs no such translation.)

### 2.5 The only permitted relationship

The sole cross-table relationship the reader may form is the DB-enforced
foreign key:

```
decision_events.candidate_event_id = candidate_evaluation_events.candidate_event_id
```

**Explicitly prohibited:** any join or correspondence by symbol; by date or
calendar day; by timestamp proximity; by `screening_results` score or
`rank`; by `model_outputs` values; by `final_confidence`; by
`deployment_manifest_id`; by `sequence_number` adjacency across tables; by
UI row position or index; and **any** correspondence whatsoever to
`trades.db` (`trades.id`, `order_id`, symbol, timestamp) or to
`screener_log` / `signal_log`. No heuristic historical backfill of
candidate → decision lineage is authorized.

### 2.6 Identity

- `candidate_event_id` remains the Trust Ledger candidate identity.
- `decision_id` remains the canonical production decision identity per
  ADR-059. It is displayed verbatim.
- This ADR introduces **no** new decision identity and **no** new
  identifier namespace.
- No attempt is made — and none is authorized — to map a Trust Ledger
  `decision_id` to a `trades.db` `trade-<id>` (Wave 2A's synthetic
  identity) or to any `order_id`. The two remain separate authoritative
  surfaces with no deterministic bridge.

### 2.7 Required semantic presentation

The surface renders recorded facts, framed as recorded facts. The
following mappings are mandatory:

- `evaluation_completed = 0` → **"Evaluation Not Completed"** (mirrors the
  column). The three booleans `evaluation_requested`, `data_available`,
  `required_models_available` are shown verbatim in the status detail. No
  cause is invented beyond those recorded booleans.
- A candidate with `evaluation_completed = 1` and **no** `decision_events`
  row → **"Evaluation completed — no decision event recorded"**.
- A candidate with `evaluation_completed = 0` and **no** `decision_events`
  row → **"Evaluation Not Completed — no decision recorded"**.
- None of the above three states may be described as "rejected",
  "declined", "no-trade", "no trade", "failed gate", "held", "ignored", or
  "skipped for cause". Absence of a `decision_events` row is absence of a
  record, never a recorded verdict.
- `action = HOLD` (which the live write path produces only from the exit
  path) → **"Position evaluated for exit — no exit condition met."** It
  must not be rendered as "AARA chose not to trade".
- Gate trace: for a `REJECT`, render only the **one recorded failing
  gate** — its `gate` name and `detail` string — verbatim. The reader must
  **not** synthesize a list of gates that passed (the ledger does not
  record them). For a `BUY` / `EXECUTED`, render "All entry gates passed."
- Missing, empty, or unparseable `risk_checks` → **"No gate detail
  recorded."**
- All decisions for one candidate remain visible; none is collapsed or
  hidden.
- Decisions within a candidate are ordered by `sequence_number` ascending.
- The most recent decision (`MAX(sequence_number)`) for a candidate may be
  default-expanded; the rest remain visible.
- `(action, event_type)` are always shown together, never one without the
  other. `EXECUTED` = "a portfolio-affecting action occurred and was
  recorded"; `QUALIFIED_REJECTION` = "the pipeline concluded without a
  portfolio-affecting action, for a recorded reason" — it is not a synonym
  for "the trade idea was bad".

### 2.8 Temporal boundary — decision-time only

The surface exposes **zero** outcome data. It must not read, derive, or
display: realized or gross or net P&L; return; win / loss / flat
direction; holding period; exit price; decision-quality classification;
calibration; or any linkage from a decision to a trade or its outcome. A
`SELL` / `EXECUTED` decision may show its recorded `exit_reason` string as
a **decision-time** fact ("an exit condition fired"), never as a P&L.

The UI carries an explicit terminal marker after the decision block, in
substance: *"End of decision-time evidence. Trade execution and outcome
are recorded separately in Performance & Learning → Outcome History and
are not linked to these decisions by any deterministic key."*

### 2.9 JSON handling

- An individual malformed / unparseable JSON value in one row's
  `screening_results`, `model_outputs`, `risk_checks`, `intent`,
  `market_context`, or `data_completeness` degrades **that field only** to
  **"not recorded"**. The row and the rest of the surface survive.
- A **missing required table** (`candidate_evaluation_events` or
  `decision_events`) or the **absence of any column named in a §2.4
  allowlist** makes the **whole surface unavailable** (an honest
  `IntegrationHealth` failure), never a partial render.

### 2.10 Security — free-text escaping

Every free-text string sourced from the ledger and surfaced by the UI is
HTML-escaped before rendering. This includes at least: a `gate_trace`
entry's `detail`; `intent.thesis`; `intent.invalidation_point`;
`risk_checks.exit_reason`; the `screening_results` `note` fallback string;
and any other ledger-provided free-text value. (Same discipline ADR-055
§8's safety posture and Decision Center's existing escaping already
apply.)

### 2.11 Health — ADR-061 tri-state

The surface follows ADR-061's `ReadResult` / `IntegrationHealth`
contract, with three rendered states:

1. **HEALTHY + data** — snapshot fetched, both tables present, at least one
   `candidate_evaluation_events` row → the inspection surface.
2. **HEALTHY + empty** — snapshot fetched, both tables present, zero
   candidate rows → an honest empty state.
3. **UNAVAILABLE** — any acquisition or structural failure (§2.12) → the
   shared `render_unavailable(...)` treatment, never a fabricated row.

### 2.12 Freshness

- The snapshot's local file mtime is surfaced verbatim as the fetch
  instant (the same `bootstrap._snapshot_fetched_at` mechanism ADR-055's
  `trades.db` snapshot already uses).
- `MAX(timestamp)` across the two authorized tables is surfaced verbatim
  as the data-through bound.
- There is **no Refresh button**. The surface is snapshot-bound and
  renders once per process from the fetched snapshot, consistent with
  Wave 2B's Outcome History. The snapshot's contents are never compared to
  "today" or presented as live.

### 2.13 UI placement

One additive **"Decision Ledger Inspection"** section inside the existing
**Performance & Learning** screen, rendered below Outcome History and
visually separated from it. It is **not** a seventh screen. It has **no**
Decision Center integration (the existing Decision Center's `decision_ids`
list and its trades-derived `trade-<id>` identity space are untouched) and
**no** cross-screen deep link. Placing this product-facing decision-chain
UI inside `applications/trading_intelligence/ui/` is consistent with
ADR-022 §2.

### 2.14 Import isolation

The Wave 3 fetch primitive, reader, contracts, query service, and UI
module(s) must not import from `bot/`, top-level `ledger/`, `scheduler/`,
`dashboard/`, `database/`, or `sentinel_engine/`. The fetch primitive is
duplicated, not imported, per this product's standing "duplicate the
primitive, never import the protected package" convention. A structural
test enforces this (§7, and the implementation's own test contract).

### 2.15 No persistent projection

No persisted, derived Trust Ledger projection artifact is created,
published, or scheduled. The in-process reader plus query service **is**
the reduction layer (raw rows → a typed, redacted read model). No change
is made to the Trust Ledger schema, and no change is made to the producer
(`bot/monitor/sync_db.py`).

---

## 3. Alternatives Considered

1. **Narrow read-only consumption of the already-published
   `trust_ledger.db` snapshot (selected).** Reuses a fetch primitive
   already proven and ADR-055-blessed against the same repo; zero new
   infrastructure; zero `bot/` change; the read surface is minimised at
   the adapter (two tables, an explicit column allowlist, sub-field
   redaction). Consistent with ADR-043's precedent that a scoped
   read-only ledger read does not touch ADR-004.
2. **A bot-produced or CI-produced derived read-only projection artifact.**
   Rejected: producing it requires a new writer in `bot/` or
   `.github/workflows/*.yml`, both ADR-002-frozen — a strictly larger
   governance ask for no honesty or safety gain over reducing the surface
   at the read adapter.
3. **A `screening_batch_id` threaded from the screener through
   `screener_log` into `trades`, joined product-side to Wave 2A.**
   Rejected: requires additive changes to `scripts/screen_universe.py`,
   `bot/_main_market.py`, `bot/_main_cycle.py`, and `bot/db/trade_log.py`
   (ADR-002 exception), cannot carry gate/rejection reasons, and depends
   on `screener_log`'s ~7-day retention. It is also explicitly the
   rejected `screener_log` → `signal_log` → `trades.db` funnel shape.
4. **Extend ADR-043's diagnostic script into the product path.** Rejected:
   ADR-043 §5 forbids UI wiring, automation, scheduling, and persistence;
   it routes through `sentinel_engine` contracts that have no field for
   the four JSON columns this surface renders verbatim. This ADR defines
   its own, non-`sentinel_engine`, verbatim read scope.
5. **Amend ADR-055 in place (an "Addendum A" section).** Rejected: this
   repository has no precedent for amending an ADR in place — every "dated
   addendum" reference points at a boundary/architecture document, never an
   ADR file — and the established mechanism for carving a scoped exception
   into a frozen ADR is a new sibling ADR (ADR-056, ADR-028 §2.2, ADR-039,
   ADR-017/018; `AARA_ARCHITECTURE_AUTHORITY.md` §"Resolving future
   conflicts": *"Write a new ADR ... that references both and states which
   wins and why."*).
6. **Do nothing — leave AARA's decision intelligence uninspectable in the
   product.** Rejected: the deterministic candidate → decision → recorded-
   reason chain is exactly the "make AARA's intelligence inspectable"
   product principle, and it is invisible today.

---

## 4. Consequences

**Positive:**
- Trading Intelligence can render, for the first time, the recorded
  candidate → decision → gate/exit-reason chain from the authoritative
  Trust Ledger, without a heuristic funnel and without a
  `decision_id ↔ trade-<id>` bridge.
- The bot stays the single writer/publisher of `trust_ledger.db`; no new
  producer, no new repo, no new secret, no `bot/` change, no schema
  change.
- The read surface is minimised by construction: two tables, an explicit
  column allowlist, mandated sub-field redaction, verbatim-only rendering,
  no outcome data.
- Fail-closed acquisition and per-row JSON tolerance mean a stale, absent,
  or partially malformed snapshot degrades honestly.

**Negative / Limitation:**
- Adds a second HuggingFace dataset file
  (`trust_ledger.db`) to the product runtime dependency set; mitigated by
  the fail-closed contract and the fact that it is the same repo ADR-055
  already depends on.
- The snapshot is eventually-consistent with the bot's activity; the
  surface shows "as-of" data and says so.
- Production `decision_events` volume is currently small (few `EXECUTED`
  rows; `decision_outcome_events` empty) — the surface is most valuable
  for the recorded rejection / HOLD / incomplete-evaluation population and
  is deliberately silent on outcomes.
- `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §5–7 will need a dated
  addendum recording `trust_ledger.db` as a Trading Intelligence runtime
  input — follow-up, not done here.

---

## 5. Non-Authorization / Scope Boundary

This ADR authorizes **only** §2. It explicitly does **not**:

1. Authorize any write, upload, commit, or delete against any HuggingFace
   repo, or against any SQLite file.
2. Make Trading Intelligence an owner, writer, or co-publisher of
   `trust_ledger.db`, `data/trust_ledger.db`, or the dataset repo.
3. Authorize reading any Trust Ledger table other than
   `candidate_evaluation_events` and `decision_events`, or any column
   outside the §2.4 allowlist, or any redacted sub-field named in §2.4.
4. Authorize reading `decision_outcome_events`, or exposing any outcome,
   P&L, holding-period, direction, exit-price, decision-quality, or
   calibration data.
5. Authorize any join, correspondence, or bridge between the Trust Ledger
   and `trades.db`, `screener_log`, or `signal_log`; any symbol / date /
   timestamp-proximity / score / model-output / row-position join; or any
   heuristic historical backfill.
6. Authorize any deploy-time acquisition of `trust_ledger.db`, any change
   to `.github/workflows/*.yml`, or the creation/setting of any GitHub or
   HuggingFace secret.
7. Introduce `-wal`/`-shm` handling, write-mode `PRAGMA`s, or any write
   connection to the snapshot.
8. Introduce a new decision identity, a new identifier namespace, or a
   persisted derived Trust Ledger projection artifact.
9. Select, prefer, constrain, reopen, or reinterpret ADR-004 Option
   A/B/C; establish ledger ownership or system-of-record authority; or
   establish dual-ledger synchronisation.
10. Modify `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level
    `ledger/`, `sentinel_engine/`, `config.py`, or the Trust Ledger schema.
11. Modify ADR-002, ADR-004, ADR-019, ADR-022, ADR-043, ADR-055, ADR-059,
    or ADR-061 — or amend, reopen, or reinterpret any of them beyond the
    single narrow exception to ADR-055 §5.6 stated in §2.
12. Authorize any Decision Center change, any cross-screen deep link, or a
    seventh Trading Intelligence screen.
13. Extend or reuse the ADR-043 implementation
    (`scripts/project_one_trust_ledger_decision.py`) or its
    `sentinel_engine` translation path.
14. Depend on or modify the bot-side asset-universe / `screener_log`
    screening funnel (ADR-019).

---

## 6. Relationship to Existing ADRs

**ADR-055:** A narrow exception is authorized — to §5.6 only, and only for
the exact scope in §2. Every other clause of ADR-055 (the remainder of
§5.6, its `trades.db` consumer contract, its non-authorizations, its
ADR-002 and ADR-004 safety statements) remains in force. ADR-055's file is
not edited. No Trust Ledger read beyond §2 is authorized.

**ADR-004:** Untouched and unaffected. This ADR reads a published,
already-produced artifact as a consumer; it makes no ledger-backend or
ownership choice, selects no Option A/B/C, and does not reinterpret the
"Q1" question — it authorizes a specific, minimal read that ADR-043 has
already shown is severable from the ownership decision. ADR-004 remains
exactly as `Deferred` as before this ADR. (See §8.)

**ADR-002:** No exception required. This ADR changes nothing under `bot/`,
`ledger/`, `scheduler/`, `dashboard/`, `database/`, `.github/workflows/`,
or `config.py`, makes no schema change, and never opens or writes
`data/trust_ledger.db` — it consumes a separately fetched, product-owned,
ephemeral copy. Deploy-time acquisition is explicitly outside this
authorization and would require separate governance review. (See §9.)

**ADR-043:** Cited as precedent that a narrow, read-only Trust Ledger
decision read can be authorized without reopening ADR-004. This ADR does
**not** import, extend, schedule, or productise ADR-043's mechanism. It
authorizes the four JSON columns (`risk_checks`, `intent`,
`market_context`, `data_completeness`) as **verbatim recorded facts
only**, explicitly not translated into any `sentinel_engine` contract —
which is why ADR-043 §9's decision not to translate those fields is not in
tension with this ADR.

**ADR-059:** Cited, unchanged. `decision_id` remains the canonical
production decision identity; this surface displays it verbatim and
introduces no competing identity.

**ADR-061:** Reused, unchanged. The surface's health behaviour follows
ADR-061's `ReadResult` / `IntegrationHealth` tri-state contract.

**ADR-019 (`Accepted — Implementation Deferred`):** Acknowledged as the
bot-side authority for the asset-universe / `screener_log` screening
funnel. This ADR does not modify it, does not depend on it, and does not
read `screener_log` — the candidate's screener provenance shown here comes
solely from `candidate_evaluation_events.screening_results` in the Trust
Ledger snapshot.

**ADR-022 (`Accepted`):** Consistent. ADR-022 §2 requires product-facing
governance / audit / evidence / decision-chain UI to live inside the
owning product's application package
(`applications/trading_intelligence/ui/`) and not inside
`sentinel_engine/`. This ADR's inspection section is exactly that.

**ADR-058:** This ADR is a proposal (D4) until it is tracked on the
authoritative default branch with `Status: Accepted`, landed under the
applicable write/merge controls (D2). Until then it authorizes nothing.

---

## 7. Evidence / Rationale

- `ledger/schema.sql` — `candidate_evaluation_events` and `decision_events`
  column definitions; the `decision_events.candidate_event_id` FK to
  `candidate_evaluation_events(candidate_event_id)`; the
  `trg_decision_events_requires_completed_evaluation` trigger; the
  append-only and chain-integrity triggers; the `decision_state` view
  definition (out of scope here).
- `bot/monitor/sync_db.py::push_ledger_db()` — the existing producer that
  uploads `trust_ledger.db` to `config.HF_DB_REPO_ID`,
  `repo_type="dataset"`, every cycle.
- `applications/trading_intelligence/adapters/trades_db_snapshot.py` — the
  proven, product-owned, `SPACE_ID`-gated, fail-closed, consumer-only
  fetch primitive (ADR-055 §2) this ADR authorizes duplicating for
  `trust_ledger.db`.
- `bot/_main_trust_decisions.py`, `bot/trust_ledger/decisions.py`,
  `bot/trust_ledger/candidates.py`, `bot/trust_ledger/ids.py` — confirm
  the `candidate_event_id` → `decision_events` propagation, the
  `EntryDecisionRecorder` gate-trace-on-failure-only behaviour, and that
  `HOLD` is produced from the exit path with `risk_checks.exit_reason`.
- `docs/decisions/ADR-055-...md` §5.6 / §5.11 — the read prohibition this
  ADR takes a narrow, scope-limited exception to, and the clause forbidding
  ADR-055's own implementation from working around it.
- `docs/decisions/ADR-043-...md` §5, §9 — the read-only-without-ADR-004
  precedent and the four-JSON-field translation boundary.
- `docs/decisions/ADR-059-...md` — `decision_id` as canonical production
  decision identity; `decision_outcome_events.decision_id` FK.
- `docs/decisions/ADR-061-...md` — the `ReadResult` / `IntegrationHealth`
  tri-state contract.
- `docs/decisions/ADR-022-...md` §2 — product-facing decision-chain UI
  ownership.
- `docs/DOCUMENT_INDEX.md` — ADR authority ("binding once status is
  **Accepted**; a 'Proposed' ADR is not yet authoritative") and the
  "frozen documents are amended, never silently edited — via a dated
  addendum or a narrowly-scoped ADR exception" convention.
- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` §"Resolving future
  conflicts" — "Write a new ADR ... that references both and states which
  wins and why."
- Independent verification of the production `data/trust_ledger.db`
  snapshot (read-only): 202 `candidate_evaluation_events` (71
  `evaluation_completed=1`), 135 `decision_events` (3 BUY/EXECUTED,
  2 SELL/EXECUTED, 26 HOLD/QUALIFIED_REJECTION, 104 REJECT/
  QUALIFIED_REJECTION), 0 `decision_outcome_events`, and no
  `trade_id`/`order_id` column anywhere in the ledger.

---

## 8. ADR-004 Safety Statement

This ADR does not select ADR-004 Option A, B, or C; does not prefer or
constrain any of them; does not reopen or reinterpret ADR-004; does not
establish Sentinel Engine as canonical ledger owner; does not establish
Trading Intelligence as canonical ledger owner; does not establish
dual-ledger synchronisation of any kind; and does not establish
system-of-record or decision-lifecycle authority. It authorizes a
read-only consumer of an already-published artifact and nothing more.
ADR-004 remains exactly as `Deferred` as before this ADR.

---

## 9. ADR-002 Safety Statement

This ADR requires no ADR-002 exception. It does not modify `bot/`,
`dashboard/`, `scheduler/`, `database/`, top-level `ledger/`,
`sentinel_engine/`, `config.py`, any `.github/workflows/*.yml` file, or
the Trust Ledger schema. It never opens, reads, or writes
`data/trust_ledger.db` or any path managed by the frozen packages — it
consumes a separately fetched, product-owned, ephemeral copy under
`applications/trading_intelligence/.runtime/`, opened `mode=ro`. The fetch
runs at Space runtime inside `applications/trading_intelligence/`, the
placement ADR-055 §2 states requires no ADR-002 exception. Deploy-time
acquisition of `trust_ledger.db` is explicitly outside this authorization
and would require its own separate governance review before it could be
proposed or implemented.

---

## 10. Fail-Closed Behaviour

The implementation must fail closed, with an honest
`IntegrationHealth`, for every one of:

- the `trust_ledger.db` artifact is missing / 404 in the dataset repo;
- the fetch fails (network, 5xx, malformed transfer);
- the fetch does not finish within the hard timeout;
- the HuggingFace runtime identity is unavailable (not running in a Space
  / `HF_DB_REPO_ID` unset / `config` or `huggingface_hub` not importable);
- the downloaded file is empty / torn / not a valid SQLite database;
- a required table (`candidate_evaluation_events` or `decision_events`) is
  absent from the snapshot;
- any column named in a §2.4 allowlist is absent from its table.

On any of these, the surface renders its UNAVAILABLE state. There is **no**
fallback to `data/trust_ledger.db`, to `trades.db`, to `screener_log`, to
`signal_log`, to any symbol/date correlation, or to any heuristic
reconstruction. A per-row malformed JSON value degrades that field to
"not recorded" without failing the surface (§2.9).

---

## 11. Rollback

Delete the Wave 3 fetch primitive, reader, contracts, query service, and
the Decision Ledger Inspection UI section, and revert the single
composition-root wiring line. The Trust Ledger, its producer, the
`trades.db` snapshot path, and every other Trading Intelligence surface
are unaffected — this ADR added a consumer-only leaf and nothing else.
ADR-055 §5.6 returns to full effect automatically (this ADR's exception is
scoped to the deleted code path).

---

## 12. Acceptance Criteria

This ADR may be considered Accepted only when the architecture owner has
confirmed, in writing:

- That the scope in §2 is authorized exactly as written, and that the
  narrow exception to ADR-055 §5.6 is limited to that scope.
- That no code, schema, test, workflow, configuration, or deployment
  change is authorized by acceptance itself — acceptance authorizes a
  subsequent, separate implementation that stays within §2.
- That ADR-004 remains `Deferred` and unaffected, and ADR-002 requires no
  exception.

---

## 13. Status

**Accepted — 2026-09-03.** Per ADR-058 D2/D4, this ADR's authority follows
from it being tracked on the authoritative default branch with
`Status: Accepted`, landed under the applicable write/merge controls; the
in-file metadata above is a locator, not the source of authority.
