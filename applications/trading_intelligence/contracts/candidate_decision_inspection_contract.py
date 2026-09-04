"""Frozen result contracts for the Wave 3B Candidate -> Decision inspection
query layer (ADR-064).

Framework-independent, stdlib-only: no bot, dashboard, scheduler,
database, ledger, sentinel_engine, sentinel, sqlite3, huggingface, or
Gradio import. These types are what
``services/candidate_decision_query_service.py`` returns from the
already-read Wave 3A :class:`LedgerInspection`; nothing here reads a
database or performs any I/O.

Scope: decision-time inspection only (ADR-064 Section 2.8, Section 8).
Results carry the Wave 3A candidate-evaluation and decision facts
verbatim, grouped by the one permitted relationship
(``candidate_event_id`` equality), plus the small set of exact semantic
strings ADR-064 Section 2.7 mandates. Nothing is reinterpreted as a
``sentinel_engine`` / domain / governance contract, and no post-decision
result -- P&L, return, holding period, direction, exit price, quality,
calibration, attribution, or any trade / order linkage -- is modelled,
computed, or attached anywhere in this layer.

Identity (ADR-064 Section 2.6): ``candidate_event_id`` and ``decision_id``
(the ADR-059 canonical production decision identity) and
``sequence_number`` are carried verbatim. No replacement identity is
synthesised.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from applications.trading_intelligence.contracts.candidate_decision_contract import (
    JsonField,
)

# --- Wave 3D: derived funnel-summary + filter-state vocabulary ---------
#
# Both are a pure re-view of columns ADR-064 already authorises
# (evaluation_completed, decision action / event_type, and the Wave 3B
# recorded gate finding). No new table, no new source, no outcome / trade
# field, no scope expansion.

GATE_NOT_RECORDED_LABEL = "Gate not recorded"

# The mutually-exclusive per-candidate bucket the Decision Ledger
# Inspection filter offers. Exactly one applies to any candidate.
FILTER_STATE_EXECUTED = "executed"
FILTER_STATE_HOLD = "hold"
FILTER_STATE_REJECTED = "rejected"
FILTER_STATE_NO_DECISION = "no-decision"
FILTER_STATE_INCOMPLETE = "incomplete"
FILTER_STATE_OTHER = "other"

# --- exact semantic strings (ADR-064 Section 2.7 / Section 8) ----------

EVALUATION_NOT_COMPLETED_LABEL = "Evaluation Not Completed"
EVALUATION_COMPLETED_LABEL = "Evaluation completed"
COMPLETED_NO_DECISION_MESSAGE = "Evaluation completed — no decision event recorded"
NOT_COMPLETED_NO_DECISION_MESSAGE = "Evaluation Not Completed — no decision recorded"
HOLD_EXIT_MESSAGE = "Position evaluated for exit — no exit condition met."
ENTRY_GATES_PASSED_MESSAGE = "All entry gates passed."
NO_GATE_DETAIL_MESSAGE = "No gate detail recorded."
DECISION_TIME_BOUNDARY_NOTICE = (
    "END OF DECISION-TIME EVIDENCE — trade/outcome recorded separately, "
    "not linked by any deterministic key."
)


@dataclass(frozen=True)
class GateFinding:
    """The one recorded failing gate for a REJECT / QUALIFIED_REJECTION,
    taken verbatim from ``risk_checks.gate_trace`` (ADR-064 Section 2.7).

    Only the single recorded failing entry is surfaced -- the query layer
    never synthesises a list of gates that passed. ``passed`` is the
    recorded boolean (``False`` for a failing gate)."""

    gate: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class DecisionInspectionResult:
    """One ``decision_events`` row, Wave 3A facts verbatim plus the exact
    ADR-064 Section 2.7 semantic presentation for its ``action``.

    ``candidate_event_id`` is the sole link back to a
    :class:`CandidateInspectionResult`. The JSON fields are the Wave 3A
    already-parsed, already-redacted mappings (or ``None`` when Wave 3A
    degraded a malformed value to "not recorded"); this layer does not
    re-parse or re-redact them.
    """

    decision_id: str
    candidate_event_id: str
    timestamp: str
    asset: str
    action: str
    event_type: str
    final_confidence: Optional[float]
    model_outputs: JsonField
    risk_checks: JsonField
    intent: JsonField
    market_context: JsonField
    data_completeness: JsonField
    sequence_number: int
    # ADR-064 Section 2.7 derived presentation -- verbatim recorded facts only:
    hold_message: Optional[str]                 # HOLD_EXIT_MESSAGE when action == HOLD
    entry_gates_passed: bool                    # BUY/EXECUTED "all_entry_gates" marker
    gate_finding: Optional[GateFinding]         # the one recorded failing gate (REJECT)
    missing_gate_detail_message: Optional[str]  # NO_GATE_DETAIL_MESSAGE when a REJECT has no gate detail


@dataclass(frozen=True)
class CandidateInspectionResult:
    """One ``candidate_evaluation_events`` row with every matching decision
    grouped beneath it by ``candidate_event_id`` equality only.

    A candidate with zero decisions is still present (ADR-064 Section 2.7).
    Multiple decisions are never collapsed; ``decisions`` is ordered by
    ``sequence_number`` ascending.
    """

    candidate_event_id: str
    timestamp: str
    asset: str
    screening_version: str
    screening_results: JsonField
    data_available: bool
    required_models_available: bool
    evaluation_requested: bool
    evaluation_completed: bool
    sequence_number: int
    decisions: Tuple[DecisionInspectionResult, ...]
    # ADR-064 Section 2.7 derived candidate semantics:
    evaluation_status_label: str               # EVALUATION_NOT_COMPLETED_LABEL / EVALUATION_COMPLETED_LABEL
    terminal_state_message: Optional[str]      # the exact "no decision" string, or None when decisions exist

    @property
    def has_decisions(self) -> bool:
        return len(self.decisions) > 0

    @property
    def latest_decision(self) -> Optional[DecisionInspectionResult]:
        """The highest-``sequence_number`` decision for this candidate, or
        ``None``. "Latest" is positional only -- it never implies a later
        decision is more correct (ADR-064 Section 2.7)."""
        return self.decisions[-1] if self.decisions else None


@dataclass(frozen=True)
class CandidateDecisionInspection:
    """The full grouped inspection result.

    ``unmatched_decisions`` holds any decision whose ``candidate_event_id``
    matched no candidate row. The Trust Ledger FK plus the
    completed-evaluation trigger make this empty in practice; it exists so
    a structurally short snapshot never causes a decision to be silently
    dropped or heuristically re-homed.

    Freshness is passed through from Wave 3A verbatim -- not recomputed.
    """

    candidates: Tuple[CandidateInspectionResult, ...]
    unmatched_decisions: Tuple[DecisionInspectionResult, ...]
    snapshot_mtime: Optional[datetime]
    data_through: Optional[str]
    decision_time_boundary_notice: str = field(default=DECISION_TIME_BOUNDARY_NOTICE)

    @property
    def is_empty(self) -> bool:
        """True when the read was HEALTHY but held no candidate rows
        (ADR-064 Section 2.11 "HEALTHY + empty")."""
        return len(self.candidates) == 0

    @property
    def decision_count(self) -> int:
        return sum(len(c.decisions) for c in self.candidates) + len(self.unmatched_decisions)


# --- Wave 3D: per-candidate filter classification --------------------


def candidate_filter_state(candidate: "CandidateInspectionResult") -> str:
    """The single mutually-exclusive bucket this candidate belongs to for
    the Decision Ledger Inspection filter.

    Deterministic, order-independent, and derived only from
    already-authorised fields:

    * ``INCOMPLETE`` -- ``evaluation_completed`` is False (the ledger's own
      completed-evaluation trigger makes this and a recorded decision
      mutually exclusive in production; classified first so the state stays
      unambiguous even if that ever changes).
    * ``NO_DECISION`` -- evaluation completed but no ``decision_events`` row.
    * ``EXECUTED`` -- at least one recorded decision with
      ``event_type == "EXECUTED"`` (a candidate that was rejected earlier
      and later executed surfaces here -- it ultimately traded).
    * ``HOLD`` / ``REJECTED`` -- otherwise, keyed on a recorded ``HOLD`` /
      ``REJECT`` action.
    * ``OTHER`` -- a recorded decision whose action is none of the above.
    """
    if not candidate.evaluation_completed:
        return FILTER_STATE_INCOMPLETE
    if not candidate.decisions:
        return FILTER_STATE_NO_DECISION
    if any(d.event_type == "EXECUTED" for d in candidate.decisions):
        return FILTER_STATE_EXECUTED
    actions = {d.action for d in candidate.decisions}
    if "HOLD" in actions:
        return FILTER_STATE_HOLD
    if "REJECT" in actions:
        return FILTER_STATE_REJECTED
    return FILTER_STATE_OTHER


# --- Wave 3D: derived funnel summary --------------------------------


@dataclass(frozen=True)
class RejectionReasonCount:
    """One recorded blocking gate and how many ``REJECT`` decision events
    cited it. ``gate`` is the gate name recorded verbatim in
    ``risk_checks.gate_trace`` (via the Wave 3B ``GateFinding``), or
    :data:`GATE_NOT_RECORDED_LABEL` when the recorded trace carried no
    usable blocking gate. No gate is inferred and no prose is parsed."""

    gate: str
    count: int


@dataclass(frozen=True)
class LedgerFunnelSummary:
    """Factual aggregation of one :class:`CandidateDecisionInspection`.

    Three distinct populations are kept separate and never conflated:

    * candidate population -- ``total_candidates`` and the
      ``evaluations_* `` / ``candidates_* `` counts partition it.
    * decision-event population -- ``decision_events_recorded`` (a candidate
      may have several); the ``*_count`` action tallies partition it.
    * ``executed_count`` -- the ``event_type == "EXECUTED"`` subset of the
      decision-event population, spanning BUY and SELL.

    Every field is a count. No percentage, ratio, rate, causal claim,
    outcome, P&L, holding period, or trade linkage is modelled here.
    """

    # candidate population
    total_candidates: int
    evaluations_completed: int
    evaluations_incomplete: int
    candidates_with_decision: int
    candidates_without_decision: int
    # decision-event population
    decision_events_recorded: int
    buy_count: int
    sell_count: int
    hold_count: int
    reject_count: int
    other_action_count: int
    # event_type == EXECUTED subset of the decision-event population
    executed_count: int
    # mutually-exclusive per-candidate filter buckets (sum == total_candidates)
    candidates_executed: int
    candidates_hold: int
    candidates_rejected: int
    candidates_no_decision: int
    candidates_incomplete: int
    candidates_other: int
    # recorded blocking gate -> count over REJECT events only, sorted by
    # count desc then gate name asc; () when reject_count == 0
    rejection_reasons: Tuple[RejectionReasonCount, ...]
