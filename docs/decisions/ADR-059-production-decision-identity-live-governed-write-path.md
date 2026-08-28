# ADR-059 — Production Decision Identity for the Live Governed Write Path

**Status:** Accepted
**Date Proposed:** 2026-08-28
**Date Accepted:** 2026-08-28
**Decision Type:** Architecture / Governance — Ratification Record (identity- and path-scoped)
**Related ADRs:** ADR-058 (the ratification model and the D1–D4 governance frame this record follows — Accepted, landed at `466a7ea`), ADR-004 (Sentinel-ledger ownership — `Deferred`; this ADR does not amend, select, prefer, or constrain any of its Option A/B/C), ADR-043 (temporary one-decision Trust-Ledger → `sentinel_engine` projection — Accepted; unaffected), ADR-044 (tracked-governance principle), ADR-002 (`bot/` + `ledger/` runtime protection — unchanged)

---

## Context

The Q1 production-lineage governance review established, from code and tests:

- There is exactly **one live, governed production decision write path**: Scanner (`bot/_main_candidates.py`) → Ledger (`bot/trust_ledger/decisions.py::write_decision_event` → `ledger/ledger.py::append_ledger_row`) → Paper Execution (`bot/trust_ledger/outcomes.py`). This is verified, not assumed, by `scripts/verify_single_write_path.py`, whose header cites `phase1a_requirements.md` Section 14 ("Single write path (verified, not assumed)").
- That path persists every production decision it creates as **one row in `data/trust_ledger.db::decision_events`** — an append-only, hash-chained table (UPDATE/DELETE blocked by triggers).
- Each such row carries `decision_id` (`TEXT NOT NULL UNIQUE`), assigned by `bot/trust_ledger/ids.py::new_decision_id` when the row is written, and referenced thereafter — e.g. `decision_outcome_events.decision_id` is a foreign key to it.
- The legacy `decision_log` write path is retired: `scripts/verify_single_write_path.py` check 2 confirms its writers (`create_decision()`/`log_decision()`) have zero production callers, and it has received zero rows since the cutover.
- `sentinel_engine.Decision.decision_id` is a contract-level `str` with **no production producer**: `bot/` never calls `sentinel_engine`'s decision-creation service (`bot/_main_trust_decisions.py` imports only the evidence and governance adapters), and the only non-test caller of `sentinel_engine`'s `create_decision()` is `scripts/project_one_trust_ledger_decision.py` (the ADR-043 one-off, one named `decision_id`, manual, non-durable).

**No ADR currently records, as a fact, which identifier the live governed write path uses for a production decision.** The Q1 review named the absence of that record as the smallest precise governance gap that can be closed **without touching ADR-004's deferred choice**, without asserting a system-wide system of record, and without establishing decision lifecycle authority.

ADR-058 (Accepted, landed at `466a7ea`) established: **D1** Architecture Owner authority derives from control of the authoritative repository / default branch; **D2** an ADR is authoritative when it is tracked on the authoritative default branch, its `Status:` is `Accepted`, and it was landed under the applicable write / merge controls (in-file `Accepted By` is metadata, not proof); **D3** continuity for existing tracked + `Accepted` ADRs; **D4** proposing an ADR is separate from ratifying it. This ADR follows that model: it records an already-true fact about the current architecture and does **not** create the identity it records.

---

## Decision

The following are recorded as facts about the current architecture:

### D1 — The live governed production decision write path and where it persists

There is one live, governed production decision write path — Scanner → Ledger → Paper Execution, as verified by `scripts/verify_single_write_path.py`. That path persists every production decision it creates as exactly one row in `data/trust_ledger.db::decision_events`.

### D2 — Production decision identity for that path

For the write path in D1, **`decision_events.decision_id` is the authoritative production decision identity**: the identifier assigned when the decision row is written, and the identifier by which that decision is thereafter referenced (including by `decision_outcome_events.decision_id`).

`decision_id` is **currently** generated as `DEC-<UTC timestamp, format `%Y%m%dT%H%M%S`>-<asset symbol, or `NA`>-<8 hexadecimal characters>` (`bot/trust_ledger/ids.py`), and is `UNIQUE` within `data/trust_ledger.db::decision_events` (`ledger/schema.sql`). **This format description is a statement of current implementation only. It is not frozen as an architectural contract.** A future change to the format, its generation mechanism, or its uniqueness scope is a normal implementation change and is not governed by this ADR.

### D3 — What this identity authority does NOT establish

Recording `decision_events.decision_id` as the production decision identity for the D1 path does **not**:

- make the Trust Ledger, `data/trust_ledger.db`, or any store the system-wide decision **system of record** — that is ADR-004's question and remains deferred;
- select, prefer, rank, constrain, or express any view on ADR-004's Option A, Option B, or Option C;
- establish **lifecycle authority**, a decision lifecycle state machine, or ownership of decision state transitions;
- ratify the `decision_state` view, the `event_type` classification, or any other construct as lifecycle authority;
- retire, delete, migrate, deprecate, re-enable, or otherwise modify the legacy `decision_log` path;
- link a decision to any execution, broker order, `order_id`, or `trades` row, or complete any `DECISION_EXECUTED` payload;
- close, complete, or make any finding about Phase-1A validation.

### D4 — `sentinel_engine` decision identity

`sentinel_engine.Decision.decision_id` is **not** the live governed production write path's decision identity: it is a contract-level string with no production producer. This ADR states nothing further about `sentinel_engine.DecisionState` or `DecisionProjection`; their authority or non-authority beyond this single point is out of scope.

---

## Scope of This Record

- This ADR records D1–D4 as facts about the current architecture. It does not add to, narrow, reinterpret, or infer beyond them.
- "The live governed production write path" means the single path `scripts/verify_single_write_path.py` verifies. The identity claim in D2 is scoped to **that path**, whatever set of files implements it at a given time — not to a fixed file list.
- Nothing in this ADR is contingent on Phase-1A being closed, or on any ADR-004 criterion being met.

---

## Explicit Non-Goals / Non-Claims

This ADR does **not**:

1. Select, prefer, rank, constrain, or comment on ADR-004 Option A, Option B, or Option C. ADR-004 remains `Status: Deferred`, unamended.
2. Declare the Trust Ledger, `data/trust_ledger.db`, or any store the system-wide decision **system of record**.
3. Establish, assign, or imply decision **lifecycle authority**, a lifecycle state machine, or ownership of decision state transitions.
4. Ratify `decision_state`, `event_type`, `bot/decision_engine/decision_state.py`, or any other construct as lifecycle authority.
5. Freeze the `decision_id` format, its generation mechanism, or its uniqueness scope as an architectural contract.
6. Retire, delete, migrate, deprecate, re-enable, or modify the legacy `decision_log` path, `database/services/decision_service.py`, or any part of it.
7. Declare `sentinel_engine.DecisionState` or `DecisionProjection` authoritative or non-authoritative, beyond stating (D4) that `sentinel_engine.Decision.decision_id` is not the live production identity source.
8. Establish or require any decision-to-execution, decision-to-order, decision-to-`order_id`, or decision-to-`trades` linkage, or complete any `DECISION_EXECUTED` payload.
9. Close, complete, review, or make any finding about Phase-1A validation, ADR-004's Future Decision Criteria, or the missing `phase1a_requirements.md`.
10. Resolve or address Q2 (audit / event-history semantics) or Q3 (Constitution / Risk Governor).
11. Authorize or require any code, schema, migration, deletion, workflow, deployment, configuration, or documentation change, including any edit to ADR-004, ADR-043, or any other ADR.
12. Claim that this document created the identity it records. `decision_events.decision_id` is what the live write path already uses; this ADR only records that fact.
13. Make any additional governance decision beyond D1–D4.

---

## Relationship to ADR-004

ADR-004 (`Status: Deferred`) defers the choice of which ledger architecture owns the operational ledger (Option A/B/C) and names `ledger/` + `bot/trust_ledger/` as "currently the live system of record" as a statement of fact it explicitly declines to confirm or replace. This ADR is consistent with that and strictly narrower: it records the *identifier* the one verified live write path uses for a production decision, and D3 states plainly that this establishes neither the system-wide system of record nor any preference among ADR-004's options. It does not amend, supersede, reopen, reinterpret, or shorten ADR-004 or any of its six Future Decision Criteria.

## Relationship to ADR-043

ADR-043 (Accepted) authorizes a temporary, one-named-`decision_id`, manual, non-durable projection of a real `decision_events` row into `sentinel_engine` contracts. That mechanism *reads* `decision_events.decision_id`; this ADR records that identifier's status for the live write path but does not extend ADR-043's authorization, make its mechanism permanent, reuse it, or change its expiry.

## Relationship to ADR-058

This ADR follows ADR-058's ratification model. Per ADR-058 D4, this document is a **proposal** until it is landed under ADR-058 D2 (tracked on the authoritative default branch, `Status: Accepted`, landed under the applicable write / merge controls). Per ADR-058 D2, the `Accepted By` line, once filled, is metadata, not the source of authority. This ADR does not create the fact it records; the fact predates this file.

---

## Evidence

- `scripts/verify_single_write_path.py` — proves (1) the legacy `decision_log` write path is unreachable from the live trading cycle and has received zero rows since the cutover; (2) exactly one decision-creation path end to end: Scanner (`bot/_main_candidates.py`) → Ledger (`bot/trust_ledger/decisions.py`) → Paper Execution (`bot/trust_ledger/outcomes.py`). Header cites `phase1a_requirements.md` Section 14 ("Single write path (verified, not assumed)").
- `bot/trust_ledger/decisions.py::write_decision_event` — the Ledger-stage writer; calls `ledger.ledger.append_ledger_row(conn, "decision_events", {…})` with `"decision_id": new_decision_id(asset)`.
- `bot/trust_ledger/ids.py::new_decision_id` / `_new_id` — the current `DEC-<ts>-<asset>-<8 hex>` generation.
- `ledger/schema.sql` — `decision_events (… decision_id TEXT NOT NULL UNIQUE …, record_hash, previous_record_hash)`; `decision_outcome_events.decision_id REFERENCES decision_events(decision_id)`; append-only enforced by `trg_*_no_update` / `trg_*_no_delete` / chain-integrity triggers.
- `bot/_main_trust_decisions.py` — imports only `evidence_adapter` / `governance_adapter` / `get_evidence_service` / `get_governance_service` from `sentinel_engine`; calls no `sentinel_engine` decision-creation service.
- `sentinel_engine/domain/decision.py`, `sentinel_engine/adapters/decision_adapter.py` — `Decision.decision_id: str`, validated only as a non-empty string; no production producer.
- `scripts/project_one_trust_ledger_decision.py` — the only non-test caller of `sentinel_engine`'s `create_decision()` (ADR-043; one named `decision_id`, manual, non-durable).
- The Q1 production-lineage governance review in this repository's working history — records the finding that no ADR yet states the live write path's decision identifier, and frames this identity-only, path-scoped ratification as the smallest gap closable without touching ADR-004.

---

## Decision Character

This is a **ratification record** of a fact about the current architecture, scoped to decision *identity* on one *path*. It authorizes no implementation of any kind. Per ADR-058 D4 it is a proposal until landed under ADR-058 D2. It does not create the identity it records, and does not derive authority from itself.

---

## Consequences

**Positive:**

- Gives the repository a tracked record of which identifier a production decision has, on the one path that verifiably creates production decisions — a fact previously carried only by code and tests.
- Lets subsequent governance work (decision-to-execution linkage, Phase-1A closure evidence, and eventually ADR-004's Option choice) refer to a named, ratified production decision identity instead of re-deriving it.
- Stays strictly inside the identity / path boundary the Q1 reviews required: no ADR-004 overlap, no lifecycle authority, no system-of-record claim.

**Negative / Limitation:**

- Does not resolve which store is the system-wide decision system of record — that remains ADR-004's deferred question.
- Does not establish decision lifecycle authority; the multiple coexisting lifecycle models remain ungoverned.
- Does not link a decision to the order or trade it produced; that linkage remains undefined.
- Does not advance Phase-1A closure; the missing criteria document and unproduced evidence remain open.
- Names only the *current* `decision_id` format, and only as implementation detail; a future format change is ungoverned by this ADR by design.

---

## Acceptance

*(Completed only when this ADR is landed under ADR-058 D2. Left as a stub while `Proposed`. Per ADR-058 D2, authority follows from this document being tracked on the authoritative default branch with `Status: Accepted`, landed under the applicable write / merge controls; the `Accepted By` line, once filled, is metadata only, not the source of authority. Per §Decision Character, completing this section does not create the fact recorded in D1–D4, which predates this file.)*

**Status:** Accepted
**Date Accepted:** 2026-08-28
**Accepted By:** Architecture Owner
