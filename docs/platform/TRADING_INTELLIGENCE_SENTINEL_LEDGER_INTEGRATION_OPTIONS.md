# Trading Intelligence ↔ Sentinel Ledger Integration Options

**Status:** Design comparison — no option chosen. No code changes accompany this
document (`bot/`, `sentinel_engine/` both confirmed untouched via `git status`
before and after).

**Builds on:** `TRADING_INTELLIGENCE_BOUNDARY.md` (ownership boundary),
`TRADING_INTELLIGENCE_EVENT_MODEL.md` (event contract),
`TRADING_INTELLIGENCE_CONTRACT_GAP_ANALYSIS.md` (field-level findings).

## Grounding: What Each Ledger Actually Is Today

Read directly from code for this comparison (not re-derived from memory):

- **Top-level `ledger/`** (`ledger/ledger.py`, `ledger/integrity.py`) — a generic,
  table-agnostic, insert-only hash-chain service. `append_ledger_row(conn, table,
  payload)` computes a genesis-seeded sequential hash per table; `verify_chain`/
  `verify_all_chains` walk the chain and report breaks (never auto-repair — "the
  correct response is to halt and investigate," per the module's own docstring).
  8 tables are registered today: `candidate_evaluation_events`, `decision_events`,
  `decision_outcome_events`, `risk_evaluation_events`, `approval_events`,
  `deployment_manifest_events`, `constitution_enforcement_events`, `cost_models`.
  It also owns deployment-manifest lifecycle state
  (`CREATED→TESTING_STARTED→REVIEW_REQUESTED→APPROVED→PROMOTED→RETIRED`) and an
  `active_deployment_pointer`.
- **Notable, not previously documented:** `approval_events` is already a
  registered Group A table in the top-level `ledger/` package — but no file in
  `bot/trust_ledger/` writes to it. It exists in schema, unused in practice. This
  maps by name almost directly to `sentinel_engine.governance.approval.Approval`.
- **`bot/trust_ledger/`** — typed writer functions per table (`candidates.py`,
  `decisions.py`, `risk.py`, `outcomes.py`, `constitution.py`), all going through
  `ledger.ledger.append_ledger_row`. Database file: `data/trust_ledger.db`.
- **`sentinel_engine/ledger/`** — `LedgerStore(ABC)`: abstract `append`/`read_all`
  only. **No backend implementation exists.** `LedgerRepository` (concrete facade)
  and `ProjectionRepository(ABC)` exist and are tested (82 tests), but nothing has
  ever been instantiated against real data.

This means: today, "Sentinel becomes canonical" isn't a migration of an existing
Sentinel ledger — it would be building one for the first time, against a live
system that already has 8 tables' worth of hash-chained history and an active
Phase 1A validation clock running on it.

---

## Option A: Trading Intelligence Owns Operational Ledger, Sentinel Consumes Events

**Data ownership:** Top-level `ledger/` + `bot/trust_ledger/` remain the system of
record for all trading decisions, unchanged. `sentinel_engine`'s ledger (once a
backend exists) holds a *derived* copy, populated by reading Trading Intelligence's
ledger and translating rows through `decision_adapter` (and future adapters per
`TRADING_INTELLIGENCE_EVENT_MODEL.md`).

**Event flow:** One-way, matching the Migration Principles already established:
`data/trust_ledger.db` (unchanged) → a translation/consumption step (batch job or
separate process, not inline in `bot/main.py`) → `sentinel_engine` adapters →
`DecisionService`/ledger/projections. Trading Intelligence's own write path is
untouched.

**Migration risk:** Low to `bot/` — no `bot/` code changes required at all; this
is purely additive on the Sentinel side, as long as the consumption step runs
outside `bot/main.py`'s cycle (staying within ADR-002's protection). Risk shifts to
keeping the derived copy consistent with the source — a missed or delayed
translation produces a stale Sentinel-side view, not a corrupted one.

**Rollback strategy:** Trivial. Since Sentinel's copy is non-authoritative, it can
be dropped and rebuilt at any time by re-reading Trading Intelligence's ledger from
scratch (assuming the translation is deterministic). No impact on Trading
Intelligence's own data.

**Impact on existing Phase 1A validation:** Minimal to none — Phase 1A's live
validation depends entirely on `bot/trust_ledger`'s writes, which are untouched.
The consumption step is a new, separate reader, not a new writer on the critical
path.

**Impact on future AARA Wealth Intelligence:** Establishes a repeatable pattern —
Wealth Intelligence would build its own adapter into `sentinel_engine` the same
way, without needing to understand Trading Intelligence's `bot/trust_ledger`
schema. Sentinel becomes a common audit surface for multiple products even though
it doesn't own the source data for any of them.

---

## Option B: Sentinel Engine Becomes Canonical Decision/Event Ledger

**Data ownership:** `sentinel_engine/ledger` (once backed by a real store) becomes
the single source of truth platform-wide. Trading Intelligence would write
directly into it via `decision_adapter → DecisionService → LedgerRepository`
instead of (or ahead of deprecating) `bot/trust_ledger`'s own tables.

**Event flow:** `bot/main.py` / `scheduler/trading_job.py` would call into
`sentinel_engine` at decision-time — this requires modifying `bot/`, which is
outside this document's scope and would need its own future ADR under ADR-002's
"Lifting This Protection" checklist before any implementation could begin.

**Migration risk:** High. Requires `bot/` code changes (blocked by ADR-002 today),
requires either a dual-write transition period or a hard cutover, and risks
breaking continuity of the hash-chained audit trail the platform already has in
production (8 tables, active history) if the cutover isn't carefully sequenced.
Directly touches the live Phase 1A write path — the exact category of change
ADR-002 exists to gate.

**Rollback strategy:** Hard. Once `bot/` writes directly to `sentinel_engine`'s
ledger and old `bot/trust_ledger` writers are bypassed or removed, reverting means
restoring `bot/`'s original write calls — a real code revert, not a "stop
consuming" toggle. Data written during the new-path window would need reconciling
against whichever ledger is deemed authoritative after a rollback decision.

**Impact on existing Phase 1A validation:** High risk. Phase 1A's 30-day live
validation depends on uninterrupted, reliable `trust_ledger` writes — this system
has already had a real silent-data-loss incident in this exact ledger
(`decision_events`/`constitution_enforcement_events` were silently empty in
production until a manifest-bootstrap fix). Introducing a second, differently-shaped
write path during an active validation window is a direct threat to a currently-running
compliance measurement, not a hypothetical one.

**Impact on future AARA Wealth Intelligence:** Architecturally cleanest long-term —
one canonical ledger for the whole platform; Wealth Intelligence would write to the
same place Trading Intelligence does, with no dual-consumption logic needed. That
cleanliness is bought at high near-term risk to a live system currently under
active validation.

---

## Option C: Dual Ledger With Synchronization

**Data ownership:** Both ledgers are authoritative for their own scope during a
transition period. `bot/trust_ledger`/top-level `ledger/` remains authoritative
for Trading Intelligence's operational/compliance needs (Phase 1A); `sentinel_engine`'s
ledger is also written, kept in sync by a defined process — either synchronous
dual-write or asynchronous replication with drift detection.

**Event flow:** Depends entirely on sync mechanism chosen (not decided by this
document):
- *Synchronous dual-write* — `bot/main.py` writes to `trust_ledger` **and** calls
  the Sentinel adapter path in the same operation. Requires `bot/` changes, same
  ADR-002 boundary-crossing as Option B.
- *Asynchronous sync* — a separate job reads `trust_ledger` periodically and syncs
  into `sentinel_engine`, similar to Option A's consumption step, but explicitly
  framed as "kept in sync" with reconciliation/drift-checking rather than a
  one-directional derived copy.

**Migration risk:** Medium — more moving parts than Option A (two write/sync paths
to keep consistent), but risk profile depends heavily on which event-flow variant
is chosen: synchronous dual-write inherits Option B's `bot/`-change risk;
asynchronous sync inherits close to Option A's risk profile, plus the added
operational burden of detecting and resolving drift between two ledgers that are
both claimed as authoritative.

**Rollback strategy:** Depends on sync mechanism. Synchronous dual-write requires
a real `bot/` code revert (Option B-like). Asynchronous sync can simply be stopped
(Option A-like) — but any period where the two ledgers disagreed needs a
reconciliation decision before rollback is considered "clean."

**Impact on existing Phase 1A validation:** Depends on sync mechanism.
Synchronous/inline dual-write carries the same live-write-path risk as Option B
during an active validation window. Asynchronous sync is much lower-risk, but
introduces a new risk category of its own: if the two ledgers ever disagree, which
one is authoritative for a Phase 1A compliance question becomes ambiguous —
tension with the platform's own frozen "hash-chained ledger integrity" principle
(`ARCHITECTURE_FREEZE_STATUS.md`), which assumes a single immutable source of
truth, not two reconciled ones.

**Impact on future AARA Wealth Intelligence:** Workable, but the dual-ledger
pattern doesn't obviously simplify as more products join — each new product
joining under this model may need its own sync/reconciliation relationship with
Sentinel, multiplying operational complexity platform-wide rather than
centralizing it the way Option B would, or keeping it fully one-directional and
simple the way Option A would.

---

## Summary Table (Tradeoffs Only — No Recommendation)

| Dimension | A: TI-owned, Sentinel consumes | B: Sentinel canonical | C: Dual + sync |
|---|---|---|---|
| Data ownership | TI ledger authoritative; Sentinel derived | Sentinel authoritative; TI ledger deprecated over time | Both authoritative for their scope, kept in sync |
| Requires `bot/` changes | No | Yes | Depends on sync mechanism (yes if synchronous) |
| Migration risk | Low | High | Medium (mechanism-dependent) |
| Rollback | Trivial (rebuild derived copy) | Hard (code revert + reconciliation) | Depends on mechanism |
| Phase 1A validation impact | Minimal | High risk | Depends on mechanism |
| Long-term platform cleanliness | Good (repeatable adapter pattern) | Best (single source of truth) | Weakest (per-product sync burden grows) |

No option is chosen or recommended by this document, per scope.
