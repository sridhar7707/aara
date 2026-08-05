# AARA Trading Intelligence — Governance Intelligence Design

**Status:** Design proposal. Documentation only. No code was created or
modified. `applications/trading_intelligence/`, `sentinel_engine/`, `ledger/`,
`bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`
untouched, confirmed via `git status` before and after.

**Authority:** `AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md`,
`AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md`,
`TRADING_INTELLIGENCE_EVENT_MODEL.md`, `TRADING_INTELLIGENCE_BOUNDARY.md`,
`ADR-001-sentinel-engine-structure.md`,
`ADR-004-sentinel-ledger-ownership-strategy.md`. This document does not
redecide anything those establish. Per this task's explicit scope, it also
does **not** resolve: ledger ownership (ADR-004 stays deferred, untouched),
approval workflow ownership, execution authorization, or migration decisions.
Where those questions surface below, they are named, not answered.

---

## 1. Current Governance State

Verified by reading each piece of real code directly — not assumed to align
just because the names sound related.

### Approval events

Two things named "approval" exist, and **they do not describe the same
concept**:

- **`sentinel_engine.governance.approval.Approval`**
  (`sentinel_engine/governance/approval.py`) — frozen dataclass:
  `approval_id`, `decision_id`, `status`, `approved_by`, `timestamp`. Keyed
  by `decision_id` — a trading-decision-scoped approval, one per decision.
  `GovernanceService.record_approval()` stores it in
  `self._approvals[approval.decision_id] = approval` — a **dict overwrite**,
  so only the single latest `Approval` per `decision_id` is ever retained
  in-memory; no history.
- **`approval_events`** (`ledger/schema.sql`, real, hash-chained,
  currently-schema'd table) — verified directly: `subject_type` is
  `WEIGHT_CHANGE / MANIFEST_PROMOTION / EXPERIMENT_PROMOTION /
  RISK_RULE_CHANGE / CAPITAL_INCREASE`, keyed by `subject_id`. **There is no
  `decision_id` column on this table at all.** It governs model/system
  lifecycle actions (weight changes, manifest promotions, capital changes) —
  not trading decisions. `deployment_manifest_events.approval_event_id`
  references it for manifest promotion approval specifically.
  **Confirmed zero writers anywhere in `bot/` or `database/`** — nothing
  constructs an `approval_events` row today, for any subject type.

**The real, concrete finding this document adds:** `sentinel_engine`'s
`Approval.decision_id`-keyed shape has **no corresponding real table at
all** — `approval_events` isn't just unwritten, it's schema-scoped to a
different governance domain entirely. Whatever eventually backs a
decision-scoped `Approval` reader would need a different data source than
`approval_events`. Section 1's "Decision audit trail" below identifies what
that real source actually is.

### Decision audit trail

- **`constitution_enforcement_events`** (`ledger/schema.sql`) — real,
  hash-chained, append-only, **and actually written today** by
  `bot/trust_ledger/constitution.py`'s `check_and_log()`. `decision_id`
  foreign-keys to `decision_events.decision_id`. Six rows are written per
  decision (one per Trading Constitution rule): `rule_id`, `rule_name`,
  `check_result` (`PASS`/`FAIL`/`ESCALATED`), `action_taken`
  (`execution_proceeded`/`advisory_only`), `reason` (free text).
- This is the **actual, currently-running decision-level governance data**
  in this codebase — verified with a writer, unlike `approval_events`.
- Two of the six rules explicitly encode the human-approval gap this
  document must not resolve (Section 5): `_rule_risk_governor_authority()`
  and `_rule_approval_escalation()` both produce `ESCALATED` /
  `advisory_only` results whose `reason` text states outright that human
  approval **would** normally be required, but Phase 1A has no per-trade
  approval workflow (`phase0_decisions.md` #17) — logged for later review,
  never blocking. This is not an inference; it's the literal `reason` string
  the running code writes today.

### Chain of custody

- **`sentinel/frontend/components/chain_timeline.py`** — stub only
  (`raise NotImplementedError`), docstring: "Renders the Decision Chain of
  Custody lineage (8-9 step timeline) from a projection view." Its data
  source (`chain_view: dict`) is undefined — no `chain_view`-shaped contract
  exists anywhere.
- **`SENTINEL_COMPONENT_CATALOG.md` Component 5 ("ChainOfCustodyTimeline")**
  describes a **5-step** linear journey sourced from `decision.timeline` —
  disagreeing with the component file's own "8-9 step" docstring. Neither
  number is backed by a real field: no `Decision`/`DecisionProjection`/
  `DecisionContract` has a `.timeline` attribute anywhere in this codebase.
  This is a documentation/implementation mismatch worth naming precisely
  rather than picking one number as authoritative.
- **`decision_state`** (`ledger/schema.sql`, a `VIEW`, not a table) is the
  only real, queryable "lifecycle" signal that exists today — a two-value
  derivation (`OPEN`/`CLOSED`) from whether a `decision_outcome_events` row
  exists yet for a given `decision_id`. Far narrower than an 8-9 step
  timeline.
- **`sentinel.backend.domain.enums.DecisionState`** (`sentinel/backend/`, the
  same unrelated, unwired scaffold flagged in
  `AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` Section 1) defines
  an 8-value lifecycle enum: `IDENTIFIED`, `EVALUATED`, `GOVERNED`,
  `APPROVED`, `DISPATCHED`, `EXECUTED`, `REVIEWED`, `CLOSED`. This is
  structurally the richest lifecycle model that exists anywhere in this
  codebase — closer in spirit to a "chain of custody" than the two-value
  `decision_state` view — but, same as every other `sentinel/backend/`
  finding in the Risk Intelligence document, it is disconnected: no code
  constructs one, no relationship to `sentinel_engine`, `decision_events`, or
  `applications/trading_intelligence` exists.

### Evidence traceability

Already fully covered in `AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md`
Sections 1-2, not re-derived here. Restated only as it bears on governance:
`Evidence` carries no `decision_id` field — the association is external
(`EvidenceService`'s own dict) — so an evidence-traceability trail would
have to be assembled the same indirect way a governance trail would, not a
built-in property of either contract.

### Existing governance components

All verified as structure-only stubs (`raise NotImplementedError`) in
`sentinel/frontend/components/` — none render anything today:

| Component | Purpose (per its own docstring) | Data source shape |
|---|---|---|
| `governance_badge.py` | Governance status (PASS/ESCALATED/BREACH) | `governance_view: dict`, undefined contract |
| `decision_card.py` | Decision projection view | `decision_view: dict` |
| `approval_controls.py` | Approve/Defer/Decline/Escalate buttons | takes `decision_id` + an API client, explicitly defers permission checks elsewhere |
| `chain_timeline.py` | Chain-of-custody lineage | `chain_view: dict`, undefined contract |
| `audit_fingerprint.py` | SHA-256 governance fingerprint (decision_id, policy_version, checks, approval, timestamp) | `fingerprint_view: dict`, undefined contract |
| `model_agreement.py` | Model consensus (3/3, 2/3, ...) | `evidence_assessment_view: dict`, undefined contract |

`SENTINEL_COMPONENT_CATALOG.md`'s `GovernanceBadge` entry names its data
source as `decision.governance.status` — a dotted path implying a `.governance`
attribute on `Decision`. **No such attribute exists** on `Decision`,
`DecisionProjection`, or `DecisionContract` at any layer, verified directly.
Same category of catalog-vs-contract mismatch already documented for
Evidence and Risk in the two prior design documents.

### Existing contracts

- **`sentinel_engine.governance.policy.Policy`** — `policy_id`, `name`,
  `description`, `enabled`. Registered/read via `GovernanceService`
  (`register_policy`/`get_policy`/`is_policy_enabled`). In-memory only, no
  persistence, no caller registers one anywhere in this codebase.
- **`sentinel_engine.governance.approval.Approval`** — covered above.
- **`DecisionProjection.status: str`** — an unconstrained string (the
  codebase's own tests use `"DECISION_CREATED"` as an example value,
  verified in `sentinel_engine/tests/test_decision_projection.py`), not an
  enum, and not the same concept as either `decision_state`'s OPEN/CLOSED
  view or `sentinel/backend`'s 8-value `DecisionState` enum. Three different
  "decision status" representations exist; none maps onto another.

## 2. Governance Display Model

```
Decision
    |
    +-- Evidence      (AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md)
    |
    +-- Risk          (AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md)
    |
    +-- Governance     (this document)
```

Three siblings under one decision's detail view, matching
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md` Section 4's existing
"Evidence section" / "Risk section" / "Governance section" split — each
independently blocked, each requiring its own reader/contract, not one
combined "supporting data" bundle. Defined conceptually only; nothing below
is a contract this document creates.

- **Decision lifecycle** — the real state of this concept today is
  fragmented across three incompatible representations (Section 1):
  `decision_state`'s binary OPEN/CLOSED, `DecisionProjection.status`'s free
  string, and `sentinel/backend`'s disconnected 8-value enum. A Governance
  Intelligence capability showing "lifecycle" would need to pick one — this
  document does not, consistent with Section 5's "do not resolve" scope
  (which state model wins is itself an ownership question, Section 3).
- **Human approval** — the most concretely governed concept found in this
  analysis, and the most explicitly *not* enforced: `constitution_enforcement_events`
  Rules 1 and 5 already state, in their own logged `reason` text, exactly
  when a decision *would* have required human approval under the Trading
  Constitution, while confirming Phase 1A enforces none of it. A Governance
  Intelligence display of "human approval" today can only mean *surfacing
  that advisory signal* — never implying an approval was sought, granted, or
  blocking, since none of the three ever happens in Phase 1A.
- **Audit history** — `constitution_enforcement_events`' six-rows-per-decision
  record is the only real, populated audit history in this codebase.
  `sentinel_engine.governance.GovernanceService`'s `Approval` storage is not
  an audit history at all — it retains only the latest record per decision
  (Section 1), the opposite of an append-only trail.
- **Immutable records** — every governance-adjacent table found
  (`approval_events`, `constitution_enforcement_events`, `decision_events`) is
  Group A: append-only, hash-chained, with `BEFORE UPDATE`/`BEFORE DELETE`
  triggers that `RAISE(ABORT, ...)`, plus a `previous_record_hash`
  chain-integrity trigger. This immutability guarantee is real and already
  enforced at the database level, independent of anything Trading
  Intelligence or `sentinel_engine` does with the data.
- **Explanation trail** — `constitution_enforcement_events.reason` is
  already a genuine, human-readable, per-rule explanation string (e.g.,
  `"missing required fields: intent.thesis, intent.invalidation_point"`),
  written today for every decision. This is the strongest existing asset for
  a future Governance Intelligence capability — an explanation trail already
  exists; it just has no reader anywhere outside `bot/trust_ledger/` itself.

## 3. Current Gaps

- **Missing writers** — `approval_events` has zero writers for any
  `subject_type`, confirmed directly. Whether it ever gets a writer at all
  is a separate, undecided question from whether it's even the right table
  for decision-level approval (Section 1 found it isn't).
- **Missing readers** — nothing in `sentinel_engine` or
  `applications/trading_intelligence` reads `constitution_enforcement_events`,
  `decision_state`, or `approval_events`. Same structural gap
  `AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md` Section 4 found for
  risk data: no `ProjectionRepository`-equivalent abstraction exists for any
  of these three sources.
- **Missing contracts** — no `sentinel_engine` contract models
  `constitution_enforcement_events`' actual shape (one decision → six rule
  rows). `Approval` doesn't fit it: `Approval` is one-record-per-decision
  with a single `status`; the real data is six-records-per-decision, each
  with its own `check_result`. This is the same category of cardinality
  mismatch `AARA_TRADING_INTELLIGENCE_EVIDENCE_DESIGN.md` Section 4 already
  named for `evidence_reference` (singular) vs. `get_evidence_for_decision()`
  (list) — now also true for governance.
- **Ownership questions** — three non-unified "governance" surfaces exist,
  none authoritative, same pattern as Risk Intelligence's four non-unified
  risk models: (a) `sentinel_engine.governance` (`Policy`/`Approval`,
  in-memory, no real backing data); (b) `bot/trust_ledger/`'s real
  `constitution_enforcement_events`/`approval_events`/`decision_state`,
  live but with no Sentinel-side reader; (c) `sentinel/backend/domain`'s
  `DecisionState`/`GovernanceAction`/`SentinelRole` enums plus governance
  dataclasses, structurally richer but entirely disconnected and unwired.
  Which becomes authoritative — or whether a fourth, new shape is designed —
  is not decided here.

## 4. Implementation Classification

**Can implement now (documentation/design only, no protected-path change):**
- Further prose-level design: naming a candidate contract shape for
  `constitution_enforcement_events`' real six-rows-per-decision structure,
  or specifying exactly what fields a future `GovernanceArea` would need in
  `applications/trading_intelligence/ui/decision_center/screen.py`, following
  the same pattern `DecisionListArea`/`DecisionDetailArea` already
  establish. Not done beyond Section 2's conceptual level here, since
  choosing among Section 3's ownership candidates first is itself out of
  this document's scope.

**Requires ADR approval:**
- Adding any governance-shaped contract to `sentinel_engine/` (e.g., a
  `ConstitutionCheck`/`RuleEnforcement` dataclass) — `sentinel_engine/` is
  protected; per `ADR-001`, any change to its package shape needs its own
  dedicated ADR.
- Building a reader/adapter from `constitution_enforcement_events` or
  `decision_state` into any Sentinel contract — crosses the one-way boundary
  `TRADING_INTELLIGENCE_BOUNDARY.md` Section 7 describes, and touches
  `ledger/`/`bot/trust_ledger/`, both protected paths; `ADR-004` criterion 6
  already states whichever ledger-integration option is eventually chosen
  "gets its own ADR... before any implementation work begins" — governance
  data inherits that same requirement, since it lives in the same ledger.
- Deciding which of Section 3's three governance surfaces becomes
  authoritative — an architectural call with effects on both
  `sentinel_engine` and `bot/trust_ledger/`, not a documentation-only one.

**Blocked by Phase 1A validation:**
- `constitution_enforcement_events`' `ESCALATED` rows are, by explicit
  design, advisory-only for the entire Phase 1A window
  (`phase0_decisions.md` #17: "no per-trade human approval in Phase 1A").
  Any Governance Intelligence UI implying an approval action is available,
  pending, or enforced would misrepresent what the running system actually
  does today. This blocks not just adapter-building but even finalizing the
  *display* design for "human approval" (Section 2) until Phase 1A's
  validation window closes and whether/how a real approval workflow gets
  built is decided — explicitly out of this document's scope (Section 5).
- `ADR-004`'s own deferral criteria (criterion 1: Phase 1A's 30-day window
  must complete and be reviewed; criterion 3: a tested dry run against real
  `trust_ledger` data, which has never happened for any table) apply equally
  to governance data, since `constitution_enforcement_events`/
  `approval_events` live in the exact same ledger `ADR-004` is about.

## 5. Explicitly Not Resolved

Per this task's scope, the following are named only where they surfaced
above, and are not decided by this document:

- **Ledger ownership** — `ADR-004`'s Option A/B/C choice remains fully
  deferred, untouched.
- **Approval workflow ownership** — whether Trading Intelligence, Sentinel
  Engine, or neither eventually owns a real per-trade approval mechanism is
  not decided; Section 2 only describes what already exists (advisory-only
  logging), not what should exist.
- **Execution authorization** — whether any future governance signal ever
  becomes execution-blocking (as opposed to today's `advisory_only`) is not
  addressed.
- **Migration decisions** — whether/when any `bot/trust_ledger/` governance
  writer, or the disconnected `sentinel/backend/` scaffold, moves into or
  aligns with `sentinel_engine/` is not decided.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No adapter was created. This document only reads and cites
existing code and prior documentation.
