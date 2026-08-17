# ADR-037: Decision Center Rendering of EvidenceEntry.data Metadata

**Status:** Accepted
**Date:** 2026-08-17
**Decision Type:** Architecture — View-Layer Presentation Authorization (Accepted)
**Related ADRs:** ADR-034 (write-side origin of `finbert.metadata.headlines`; §3.4's semantic-scope constraint governs this ADR's rendering of it), ADR-036 (made `EvidenceEntry.data` reachable but explicitly deferred rendering it — this ADR is that deferred work), ADR-022 (confirms `applications/trading_intelligence/ui/decision_center/` as the correct, undisputed package location for this UI; not re-litigated here), ADR-012 (governs the `Evidence.data`/`model_outputs` shape this ADR renders, not modifies)

---

## 1. Context

ADR-036 propagated `Evidence.data` through to `EvidenceEntry.data`
(`applications/trading_intelligence/projections/evidence_entry.py`) but
explicitly declined to authorize displaying it:

> "Not authorized by this ADR: any change to `gradio_view.py` or any other
> rendering of `EvidenceEntry.data` — surfacing it in the UI is explicitly
> future, separate work." (ADR-036 §3)

A follow-on read-only scoping audit (this session, 2026-08-17) traced the
existing Evidence card rendering path and found:

- `_format_evidence_html` (`gradio_view.py:739-754`) currently renders only
  `entry.evidence_type`/`entry.source`/`entry.attached_at` via
  `_record_card_html` (`gradio_view.py:891-950`), which already
  `html.escape()`s every `(label, value, is_tabular)` field it's given
  (lines 929-936).
- `_record_card_html` already accepts an `extra_html` parameter for an
  expandable detail block, used today by exactly one caller —
  `_format_audit_detail_html` (`gradio_view.py:809-831`) — which renders an
  arbitrary dict as a native `<details>`/`<summary>` disclosure, reusing the
  same escaped-field markup classes. This is a working, tested precedent
  for exactly the kind of rendering this ADR authorizes, not a new pattern.
- No `EvidenceEntry`, `DecisionQuery`, or `EvidenceService` change is
  required — `EvidenceEntry.data` already exists and is already populated
  (ADR-036); this is pure view-layer work.
- Two real risks were identified, both addressed in §3 below: (a)
  `bot/strategy/model_output_adapter.py:6-12`'s own docstring documents
  that per-model `signal` is "NOT the ensemble's actual trading decision...
  Conflating the two would misrepresent what actually drove a
  BUY/SELL/HOLD action" — the same caution applies to per-model
  `confidence`, which is distinct from `DecisionView.confidence` (the
  ensemble's `final_confidence`) already shown elsewhere in the UI; (b)
  `headlines` is a `list[str]` — naively `str()`-ing it (mirroring
  `_format_audit_detail_html:818`'s existing `str(value)` pattern) would
  render as a Python list repr (`"['A', 'B']"`), not readable text.

This ADR is the governance decision that authorizes closing that gap.

## 2. Decision

Authorize exactly two additive changes, both confined to the two files
named in this ADR's title area:

### 2.1 New function — evidence detail rendering

- **File:** `applications/trading_intelligence/ui/decision_center/
  gradio_view.py`.
- **New static method**, sibling to `_format_audit_detail_html`:
  `_format_evidence_detail_html(metadata: Dict[str, Any]) -> str`.
- **Behavior:** renders **exactly and only** these five keys from
  `EvidenceEntry.data["metadata"]`, when present, as an expandable
  `<details>`/`<summary>` disclosure reusing `_record_card_html`'s existing
  escaped-field markup (`aara-record-card-fields`/`aara-record-field`/
  `record-label`/`record-value` classes) — the same reuse
  `_format_audit_detail_html` already demonstrates:
  - `shap_drivers` — rendered as readable feature/value pairs (e.g. one row
    per driver, "feature: shap_value"), not a raw Python repr of the list.
  - `is_degraded` — rendered as a human-readable Yes/No, not `str(bool)`.
  - `val_loss` — rendered as a plain number, or an explicit "N/A" when
    `None`.
  - `raw_score` — rendered as a plain number.
  - `headlines` — rendered as **individually readable items** (e.g. one
    row/line per headline), never a single `str(list)` dump. An empty list
    renders as an explicit empty/absent state, not a blank field.
  - **Any other current or future key inside `metadata`** is not rendered
    by this function and is not authorized for rendering by this ADR. A
    future metadata key requires its own governance decision before
    display, matching this project's established narrow-authorization
    discipline — this ADR does not pre-authorize an open-ended "render
    whatever's in metadata" dump.
  - **`signal` and `confidence` are top-level sibling keys of `metadata`
    on `EvidenceEntry.data`, not keys inside `metadata` itself** (see
    `bot/strategy/model_output_adapter.py:51-73`:
    `{"signal": ..., "confidence": ..., "metadata": {...}}`). They are
    outside this function's input entirely — `_format_evidence_detail_html`
    receives only the `metadata` sub-dict (§2.2) — and remain explicitly
    excluded from rendering per §2.3.
- **Escaping:** every interpolated value passes through `html.escape()`,
  exactly as `_record_card_html` and `_format_audit_detail_html` already
  require of every other field in this file. No interpolation of
  `metadata` content is authorized outside that mechanism.
- **No narrative interpretation:** the function renders factual
  labeled values only. It must not compose sentences characterizing what
  the data means, implies, or caused (the same discipline
  `_format_evidence_html`'s existing fields already follow — contrast with
  `_format_why_summary_html`, which does compose interpretive sentences
  and is not modified or used as a model by this ADR).

### 2.2 Wire the new function into the Evidence card

- **File:** same file, `_format_evidence_html` (`gradio_view.py:739-754`).
- **Corrected:** pass `DecisionCenterUI._format_evidence_detail_html(
  entry.data.get("metadata", {}))` as `_record_card_html`'s `extra_html`
  argument for each evidence card — the same call shape
  `_format_audit_html` already uses for `_format_audit_detail_html`
  (`gradio_view.py:797-803`).
- **Not authorized:** any change to the card's existing header fields
  (`evidence_type`/`source`/`attached_at` remain exactly as rendered
  today); any change to `_record_card_html`, `_record_list_html`, or any
  other card type (Governance/Approval/Audit).

### 2.3 Explicit exclusion — top-level `signal`/`confidence`

Neither `EvidenceEntry.data["signal"]` nor `EvidenceEntry.data["confidence"]`
is rendered by this ADR's first implementation, in either the Evidence
card's header or its new detail disclosure. Per §1, both are per-model
informational values — not the ensemble's actual decision (already shown
via `DecisionView.action`/`DecisionView.confidence` elsewhere on the same
screen) — and displaying them without very deliberate framing risks a
user reading a per-model BUY/SELL/HOLD signal as the decision itself.
Authorizing that display, if ever wanted, is separate future work requiring
its own explicit framing decision, not an extension of this ADR.

## 3. Explicit Non-Authorization

This ADR authorizes **only** §2's two changes, across the two named files.
It does not authorize:

- Any change to `EvidenceEntry`, `DecisionQuery`, `EvidenceSummary`, or
  `EvidenceService` (`sentinel_engine/` or the `EvidenceEntry`/
  `SentinelEvidenceSource` files ADR-036 already authorized). This ADR
  reads only the already-existing `EvidenceEntry.data` field; it adds
  nothing to what any of those already return.
- Any change to `bot/`, persistence, schema, the trust ledger, or any
  ledger-backend selection (ADR-004 remains fully deferred, untouched).
- Any new Evidence provenance schema or semantics. `Evidence.data`'s shape
  (ADR-012/ADR-034) is rendered exactly as it already exists — this ADR
  adds a display, not a field.
- Rendering top-level `signal` or `confidence` (§2.3).
- Rendering any `metadata` key other than the five named in §2.1.
- Any narrative/interpretive text generation about what the rendered data
  means or implies (§2.1).
- Any change to `_format_why_summary_html`, `_format_audit_detail_html`,
  or any other existing render function, card type, or CSS class beyond
  the one new function and one call-site wiring named in §2. In
  particular, this ADR does not fix the pre-existing, unrelated
  `ApprovalStatus` `str()`-formatting defect in `_format_audit_detail_html`
  found during the same investigation that produced this ADR — that
  remains a separate, unauthorized fix.
- Any unrelated UI change, visual redesign, or CSS addition beyond what
  rendering five new fields structurally requires.

## 4. Relationship to ADR-034

ADR-034 §3.4 ("Semantic scope of `headlines`") remains binding on this
ADR's rendering of that field:

> "It must not be represented, in this ADR or in any later consumer of
> this field, as the complete rationale, proof, causal explanation, or
> deterministic basis of the investment decision."

`_format_evidence_detail_html` (§2.1) satisfies this by construction —
factual, labeled, unnarrated display, inside an evidence card that already
sits alongside the decision's real basis (`final_confidence`, the gate
trace) displayed elsewhere on the same screen, not in place of it.

## 5. Relationship to ADR-036

This ADR is exactly the "future, separate work" ADR-036 §3/§11 named and
declined to authorize itself. It makes no change to anything ADR-036
authorized or to `EvidenceEntry.data`'s shape — it only displays a field
that already exists and is already populated.

## 6. Relationship to ADR-022

ADR-022 already settled that product-facing evidence UI belongs in
`applications/trading_intelligence/ui/decision_center/`, not
`sentinel_engine/`. This ADR's two files are both already inside that
already-authorized location; ADR-022's ownership question is not reopened
or re-litigated here.

## 7. Tests Required

- New unit test(s) for `_format_evidence_detail_html`: given a `metadata`
  dict containing all five authorized keys, asserts each renders with a
  readable label and value; given `headlines=[]`, asserts an explicit
  empty state, not a blank or missing field; given `headlines` with
  multiple entries, asserts each appears as an individually readable item,
  not a single `str(list)` value; given a `metadata` dict containing an
  unauthorized/unknown key, asserts it does not appear in the rendered
  output.
- New unit test confirming `val_loss=None` renders as an explicit `N/A`
  value, proving it is neither the literal string `"None"` nor a blank/
  empty field in the rendered output.
- New unit test confirming HTML-unsafe characters in a headline (e.g.
  `<script>`) are escaped in the rendered output, not passed through raw.
- New unit test confirming `_format_evidence_html`'s existing header
  fields (`evidence_type`/`source`/`attached_at`) are unchanged by this
  ADR — extends `applications/trading_intelligence/ui/tests/
  test_gradio_view.py`'s existing Evidence-card coverage rather than
  replacing it.
- New unit test confirming `EvidenceEntry.data["signal"]` and
  `["confidence"]`, when present, do not appear anywhere in the rendered
  Evidence card output (proves §2.3, not just assumes it).
- Full existing `applications/trading_intelligence/ui/tests/` suite
  re-run — zero regressions required.

## 8. Verification

Like ADR-036 and unlike ADR-026/ADR-034, this ADR touches no `bot/`
protected path and no `.github/workflows/*.yml` — ADR-002's
two-entry-point trading-trigger verification does not apply. Verification
consists of: the tests in §7 passing; a manual visual check of the
Decision Center's Evidence section against real or seeded decision data
confirming headlines/SHAP drivers/degradation flag/raw score render
legibly; and `scripts/arch_review.py --diff` clean on the two changed
files.

## 9. Rollback Plan

Both changes are additive (one new function, one call-site wiring) and
touch no data, persistence, or contract. Rollback is a plain `git revert`
of the implementing commit(s). No data-level rollback step is required.

## 10. Consequences

**Positive:**

- Closes the loop this session's work opened: ADR-034 (capture headlines)
  → ADR-036 (propagate to the read side) → this ADR (display them) — a
  user can finally see why `finbert`'s score was what it was, and the
  SHAP/degradation context for `xgboost`/`lstm`, without any of it being
  misrepresented as the decision's actual basis.
- Reuses an already-tested rendering pattern
  (`_format_audit_detail_html`'s escaped-disclosure mechanism) rather than
  inventing new markup or a new escaping discipline.
- Explicit exclusion of `signal`/`confidence` (§2.3) and the five-key
  allowlist (§2.1) keep this ADR from silently authorizing rendering of
  whatever `metadata` happens to contain in the future.

**Negative:**

- Does not address the pre-existing `ApprovalStatus` rendering defect in
  the neighboring Audit detail disclosure — a known, separate issue left
  as-is.
- Does not render `signal`/`confidence` at all in this pass — a real,
  deliberately deferred limitation, not an oversight; revisiting it
  requires its own future framing decision.

## 11. Status

**Accepted.** This ADR is now authoritative per `docs/DOCUMENT_INDEX.md`'s
documentation hierarchy — the two changes named in §2 are authorized,
strictly bounded by §3's Explicit Non-Authorization list. Acceptance
authorizes this view-layer presentation itself; it does not waive §7's
required tests or §8's verification requirements — those remain
preconditions to be satisfied during
implementation, not retroactively satisfied by acceptance.
