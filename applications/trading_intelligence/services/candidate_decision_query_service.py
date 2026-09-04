"""Query boundary for the Wave 3B Candidate -> Decision inspection read
model (ADR-064).

Pure and I/O-free. This module opens no database connection, fetches
nothing over a network, and imports nothing under ``bot/``, top-level
``ledger/``, ``scheduler/``, ``dashboard/``, ``database/``, or
``sentinel_engine/`` -- and no Gradio / UI module. It consumes only the
already-read Wave 3A :class:`LedgerInspection` and deterministically
groups it into the inspection semantics ADR-064 Section 2.7 defines.

The only permitted relationship (ADR-064 Section 2.5) is
``decision.candidate_event_id == candidate.candidate_event_id``. No
correlation by asset, date, timestamp, timestamp proximity, score, model
output, row position, sequence adjacency, or any other identifier or
store is performed. ``candidate_event_id`` / ``decision_id`` /
``sequence_number`` are carried verbatim; no identity is synthesised.

Health / freshness (ADR-061, ADR-064 Section 2.11 / 2.12): the service is
given the ``ReadResult`` the Wave 3A reader produced and threads its
health through verbatim -- a non-HEALTHY read yields a non-HEALTHY result
carrying the same reason (never turned into an empty result), and
``snapshot_mtime`` / ``data_through`` are passed through unchanged. This
module introduces no clock of its own.

Decision-time only (ADR-064 Section 2.8, Section 8): the results carry no
post-decision result, no quality / calibration / attribution figure, and
no trade or order linkage. The stable end-of-decision-time notice is
exposed as ``CandidateDecisionInspection.decision_time_boundary_notice``.
Wave 3B ends here: no controller, no Gradio view, no bootstrap wiring.
"""
from collections.abc import Mapping as _AbcMapping
from typing import Dict, List, Optional, Tuple

from applications.platform.integrations import ReadResult
from applications.trading_intelligence.contracts.candidate_decision_contract import (
    DecisionInspectionRecord,
    JsonField,
    LedgerInspection,
)
from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    COMPLETED_NO_DECISION_MESSAGE,
    CandidateDecisionInspection,
    CandidateInspectionResult,
    DecisionInspectionResult,
    EVALUATION_COMPLETED_LABEL,
    EVALUATION_NOT_COMPLETED_LABEL,
    FILTER_STATE_EXECUTED,
    FILTER_STATE_HOLD,
    FILTER_STATE_INCOMPLETE,
    FILTER_STATE_NO_DECISION,
    FILTER_STATE_OTHER,
    FILTER_STATE_REJECTED,
    GATE_NOT_RECORDED_LABEL,
    GateFinding,
    HOLD_EXIT_MESSAGE,
    LedgerFunnelSummary,
    NO_GATE_DETAIL_MESSAGE,
    NOT_COMPLETED_NO_DECISION_MESSAGE,
    RejectionReasonCount,
    candidate_filter_state,
)

_PROVIDER = "candidate_decision_inspection"

_ENTRY_GATES_MARKER = "all_entry_gates"
_REJECTION_ACTIONS = ("REJECT",)


def _extract_gate(risk_checks: JsonField) -> Tuple[Optional[GateFinding], bool]:
    """From the Wave 3A already-redacted ``risk_checks`` mapping, return
    ``(failing_gate, entry_gates_passed)``.

    * ``entry_gates_passed`` is ``True`` only when ``gate_trace`` carries the
      recorded ``all_entry_gates`` / ``passed=True`` marker (BUY / EXECUTED).
    * ``failing_gate`` is the single recorded ``passed`` is ``False`` entry,
      verbatim. Passed gates are never enumerated (ADR-064 Section 2.7).
    """
    if not isinstance(risk_checks, _AbcMapping):
        return None, False
    trace = risk_checks.get("gate_trace")
    if not isinstance(trace, list):
        return None, False
    for entry in trace:
        if (
            isinstance(entry, _AbcMapping)
            and entry.get("gate") == _ENTRY_GATES_MARKER
            and entry.get("passed") is True
        ):
            return None, True
    for entry in trace:
        if isinstance(entry, _AbcMapping) and entry.get("passed") is False:
            return (
                GateFinding(
                    gate=str(entry.get("gate", "")),
                    passed=False,
                    detail=str(entry.get("detail", "")),
                ),
                False,
            )
    return None, False


def _to_decision_result(rec: DecisionInspectionRecord) -> DecisionInspectionResult:
    gate_finding, entry_gates_passed = _extract_gate(rec.risk_checks)
    hold_message = HOLD_EXIT_MESSAGE if rec.action == "HOLD" else None
    missing_gate_detail = None
    if (
        rec.action in _REJECTION_ACTIONS
        and gate_finding is None
        and not entry_gates_passed
    ):
        missing_gate_detail = NO_GATE_DETAIL_MESSAGE
    return DecisionInspectionResult(
        decision_id=rec.decision_id,
        candidate_event_id=rec.candidate_event_id,
        timestamp=rec.timestamp,
        asset=rec.asset,
        action=rec.action,
        event_type=rec.event_type,
        final_confidence=rec.final_confidence,
        model_outputs=rec.model_outputs,
        risk_checks=rec.risk_checks,
        intent=rec.intent,
        market_context=rec.market_context,
        data_completeness=rec.data_completeness,
        sequence_number=rec.sequence_number,
        hold_message=hold_message,
        entry_gates_passed=entry_gates_passed,
        gate_finding=gate_finding,
        missing_gate_detail_message=missing_gate_detail,
    )


def build_candidate_decision_inspection(
    inspection: LedgerInspection,
) -> CandidateDecisionInspection:
    """Pure transform: group the Wave 3A records into ADR-064 Section 2.7
    inspection semantics. No I/O, no source-record mutation."""
    decision_results = [_to_decision_result(d) for d in inspection.decisions]

    by_cid: Dict[str, List[DecisionInspectionResult]] = {}
    for d in decision_results:
        by_cid.setdefault(d.candidate_event_id, []).append(d)

    candidate_cids = {c.candidate_event_id for c in inspection.candidates}

    out_candidates = []
    for c in sorted(
        inspection.candidates,
        key=lambda cand: (cand.sequence_number, cand.candidate_event_id),
    ):
        decs = tuple(
            sorted(
                by_cid.get(c.candidate_event_id, []),
                key=lambda d: (d.sequence_number, d.decision_id),
            )
        )
        if not c.evaluation_completed:
            status_label = EVALUATION_NOT_COMPLETED_LABEL
        else:
            status_label = EVALUATION_COMPLETED_LABEL
        if decs:
            terminal_message = None
        elif c.evaluation_completed:
            terminal_message = COMPLETED_NO_DECISION_MESSAGE
        else:
            terminal_message = NOT_COMPLETED_NO_DECISION_MESSAGE
        out_candidates.append(
            CandidateInspectionResult(
                candidate_event_id=c.candidate_event_id,
                timestamp=c.timestamp,
                asset=c.asset,
                screening_version=c.screening_version,
                screening_results=c.screening_results,
                data_available=c.data_available,
                required_models_available=c.required_models_available,
                evaluation_requested=c.evaluation_requested,
                evaluation_completed=c.evaluation_completed,
                sequence_number=c.sequence_number,
                decisions=decs,
                evaluation_status_label=status_label,
                terminal_state_message=terminal_message,
            )
        )

    unmatched = tuple(
        sorted(
            (d for d in decision_results if d.candidate_event_id not in candidate_cids),
            key=lambda d: (d.sequence_number, d.decision_id),
        )
    )

    return CandidateDecisionInspection(
        candidates=tuple(out_candidates),
        unmatched_decisions=unmatched,
        snapshot_mtime=inspection.snapshot_mtime,
        data_through=inspection.data_through,
    )


_EXECUTED_EVENT_TYPE = "EXECUTED"
_ACTION_BUY = "BUY"
_ACTION_SELL = "SELL"
_ACTION_HOLD = "HOLD"
_ACTION_REJECT = "REJECT"

_FILTER_BUCKET_ORDER = (
    FILTER_STATE_EXECUTED,
    FILTER_STATE_HOLD,
    FILTER_STATE_REJECTED,
    FILTER_STATE_NO_DECISION,
    FILTER_STATE_INCOMPLETE,
    FILTER_STATE_OTHER,
)


def build_ledger_funnel_summary(
    inspection: CandidateDecisionInspection,
) -> LedgerFunnelSummary:
    """Pure count-only aggregation of an already-grouped inspection.

    No I/O, no mutation of ``inspection``, no clock, no ratio / percentage /
    causal claim, no outcome or trade field. Rejection reasons come only
    from the Wave 3B ``GateFinding`` already extracted from the recorded
    ``risk_checks`` gate trace -- an absent finding is reported honestly as
    :data:`GATE_NOT_RECORDED_LABEL`, never inferred.
    """
    candidates = inspection.candidates

    all_events: List[DecisionInspectionResult] = [
        d for c in candidates for d in c.decisions
    ]
    all_events.extend(inspection.unmatched_decisions)

    def _action_total(action: str) -> int:
        return sum(1 for d in all_events if d.action == action)

    buy = _action_total(_ACTION_BUY)
    sell = _action_total(_ACTION_SELL)
    hold = _action_total(_ACTION_HOLD)
    reject = _action_total(_ACTION_REJECT)
    other_action = len(all_events) - buy - sell - hold - reject
    executed = sum(1 for d in all_events if d.event_type == _EXECUTED_EVENT_TYPE)

    completed = sum(1 for c in candidates if c.evaluation_completed)
    with_decision = sum(1 for c in candidates if c.decisions)

    buckets: Dict[str, int] = {name: 0 for name in _FILTER_BUCKET_ORDER}
    for c in candidates:
        buckets[candidate_filter_state(c)] += 1

    gate_counts: Dict[str, int] = {}
    for d in all_events:
        if d.action != _ACTION_REJECT:
            continue
        finding = d.gate_finding
        gate = finding.gate if (finding is not None and finding.gate) else GATE_NOT_RECORDED_LABEL
        gate_counts[gate] = gate_counts.get(gate, 0) + 1
    rejection_reasons = tuple(
        RejectionReasonCount(gate=gate, count=count)
        for gate, count in sorted(
            gate_counts.items(), key=lambda item: (-item[1], item[0])
        )
    )

    total = len(candidates)
    return LedgerFunnelSummary(
        total_candidates=total,
        evaluations_completed=completed,
        evaluations_incomplete=total - completed,
        candidates_with_decision=with_decision,
        candidates_without_decision=total - with_decision,
        decision_events_recorded=len(all_events),
        buy_count=buy,
        sell_count=sell,
        hold_count=hold,
        reject_count=reject,
        other_action_count=other_action,
        executed_count=executed,
        candidates_executed=buckets[FILTER_STATE_EXECUTED],
        candidates_hold=buckets[FILTER_STATE_HOLD],
        candidates_rejected=buckets[FILTER_STATE_REJECTED],
        candidates_no_decision=buckets[FILTER_STATE_NO_DECISION],
        candidates_incomplete=buckets[FILTER_STATE_INCOMPLETE],
        candidates_other=buckets[FILTER_STATE_OTHER],
        rejection_reasons=rejection_reasons,
    )


class CandidateDecisionQueryService:
    """Health-aware, I/O-free query boundary.

    :meth:`inspect` takes the ADR-061 ``ReadResult`` the Wave 3A reader
    produced. A non-HEALTHY read is returned unchanged (same reason); a
    HEALTHY read is grouped by :func:`build_candidate_decision_inspection`.
    An empty snapshot stays a HEALTHY, empty result -- never fabricated.
    """

    def inspect(
        self, source_result: "ReadResult[LedgerInspection]"
    ) -> "ReadResult[CandidateDecisionInspection]":
        if not source_result.is_healthy:
            return ReadResult.failed(source_result.health)
        inspection = source_result.value
        if inspection is None:
            return ReadResult.healthy(
                CandidateDecisionInspection((), (), None, None), _PROVIDER
            )
        return ReadResult.healthy(
            build_candidate_decision_inspection(inspection), _PROVIDER
        )
