# ADR-016 — ConstitutionRuleCheck Contract Shape (Classification Only, Implementation Deferred)

**Status:** Proposed — Implementation Deferred
**Date:** 2026-08-13
**Decision Type:** Architecture / Governance — Contract Classification Only
**Related ADRs:** ADR-004, ADR-013, ADR-015

---

## 1. Context

`docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md` (§1.3, §3 "Trust" stage, §4 "Governance") identifies that Decision Center's stated long-term intent — surfacing the Trading Constitution's per-decision audit trail — is not yet realized, and that no `sentinel_engine` contract exists to represent it.

A read-only inspection of `bot/trust_ledger/constitution.py` (`bot/` remains untouched; this ADR only cites what was read) confirms the real, live-written shape of `constitution_enforcement_events`: `check_and_log()` writes exactly **six rows per decision**, one per Trading Constitution rule, each carrying:

```text
event_id, decision_id, rule_id, rule_name,
check_timestamp, check_result, action_taken, reason
```

This shape does not fit `sentinel_engine.governance.Approval` (a single record: `status`/`approved_by`/`timestamp`) — the capability model doc's own finding, now confirmed directly against the writer code. `Approval` models a governance verdict; a constitution rule check is a different, six-per-decision concept. Repurposing `Approval` would misrepresent what it models. The correct move is a new, additive contract, not a modification of an existing one.

**Governing constraint — ADR-004 §1 (Future Decision Criteria):** *"Phase 1A's 30-day live-validation window has completed, and its results... have been reviewed."* Phase 1A began 2026-07-28; the 30-day window closes 2026-08-27 and has not yet closed as of this ADR's date. Per the capability model doc's own finding, surfacing Phase-1A-observation-mode data as settled, authoritative content before that window closes and is reviewed would misrepresent unvalidated data as final. This ADR is therefore scoped, deliberately, to name a contract *shape* only — exactly the precedent ADR-004 itself set (existing today, mid-Phase-1A, without authorizing any backend) and ADR-013/ADR-015 both followed (explicit, bounded, non-implementing classification decisions).

---

## 2. Decision

Define, for future use, a new proposed dataclass shape in `sentinel_engine`'s governance contract layer:

```text
ConstitutionRuleCheck
    decision_id: str
    rule_id: str
    rule_name: str
    check_result: str
    action_taken: str
    reason: str
    checked_at: datetime
```

This is a **name and field list only**. This ADR does not create the file, does not write the dataclass, and does not select its exact module path (a plausible future location would be alongside `sentinel_engine/governance/policy.py`/`approval.py`, e.g. `sentinel_engine/governance/constitution_rule_check.py` — noted here as a design consideration, not authorized by this ADR).

`event_id` is deliberately excluded from the proposed shape, mirroring the existing precedent already established by `EvidenceEntry`/`ApprovalEntry` (`applications/trading_intelligence/projections/`), both of which already drop their own source event/record ids as internal identifiers with no consuming-layer use.

---

## 3. Explicit Non-Authorization

This ADR authorizes **naming a shape only**. It does not authorize, and implementation must not include, any of the following:

- Any read access to `bot/trust_ledger/`, top-level `ledger/`, or `database/`.
- Any adapter, reader, or query-service implementation (no `SentinelConstitutionSource`-style class, no `DecisionQuery` extension, nothing analogous to `SentinelEvidenceSource`/`SentinelGovernanceSource`).
- Any Trading Intelligence (or any other application) projection, service, controller, or UI change.
- Any modification to `sentinel_engine.governance.Approval` or `sentinel_engine.governance.Policy` — both remain exactly as they are today, in name, shape, and behavior.
- Any change to `applications/*/bootstrap.py`.
- Any change to `sentinel_engine/ledger/`, `sentinel_engine/repositories/`, or any existing composition boundary (including ADR-013's `sentinel_engine/composition/evidence.py`, which this ADR does not touch or extend).
- Any test beyond what is strictly required to confirm the dataclass itself is well-formed (field names/types), if and when this ADR is accepted and that minimal step is separately taken.

---

## 4. Relationship to ADR-004

This ADR does **not** resolve ADR-004. It does not select Option A, B, or C for ledger ownership, and it does not authorize any backend, reader, or ledger-touching code.

**Implementation of `ConstitutionRuleCheck` — i.e., any adapter or reader that would populate it from real data — requires both:**

1. **Phase 1A's 30-day validation window closing (2026-08-27) and its results being reviewed**, per ADR-004 §1; and
2. **ADR-004's own Option A/B/C ledger-ownership choice being separately made**, since any reader touching `constitution_enforcement_events` is exactly the kind of ledger-integration work ADR-004 §1 and §6 gate behind that choice.

Neither condition is satisfied today. This ADR does not attempt to satisfy them — it only makes the contract shape available to name in advance, at zero implementation cost, the same way ADR-004 kept `LedgerStore` abstract "at zero sunk cost" while deferring its backend choice.

---

## 5. Relationship to ADR-013 and ADR-015

This ADR follows the same self-limiting pattern both already established in this repository:

- Like **ADR-015**, this ADR is classification-only: it names something (there, module core-vs-product status; here, a contract shape) without moving, building, or wiring anything.
- Like **ADR-013**, this ADR contains an explicit, exhaustive non-authorization list rather than relying on silence to imply restraint.

Neither ADR-013 nor ADR-015 is modified, superseded, or amended by this ADR.

---

## 6. Explicit Non-Decisions

This ADR does **not** decide:

1. The module path or file location for `ConstitutionRuleCheck`.
2. Any adapter, reader, or query-service design.
3. Any Trading Intelligence projection or UI design (e.g. a future "Audit Trail" section).
4. ADR-004's Option A, B, or C.
5. Whether `check_result`/`action_taken` should become typed enums (`ApprovalStatus`-style) rather than `str`, versus staying as plain strings mirroring the real `constitution_enforcement_events` column types as written today.
6. Whether a `GovernanceEntry`-style "narrower" projection type would later wrap this contract for UI consumption (the existing precedent — `EvidenceEntry`/`GovernanceEntry`/`ApprovalEntry` each narrow their sentinel_engine-side summary type) — that remains a future, separately governed design step.
7. Any timeline for revisiting this ADR beyond "no earlier than 2026-08-27, and only after ADR-004's ownership choice."

---

## 7. Consequences

**Positive:**
- Gives future governance a citable, already-reasoned starting shape instead of re-deriving the six-row structure from `bot/trust_ledger/constitution.py` again later.
- Zero implementation risk: no code exists yet to protect against reuse creep (unlike ADR-013's temporary repositories, which required an explicit "primary risk" section).
- Keeps `Approval`/`Policy` untouched, avoiding any risk to their existing tested behavior.

**Negative:**
- Provides no functional capability by itself; a user sees nothing new until a separate, future ADR authorizes the reader/adapter/UI work.
- The shape may need revision once real Phase-1A data is reviewed (e.g., if `check_result` values in practice include states not yet seen in the current codebase, such as a documented-but-unobserved `FAIL`).

---

## 8. Acceptance Criteria

This ADR may be considered accepted only when:

- It names exactly one new contract shape (`ConstitutionRuleCheck`, 7 fields as listed in §2).
- It authorizes no adapter, reader, projection, service, controller, or UI change.
- It authorizes no access to `bot/trust_ledger/`, `ledger/`, or `database/`.
- It modifies neither `Approval` nor `Policy`.
- It does not resolve ADR-004's Option A/B/C choice.
- It states plainly that implementation requires both Phase 1A completion/review and ADR-004's ownership decision.
- Its status is recorded as **Proposed — Implementation Deferred**, not Accepted, not Frozen, until explicitly approved otherwise.

---

## 9. Decision Statement

> **Name a proposed contract shape, `ConstitutionRuleCheck` (`decision_id`, `rule_id`, `rule_name`, `check_result`, `action_taken`, `reason`, `checked_at`), for the eventual representation of Trading Constitution rule-check data in `sentinel_engine`.**
>
> **This ADR authorizes naming the shape only. It authorizes no file creation, no adapter, no reader, no projection, no UI change, and no access to `bot/`, `ledger/`, or `database/`.**
>
> **It does not modify `Approval` or `Policy`, and it does not resolve ADR-004.**
>
> **Implementation is deferred until both Phase 1A's validation window closes and is reviewed (no earlier than 2026-08-27), and ADR-004's ledger-ownership choice is separately made.**

---

## 10. Status

**Proposed — Implementation Deferred.**

No implementation of any kind is authorized by this draft.
