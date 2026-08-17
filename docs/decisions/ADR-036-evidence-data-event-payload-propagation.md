# ADR-036: Evidence.data Propagation to EVIDENCE_ATTACHED Event.payload

**Status:** Accepted
**Date:** 2026-08-17
**Decision Type:** Architecture — Additional Governance Decision Required by ADR-013 §16/§20 (Accepted)
**Related ADRs:** ADR-013 (governs `EvidenceService`; this ADR is the "new governance decision" its §16/§20 anticipates), ADR-009 (authorizes the bot→sentinel_engine evidence call this ADR does not modify), ADR-012 (governs `evidence_adapter.py`; unchanged), ADR-034 (write-side origin of the headline data this ADR makes visible), ADR-004 (deferred ledger-ownership decision; not selected or implied by this ADR)

---

## 1. Context

A read-only architectural investigation (this session, 2026-08-17) traced the
complete existing read path for Sentinel Engine `Evidence`:

```
Evidence → EvidenceService.associate_evidence() → Event.payload
  → DecisionQuery.get_decision_timeline() → EvidenceSummary
  → SentinelEvidenceSource → EvidenceEntry
  → DecisionDetailArea → gradio_view.py
```

The trace found that `Evidence.data` — the free-form per-model payload
`build_model_outputs()` produces, including ADR-034's `finbert.metadata.
headlines` — is discarded not at the UI layer, and not inside `DecisionQuery`,
but earlier: inside `EvidenceService.associate_evidence()`
(`sentinel_engine/services/evidence_service.py:33-44`), when the
`EVIDENCE_ATTACHED` `Event.payload` dict is constructed. That dict currently
carries exactly `decision_id`, `evidence_id`, `evidence_type`, `source` — never
`data`. Every downstream component (`EvidenceSummary`, `EvidenceEntry`,
`gradio_view.py`) has nothing to read, because the data was never made
durable past that one call.

A second, non-durable copy of `Evidence.data` does exist —
`EvidenceService`'s private `_evidence_by_decision` dict
(`evidence_service.py:26,31`), reachable via `get_evidence_for_decision()`
— but ADR-013 §14 ("Process-Local State Limitation") establishes that this
state does not survive or cross OS process boundaries. The bot (CLI/watchdog
process) and any Trading Intelligence read process are always separate
processes. This path is architecturally dead for this purpose, independent
of any governance question, and this ADR does not rely on it.

### Why this requires its own ADR

ADR-013 §17 scopes what ADR-013's *own* implementation was authorized to
touch when it was accepted (2026-08-11) — it is not a standing, permanent
prohibition on `EvidenceService` ever changing, and this ADR does not treat
it, or supersede it, as one. The actual governing clause is ADR-013 §16
("Future Migration Requirement") and §20's "Primary Risk" subsection: the temporary
`EvidenceService`/ledger wiring "shall not acquire additional
responsibilities" beyond what §5 scopes it to today, and "any expansion
requires a new governance decision." Adding a `data` key to
`EVIDENCE_ATTACHED`'s payload is exactly that class of expansion. **This ADR
is that governance decision.** ADR-013 itself remains in force, unmodified,
and is not superseded by anything in this ADR.

## 2. Evidence

A follow-on read-only audit (this session) verified, file-by-file, that this
change conflicts with nothing:

- **No accepted ADR or doc asserts a fixed `EVIDENCE_ATTACHED` payload
  shape.** Every "four" reference found (`ADR-020:71`, `ADR-021:68`,
  `SENTINEL_ENGINE_PHASE1_DECISION_LIFECYCLE.md:81,99`,
  `decision-state-enum.md:7,13`) means the four lifecycle event *types*
  (`DECISION_CREATED`/`EVIDENCE_ATTACHED`/`GOVERNANCE_EVALUATED`/
  `APPROVAL_RECORDED`), never a per-event payload key count.
- **Exactly one production consumer indexes `EVIDENCE_ATTACHED`'s payload**:
  `sentinel_engine/queries/decision_query.py:80-82`, by named key
  (`event.payload["evidence_id"]` etc.), never by unpacking the whole dict.
  An added key is invisible to it.
- **No test asserts an exact key set or length** against real
  `EvidenceService` output. `sentinel_engine/tests/test_evidence_service.py:
  130-133` and `sentinel_engine/tests/test_decision_query.py` assert
  individual keys/values only. The one whole-dict equality assertion found
  (`sentinel_engine/tests/test_event.py:26`) is against a self-constructed
  generic `Event` fixture with `event_type="DECISION_CREATED"` — it never
  exercises `EvidenceService` and is unaffected.
- **No serialization constraint applies.** ADR-013 §4.1 already prohibits
  the temporary `LedgerStore` from introducing serialization; it is a bare
  in-memory `List[Event]`. `Event.payload: Dict[str, Any]`
  (`sentinel_engine/events/event.py:12`) is unconstrained by design, and
  other event types already carry differing key counts (`DECISION_CREATED`:
  6, `GOVERNANCE_EVALUATED`: 3, `APPROVAL_RECORDED`: 4) with no uniform-shape
  convention to violate.
- **No historical-compatibility exposure.** The temporary ledger is
  process-local and non-durable (ADR-013 §14); no persisted prior-shaped
  `EVIDENCE_ATTACHED` data exists for a new-shaped reader to ever encounter,
  and ADR-013 §16 already anticipates this data being replaced, not
  migrated, at any future backend cutover.

**The application-layer half already has a working, tested precedent.**
`DecisionQuery.get_decision_timeline()` already returns
`DecisionTimeline.events: List[Event]` as a public field
(`decision_query.py:49,113`) — full, unfiltered `Event` objects, including
`.payload`, with **zero further sentinel_engine change required to read
it**. `SentinelAuditSource.get_audit_trail()`
(`applications/trading_intelligence/adapters/sentinel_audit_source.py:
38-46`) already consumes exactly this field, mapping `event.payload`
straight into `AuditEntry.payload`, today, for every event type. This ADR's
application-layer authorization is the same pattern applied to
`SentinelEvidenceSource`, not a new one.

## 3. Decision

Authorize exactly three additive changes:

### 3.1 Fix 1 — include `data` in the EVIDENCE_ATTACHED payload

- **File/lines:** `sentinel_engine/services/evidence_service.py:37-42`
  (`EvidenceService.associate_evidence()`).
- **Current:** `payload={"decision_id": ..., "evidence_id": ...,
  "evidence_type": ..., "source": ...}`.
- **Corrected:** add `"data": evidence.data` to that same dict literal.
  No signature change to `associate_evidence()`, no change to `Evidence`,
  `Event`, `LedgerRepository`, `ProjectionRepository`, or any other
  `EvidenceService` method. `evidence.data` is already available at this
  call site — it is a field of the `Evidence` object already passed in.
- **Risk:** Low. Additive key on an already-arbitrary `Dict[str, Any]`
  field; §2 confirms zero existing consumer or test is sensitive to it.

### 3.2 Fix 2 — thread `data` through the Trading Intelligence evidence adapter

- **File:** `applications/trading_intelligence/adapters/
  sentinel_evidence_source.py`.
- **Current:** `SentinelEvidenceSource.get_evidence()` reads only
  `timeline.evidence` (the narrow `EvidenceSummary` list).
- **Corrected:** also consult the already-public `timeline.events`, find
  each `EventType.EVIDENCE_ATTACHED` event whose `payload["evidence_id"]`
  matches the current `EvidenceSummary.evidence_id`, and pass
  `event.payload.get("data", {})` into the new `EvidenceEntry.data` field
  (§3.3). Mirrors `SentinelAuditSource.get_audit_trail()`'s existing pattern
  exactly (§2). `DecisionQuery` and `EvidenceSummary` are not modified.
- **Risk:** Low. New logic confined to one adapter file already governed
  entirely by `applications/trading_intelligence/`'s own conventions —
  outside ADR-002's protected paths.

### 3.3 Fix 3 — widen the application-layer `EvidenceEntry` projection

- **File:** `applications/trading_intelligence/projections/
  evidence_entry.py`.
- **Current:** `EvidenceEntry(evidence_id, evidence_type, source,
  attached_at)` — no `data` field; its own docstring explicitly defers this
  ("rendering that free-form dict remains a separate, later decision").
- **Corrected:** add `data: Dict[str, Any] = field(default_factory=dict)`.
  The default preserves every existing `EvidenceEntry(...)` construction
  site (tests and elsewhere) unchanged, matching the same
  default-preserves-existing-callers shape ADR-034 used for
  `sentiment_headlines`.
- **Risk:** Low. Additive dataclass field with a safe default.

**Not authorized by this ADR:** any change to `gradio_view.py` or any other
rendering of `EvidenceEntry.data` — surfacing it in the UI is explicitly
future, separate work (per the original investigation's own instruction that
UI design is out of scope).

## 4. Explicit Non-Authorization

This ADR authorizes **only** the three changes in §3, across the three named
files. It does not authorize:

- Any change to `EvidenceSummary` or `DecisionQuery`'s public contract —
  both stay exactly as they are; `EvidenceSummary` is not widened (the
  application layer reads `timeline.events` directly instead, an already-
  public field).
- Any change to `bot/` — none is needed. `to_evidence_records()`'s output
  already flows into `associate_evidence()` unchanged; `evidence.data` is
  already present at the one call site being modified.
- Any new consumer of `EvidenceService`. Trading Intelligence continues to
  reach evidence exclusively through `DecisionQuery`, exactly as today —
  it never calls `EvidenceService` directly. ADR-013 §21's "no additional
  `EvidenceService` consumer" criterion is not implicated by this ADR.
- Reading `bot/trust_ledger.db`'s `decision_events.model_outputs` column
  directly from Trading Intelligence. This alternative was explicitly
  considered and rejected during the investigation: it requires zero
  sentinel_engine change, but it creates a second, parallel read source
  for Decision Center (duplicating exactly what `sentinel_evidence_source.
  py`'s own docstring says it deliberately avoids), and it would enact a
  piece of ADR-004's Option A ("Trading Intelligence owns the operational
  ledger") ahead of ADR-004's own explicit deferral. Not selected.
- Widening `EvidenceSummary` instead of extending the adapter (the
  alternative "Option D" from the investigation). Rejected as unnecessarily
  large: `EvidenceSummary` is consumed by *both* product bootstraps
  (`applications/trading_intelligence/bootstrap.py` and
  `applications/wealth_intelligence/bootstrap.py`, per ADR-015), so
  widening it has a larger blast radius than extending one product's own
  adapter, for no additional capability — `DecisionTimeline.events` already
  carries everything needed.
- Any UI/rendering change (`gradio_view.py` or elsewhere).
- Any new Evidence provenance schema. `Evidence.data`'s existing shape
  (established by ADR-012/ADR-034) is used exactly as-is.
- Any persistence, schema, or ledger-backend change. The temporary
  in-memory ledger (ADR-013) is unchanged in kind — still non-durable,
  still process-local. ADR-004 remains fully deferred and unselected.
- Any change to ADR-002, ADR-004, ADR-009, ADR-012, or ADR-013 themselves.

## 5. Relationship to ADR-013

ADR-013 remains in force, unmodified, and is not superseded by this ADR.
This ADR is the "new governance decision" ADR-013 §16/§20 explicitly
anticipates and requires before the temporary `EvidenceService`/ledger
wiring's payload responsibility can expand beyond its original §5 scope.
ADR-013's own restrictions not implicated here — process-local lifetime,
no new repository implementation, no new persistence, `bot → sentinel_engine`
dependency direction, no application-bootstrap coupling — all remain
unchanged and are re-affirmed, not re-opened, by this ADR.

## 6. Relationship to ADR-012

ADR-012 remains unchanged and fully in force. This ADR does not modify
`sentinel_engine/adapters/evidence_adapter.py`, `to_evidence_records()`, or
any evidence translation semantics. `Evidence.data` reaching this ADR's one
changed call site is exactly the shallow-copied `model_outputs[model]`
dict ADR-012 already established — no new translation logic is introduced.

## 7. Relationship to ADR-004

This ADR makes no ledger-ownership decision and does not read
`bot/trust_ledger.db` (see §4). It does not select, imply, or move toward
any of ADR-004's Option A/B/C. The temporary sentinel_engine ledger
(ADR-013) remains exactly as non-production and non-durable as before —
this ADR only changes what one already-arbitrary payload dict carries
within it.

## 8. Tests Required

- New unit test in `sentinel_engine/tests/test_evidence_service.py`,
  sibling to the existing
  `test_associate_evidence_writes_evidence_attached_event_with_correct_payload`:
  asserts `events[0].payload["data"] == evidence.data` for a non-empty
  `Evidence.data` dict.
- New unit test confirming `DecisionQuery.get_decision_timeline()`'s
  `EvidenceSummary`/`timeline.evidence` output shape is unchanged (proves
  §4's "no `EvidenceSummary` widening" claim, not just assumes it).
- New unit test(s) in `applications/trading_intelligence/tests/
  test_sentinel_evidence_source.py`: given a `timeline.events` entry
  carrying `data`, `EvidenceEntry.data` reflects it unchanged; given no
  matching `EVIDENCE_ATTACHED` event or a missing `data` key, defaults to
  `{}`, not an error.
- New unit test confirming existing `EvidenceEntry(...)` construction
  sites that omit `data` still work (default `{}` applies).
- Full existing suite re-run: `sentinel_engine/tests/`,
  `applications/trading_intelligence/tests/` — zero regressions required.
  `pytest tests/` (bot's own suite) is not expected to be affected, since
  no `bot/` file changes, but should be re-run as a sanity check matching
  this session's established practice.

## 9. Verification

Unlike ADR-026/ADR-034, this ADR touches no `bot/`-protected path and no
`.github/workflows/*.yml` — neither the CLI trading-trigger path
(`trade.yml` → `bot/main.py`) nor the watchdog-mediated path
(`watchdog.yml` → `dashboard/http_endpoints.py` → `scheduler/` →
`bot.main.run()`) executes any of the three changed files. ADR-002's
two-entry-point verification requirement therefore does not apply to this
ADR, and this is stated explicitly rather than assumed.

Verification instead consists of:

- The round-trip test (§8) proving `evidence.data` survives
  `EvidenceService.associate_evidence()` → `LedgerRepository` →
  `DecisionQuery.get_decision_timeline()`'s `events` field →
  `SentinelEvidenceSource` → `EvidenceEntry.data`, exercised end to end,
  not assumed from unit tests of each layer in isolation.
- Full `sentinel_engine/tests/` and `applications/trading_intelligence/
  tests/` suites passing, zero regressions.
- `scripts/arch_review.py --diff` clean on the three changed files.

## 10. Rollback Plan

All three changes are additive (one new dict key, one new adapter code
path, one new dataclass field with a safe default) and non-schema,
non-persistent — the temporary ledger is in-memory only and is discarded on
every process restart regardless. Rollback is a plain `git revert` of the
implementing commit(s). No data-level rollback step is required.

## 11. Consequences

**Positive:**

- Closes the gap the original investigation was commissioned to find:
  ADR-034's `finbert.metadata.headlines` (and the SHAP drivers /
  degradation flag / raw scores already sitting unused in `Evidence.data`)
  become reachable by Trading Intelligence's read side for the first time,
  without widening any shared sentinel_engine contract.
- Satisfies ADR-013 §16/§20's own anticipated governance requirement
  explicitly, rather than leaving the temporary ledger's payload scope
  informally frozen indefinitely.
- Reuses an already-tested pattern (`SentinelAuditSource`) instead of
  inventing a new one, per the original investigation's explicit
  constraint against a one-off pathway.
- Zero `bot/` change, zero ADR-002 involvement, zero new ADR-004 exposure.

**Negative:**

- Does not itself make headlines (or anything else in `Evidence.data`)
  visible in the UI — that remains separate, unauthorized future work.
- Does not resolve ADR-004's deferred ledger-ownership question; Decision
  Center's evidence detail remains sourced from the temporary, non-durable
  ledger until that separate decision is made.
- Adds one more field the temporary `EvidenceService` wiring's payload
  scope now depends on being carried forward correctly whenever ADR-013's
  eventual production migration (§16) happens — a small, explicitly
  accepted increase to that future migration's surface.

## 12. Status

**Accepted.** This ADR is now authoritative per `docs/DOCUMENT_INDEX.md`'s
documentation hierarchy — the three corrections named in §3 are
authorized, strictly bounded by §4's Explicit Non-Authorization list.
Acceptance authorizes the payload-propagation exception itself; it does
not waive §8's required tests or §9's verification requirements — those
remain preconditions to be satisfied during implementation, not
retroactively satisfied by acceptance.
