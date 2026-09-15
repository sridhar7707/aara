"""Decision Center screen structure -- V1 prototype.

No rendering framework: this project has no frontend toolchain wired into
applications/trading_intelligence/ (dashboard/'s Gradio app is separate and
protected). Screen areas are plain, framework-independent dataclasses,
testable the same way DecisionView/DecisionContract already are, per
docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md's layout
(Section 4). No sentinel_engine, bot, dashboard, database, or ledger import.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry

# P1 UI-only timestamp fix (GOOGL/dec-seed-004 timestamp audit): every
# timestamp this application stores or reads -- Decision.timestamp,
# Evidence.collected_at, Approval.timestamp, and GovernanceService's own
# internal datetime.utcnow() stamp -- is a naive datetime whose implicit
# meaning is UTC; there is no tz-aware datetime anywhere in the read chain
# (sentinel_engine/projections/decision_projection.py through
# DecisionContract/DecisionView all carry naive datetimes unchanged). This
# converts that naive-UTC value to America/Chicago for display only, DST-
# aware (CST/CDT) via the stdlib zoneinfo module -- it does not touch the
# stored value, sort order (callers still sort/compare the original naive
# datetime), or any sentinel_engine/contracts/projections code. Both
# gradio_view.py and this module's own timestamp_display below call this
# one function so every Decision Center timestamp (list, detail header,
# Evidence, Governance, Approval, Audit Trail) converts identically.
_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")
_NAIVE_SOURCE_TIMEZONE = ZoneInfo("UTC")


def format_display_timestamp(moment: datetime) -> str:
    """Formats a naive-but-UTC datetime for display in America/Chicago,
    e.g. "2026-08-21 14:45 CDT" (summer) or "2026-01-08 09:40 CST"
    (winter) -- %Z renders whichever abbreviation applies via zoneinfo's
    own DST rules, never a fixed offset."""
    aware = moment.replace(tzinfo=_NAIVE_SOURCE_TIMEZONE)
    return aware.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")


# ---------------------------------------------------------------------------
# ADR-070 Sprint 3 Batch 2 -- recommendation-surfacing presentation semantics.
#
# Pure, deterministic formatting over the Batch 1 read-model fields
# (DecisionView.action_source, DecisionView.action, DecisionView.confidence,
# EvidenceEntry.polarity). Nothing here re-forms a recommendation, recomputes
# or calibrates confidence, aggregates evidence, or implies execution /
# approval / scheduling. Provenance is authoritative: a decision is only
# ever called a "Sentinel recommendation" when action_source is exactly
# "SENTINEL" -- never inferred from action, confidence, evidence, status, or
# symbol.
# ---------------------------------------------------------------------------

SENTINEL_RECOMMENDATION_LABEL = "Sentinel recommendation"
INTERPRETED_STRATEGY_DECISION_LABEL = "interpreted strategy decision"
SENTINEL_NON_CONCURRENCE_STATEMENT = "Sentinel does not concur at this time."
CONFIDENCE_QUALIFIER = "Uncalibrated ensemble model score"
EVIDENCE_POLARITY_SUPPORTED_LABEL = "Supported the BUY"
EVIDENCE_POLARITY_CONTRADICTED_LABEL = "Contradicted the BUY"
EVIDENCE_POLARITY_UNAVAILABLE_LABEL = "Polarity unavailable"

_SENTINEL_ACTION_SOURCE = "SENTINEL"
_WAIT_ACTION = "WAIT"
_SUPPORTING_POLARITY = "SUPPORTING"
_CONTRADICTING_POLARITY = "CONTRADICTING"
_DECISION_CREATED_EVENT_TYPE = "DECISION_CREATED"
_MODEL_ENSEMBLE_EVIDENCE_TYPE = "MODEL_ENSEMBLE"


def entry_ensemble_score_from_evidence(
    evidence: Tuple[EvidenceEntry, ...]
) -> Optional[float]:
    """The recorded MODEL_ENSEMBLE.ensemble score for this decision, read
    verbatim from the already-loaded Evidence section -- never recomputed,
    re-weighted, or otherwise touched (that calculation lives entirely in
    bot/strategy/ensemble.py, untouched). None when no MODEL_ENSEMBLE entry
    is attached, the "ensemble" key is absent (adapters/
    trade_decision_derivation.py omits it rather than storing a fabricated
    0.0 when the underlying trades row has no ensemble_score), or the value
    is not a real number (bool is deliberately excluded -- it is a subclass
    of int in Python but never a real score here)."""
    for entry in evidence:
        if entry.evidence_type != _MODEL_ENSEMBLE_EVIDENCE_TYPE:
            continue
        value = (entry.data or {}).get("ensemble")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)
    return None


# Decision Quality Cross-Linking: duplicated verbatim from
# ui.performance_learning.screen.CALIBRATION_MIN_OUTCOMES -- the same
# conservative display floor, not a second methodology. decision_center/
# stays self-contained (it must not import ui.performance_learning, per
# this product's per-screen self-containment convention -- see
# ui/tests/test_performance_learning_structure.py's own forbidden-sibling
# check), so the value is duplicated here rather than imported. If that
# floor ever changes, both constants must be updated together.
CALIBRATION_MIN_OUTCOMES = 30


def provenance_label(action_source: Optional[str]) -> str:
    """"Sentinel recommendation" iff ``action_source`` is exactly
    ``"SENTINEL"``; every other value -- ``"STRATEGY"``, ``None``, or any
    unexpected string -- is an "interpreted strategy decision" (ADR-070 §6).
    Provenance is never inferred from any other field."""
    if action_source == _SENTINEL_ACTION_SOURCE:
        return SENTINEL_RECOMMENDATION_LABEL
    return INTERPRETED_STRATEGY_DECISION_LABEL


def is_sentinel_recommendation(action_source: Optional[str]) -> bool:
    """True only for the exact literal ``"SENTINEL"``. An unexpected
    action_source value is never treated as Sentinel-authored."""
    return action_source == _SENTINEL_ACTION_SOURCE


def sentinel_non_concurrence_statement(
    action: str, action_source: Optional[str]
) -> Optional[str]:
    """The exact inert line "Sentinel does not concur at this time." only
    when Sentinel authored a WAIT (``action_source == "SENTINEL"`` and
    ``action == "WAIT"``); otherwise ``None``. The line carries no
    rejection, veto, execution-block, schedule, timer, notification, alert,
    future-BUY, or "check back" meaning (ADR-070 §7). A STRATEGY / None /
    unknown WAIT does not receive this wording."""
    if action_source == _SENTINEL_ACTION_SOURCE and action == _WAIT_ACTION:
        return SENTINEL_NON_CONCURRENCE_STATEMENT
    return None


def evidence_polarity_label(polarity: Optional[str]) -> str:
    """Per-record only. ``"SUPPORTING"`` -> "Supported the BUY";
    ``"CONTRADICTING"`` -> "Contradicted the BUY"; ``None`` / missing / any
    other value -> "Polarity unavailable" (ADR-070 §9). No count, majority,
    unanimity, net polarity, or score is derived from these anywhere."""
    if polarity == _SUPPORTING_POLARITY:
        return EVIDENCE_POLARITY_SUPPORTED_LABEL
    if polarity == _CONTRADICTING_POLARITY:
        return EVIDENCE_POLARITY_CONTRADICTED_LABEL
    return EVIDENCE_POLARITY_UNAVAILABLE_LABEL


@dataclass(frozen=True)
class EvidencePolarityRow:
    """One evidence record's identity/source plus its own polarity label --
    per record, never combined with any other record's. Same
    framework-independent, testable shape as EvidenceEntry / GovernanceEntry."""
    evidence_id: str
    source: str
    polarity_label: str


class ReadStatus(Enum):
    """Distinguishes a successful read (possibly empty) from a read that
    could not be completed. AVAILABLE-vs-EMPTY is never ambiguous here --
    an empty tuple already means that -- so this only needs two members,
    not a three-way split."""
    OK = "ok"
    ERROR = "error"


@dataclass(frozen=True)
class DecisionListArea:
    decisions: List[DecisionView]

    @property
    def is_empty(self) -> bool:
        return len(self.decisions) == 0

    @property
    def empty_state_message(self) -> Optional[str]:
        return "No decisions recorded yet." if self.is_empty else None


@dataclass(frozen=True)
class DecisionDetailArea:
    decision: Optional[DecisionView]
    decision_status: ReadStatus = ReadStatus.OK
    # Raw, opaque, unresolved pointer values from DecisionContract -- not
    # part of DecisionView (which deliberately excludes them). Displayed
    # verbatim in the detail header; never interpreted, resolved, or
    # validated here.
    evidence_reference: Optional[str] = None
    risk_reference: Optional[str] = None
    evidence: Tuple[EvidenceEntry, ...] = field(default=())
    evidence_status: ReadStatus = ReadStatus.OK
    governance: Tuple[GovernanceEntry, ...] = field(default=())
    governance_status: ReadStatus = ReadStatus.OK
    approvals: Tuple[ApprovalEntry, ...] = field(default=())
    approvals_status: ReadStatus = ReadStatus.OK
    audit_trail: Tuple[AuditEntry, ...] = field(default=())
    audit_trail_status: ReadStatus = ReadStatus.OK
    # Sprint 7 "Evidence Since Decision": typed as a bare forward-reference
    # string, not imported, so this UI component does not import from
    # applications.trading_intelligence.services (see ui/tests/
    # test_ui_structure.py's test_screen_components_do_not_import_services_
    # directly) -- the concrete NewsCacheSnapshotDiff type is passed through
    # unmodified by controller.py, which is allowed to call services/.
    news_cache_diff: Optional["NewsCacheSnapshotDiff"] = None
    news_cache_diff_status: ReadStatus = ReadStatus.OK
    # Sprint 7 "Recommendation Since Decision": same forward-reference-
    # string convention as news_cache_diff above, for the same reason --
    # RecommendationDiff lives in applications.trading_intelligence.services.
    recommendation_diff: Optional["RecommendationDiff"] = None
    recommendation_diff_status: ReadStatus = ReadStatus.OK
    # Sprint 7 "Earnings Proximity": same forward-reference-string
    # convention as the two fields above, kept consistent even though
    # EarningsSnapshot lives under adapters/ rather than services/.
    earnings_snapshot: Optional["EarningsSnapshot"] = None
    earnings_status: ReadStatus = ReadStatus.OK
    # Decision -> Outcome linkage: same forward-reference-string convention
    # as the three fields above, for the same reason -- DecisionOutcome
    # lives in applications.trading_intelligence.contracts.
    # decision_outcome_contract. `outcome` is the real, frozen Wave 2A
    # DecisionOutcome for this decision's own decision_id (verbatim, never
    # recomputed) when the read succeeded and a matching outcome exists;
    # None when the read succeeded but no outcome exists yet, or when no
    # outcome_source collaborator was injected (the Sentinel path's
    # existing 7-arg construction) -- an honest "not yet resolved" state,
    # never an error, in both cases.
    outcome: Optional["DecisionOutcome"] = None
    outcome_status: ReadStatus = ReadStatus.OK
    # Decision Quality Cross-Linking: same forward-reference-string
    # convention as the four fields above, for the same reason --
    # CalibrationBandContext lives in applications.trading_intelligence.
    # projections.calibration_band_context. `calibration_context` is the
    # real CalibrationBandContext (band + total_outcomes across all four
    # bands, both carried verbatim from services/
    # decision_calibration_query_service.py) for this decision's own
    # MODEL_ENSEMBLE.ensemble score, when the read succeeded and that score
    # falls inside a known band; None when the read succeeded but the score
    # is missing/out-of-range, or when no calibration_source collaborator
    # was injected -- an honest "no band to reference" state, never an
    # error, in both cases.
    calibration_context: Optional["CalibrationBandContext"] = None
    calibration_status: ReadStatus = ReadStatus.OK

    @property
    def is_empty(self) -> bool:
        return self.decision is None

    @property
    def confidence_display(self) -> Optional[str]:
        if self.decision is None:
            return None
        return f"{self.decision.confidence * 100:.0f}%"

    @property
    def status_display(self) -> Optional[str]:
        if self.decision is None:
            return None
        return self.decision.status.replace("_", " ").title()

    @property
    def timestamp_display(self) -> Optional[str]:
        if self.decision is None:
            return None
        return format_display_timestamp(self.decision.updated_at)

    @property
    def decision_created_display(self) -> Optional[str]:
        """Sprint 4 Item #3 -- the DECISION_CREATED entry's own recorded
        timestamp, taken from the already-loaded timeline (``audit_trail``)
        and formatted for display, or ``None`` when the timeline carries no
        such entry.

        Reads the existing ``AuditEntry.created_at`` verbatim: never the
        decision's ``updated_at`` (a different value with a different
        meaning), never fabricated, and never invented when the entry is
        absent. Whether that entry is a durable ledger event or a
        read-model-synthesised one is not asserted or changed here -- this
        only surfaces the timestamp it already carries. The first matching
        entry wins, so the result is deterministic for a given timeline."""
        if self.decision is None:
            return None
        for entry in self.audit_trail:
            if entry.event_type == _DECISION_CREATED_EVENT_TYPE:
                return format_display_timestamp(entry.created_at)
        return None

    # --- ADR-070 Batch 2: recommendation-surfacing presentation semantics ---

    @property
    def recommendation_provenance_display(self) -> Optional[str]:
        """"Sentinel recommendation" iff DecisionView.action_source is
        exactly "SENTINEL"; otherwise "interpreted strategy decision".
        None when no decision is selected."""
        if self.decision is None:
            return None
        return provenance_label(self.decision.action_source)

    @property
    def is_sentinel_recommendation(self) -> bool:
        """Whether Sentinel's B2 rule authored this decision's action.
        Purely a provenance read -- it confers no execution authority on
        the decision and is not derived from action/confidence/evidence."""
        return self.decision is not None and is_sentinel_recommendation(
            self.decision.action_source
        )

    @property
    def sentinel_non_concurrence_display(self) -> Optional[str]:
        """The exact inert line "Sentinel does not concur at this time."
        only for a Sentinel-authored WAIT; None otherwise (including a
        STRATEGY / None / unknown WAIT, and every non-WAIT action)."""
        if self.decision is None:
            return None
        return sentinel_non_concurrence_statement(
            self.decision.action, self.decision.action_source
        )

    @property
    def confidence_qualifier(self) -> Optional[str]:
        """The fixed semantic qualifier for the number confidence_display
        shows -- an uncalibrated ensemble model score, never a probability
        or a calibrated / recommendation confidence. The numeric value in
        confidence_display is unchanged and unre-computed."""
        if self.decision is None:
            return None
        return CONFIDENCE_QUALIFIER

    @property
    def evidence_polarity_rows(self) -> Tuple[EvidencePolarityRow, ...]:
        """One row per evidence record, in the order evidence was loaded,
        each carrying that record's own identity/source and its individual
        polarity label. No aggregate, count, majority, unanimity, net
        polarity, or score is produced here or anywhere downstream."""
        return tuple(
            EvidencePolarityRow(
                evidence_id=entry.evidence_id,
                source=entry.source,
                polarity_label=evidence_polarity_label(entry.polarity),
            )
            for entry in self.evidence
        )

    # --- Decision Quality Cross-Linking: calibration-band context ---------

    @property
    def calibration_band_label(self) -> Optional[str]:
        """This decision's own historical confidence band identity (e.g.
        "0.60-0.65"), or None when no calibration_context is available."""
        if self.calibration_context is None:
            return None
        return self.calibration_context.band.label

    @property
    def calibration_has_enough_data(self) -> Optional[bool]:
        """Whether the SAME conservative display floor Performance &
        Learning already applies (CALIBRATION_MIN_OUTCOMES, counted across
        ALL FOUR bands, not just this decision's own band) is met. None
        when no calibration_context is available -- there is nothing to
        gate yet, distinct from a real False."""
        if self.calibration_context is None:
            return None
        return self.calibration_context.total_outcomes >= CALIBRATION_MIN_OUTCOMES


@dataclass(frozen=True)
class DecisionCenterScreen:
    list_area: DecisionListArea
    detail_area: DecisionDetailArea
