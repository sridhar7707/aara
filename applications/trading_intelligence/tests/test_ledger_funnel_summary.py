"""Wave 3D: the derived Decision Ledger funnel summary + per-candidate
filter-state classification (ADR-064, no scope expansion).

Both are pure transforms of the already-materialized Wave 3B
``CandidateDecisionInspection`` -- no SQLite, no snapshot fetch, no
network, no trades.db / outcome / trade linkage. Fixtures run the real
Wave 3B pipeline (``build_candidate_decision_inspection`` over a
``LedgerInspection``) so the aggregation is exercised against the exact
objects the composition root will hand it.
"""
import dataclasses
import inspect as _inspect

import pytest

from applications.trading_intelligence.contracts.candidate_decision_contract import (
    CandidateEvaluationRecord,
    DecisionInspectionRecord,
    LedgerInspection,
)
from applications.trading_intelligence.contracts import (
    candidate_decision_inspection_contract as C,
)
from applications.trading_intelligence.services import candidate_decision_query_service as S
from applications.trading_intelligence.services.candidate_decision_query_service import (
    build_candidate_decision_inspection,
    build_ledger_funnel_summary,
)

_UNSET = object()


def _cand(cid, *, seq, asset="BLK", ts="2026-07-29T14:33:22+00:00",
          completed=1, data_available=1, required_models_available=0,
          evaluation_requested=1, screening_results=_UNSET):
    return CandidateEvaluationRecord(
        candidate_event_id=cid, timestamp=ts, asset=asset,
        screening_version="screen_universe_v1",
        screening_results=({"rank": 3, "composite_score": 0.62}
                           if screening_results is _UNSET else screening_results),
        data_available=bool(data_available),
        required_models_available=bool(required_models_available),
        evaluation_requested=bool(evaluation_requested),
        evaluation_completed=bool(completed),
        sequence_number=seq,
    )


def _dec(did, cid, *, seq, asset="BLK", ts="2026-07-30T13:48:41+00:00",
         action="REJECT", event_type="QUALIFIED_REJECTION",
         final_confidence=0.56, risk_checks=_UNSET):
    return DecisionInspectionRecord(
        decision_id=did, candidate_event_id=cid, timestamp=ts, asset=asset,
        action=action, event_type=event_type, final_confidence=final_confidence,
        model_outputs={"xgboost": {"signal": "BUY", "confidence": 0.57}},
        risk_checks=({"gate_trace": [{"gate": "volume", "passed": False,
                                      "detail": "volume ratio 0.04 < 0.3"}]}
                     if risk_checks is _UNSET else risk_checks),
        intent={"primary_intent": "NO_ACTION"},
        market_context={"regime": "BULL"},
        data_completeness={"status": "COMPLETE"},
        sequence_number=seq,
    )


def _summary(candidates=(), decisions=()):
    inspection = build_candidate_decision_inspection(
        LedgerInspection(
            candidates=tuple(candidates), decisions=tuple(decisions),
            snapshot_mtime=None, data_through="2026-09-01T19:00:53+00:00",
        )
    )
    return inspection, build_ledger_funnel_summary(inspection)


_REJECT_GATE = {"gate_trace": [{"gate": "volume", "passed": False, "detail": "d"}]}
_ENTRY_PASSED = {"gate_trace": [{"gate": "all_entry_gates", "passed": True,
                                 "detail": "all gates passed"}]}
_HOLD_RC = {"exit_reason": "no exit condition met"}


# --- 1. candidate counts -------------------------------------------------

def test_total_candidates_is_the_candidate_row_count_not_the_decision_count():
    decs = [_dec("D1", "C1", seq=10), _dec("D2", "C1", seq=11),
            _dec("D3", "C1", seq=12)]
    _, s = _summary([_cand("C1", seq=1), _cand("C2", seq=2)], decs)
    assert s.total_candidates == 2                 # candidate population
    assert s.decision_events_recorded == 3         # event population (distinct)
    assert s.candidates_with_decision == 1
    assert s.candidates_without_decision == 1


# --- 2. evaluation counts ----------------------------------------------

def test_evaluation_completed_and_incomplete_partition_the_candidates():
    _, s = _summary(
        [_cand("C1", seq=1, completed=1), _cand("C2", seq=2, completed=0),
         _cand("C3", seq=3, completed=0)],
        [],
    )
    assert s.evaluations_completed == 1
    assert s.evaluations_incomplete == 2
    assert s.evaluations_completed + s.evaluations_incomplete == s.total_candidates


# --- 3. decision counts ----------------------------------------------

def test_decision_events_recorded_counts_every_event_including_repeats():
    decs = [_dec(f"D{i}", "C1", seq=10 + i) for i in range(7)]
    _, s = _summary([_cand("C1", seq=1)], decs)
    assert s.decision_events_recorded == 7
    assert s.candidates_with_decision == 1        # still ONE candidate


# --- 4. BUY/SELL/HOLD/REJECT classification --------------------------

def test_action_counts_reconcile_to_the_decision_event_total():
    decs = [
        _dec("D1", "C1", seq=10, action="BUY", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
        _dec("D2", "C2", seq=20, action="SELL", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
        _dec("D3", "C3", seq=30, action="HOLD", event_type="QUALIFIED_REJECTION",
             risk_checks=_HOLD_RC),
        _dec("D4", "C4", seq=40, action="REJECT", risk_checks=_REJECT_GATE),
        _dec("D5", "C5", seq=50, action="REJECT", risk_checks=_REJECT_GATE),
    ]
    cands = [_cand(f"C{i}", seq=i) for i in range(1, 6)]
    _, s = _summary(cands, decs)
    assert (s.buy_count, s.sell_count, s.hold_count, s.reject_count) == (1, 1, 1, 2)
    assert s.other_action_count == 0
    assert (s.buy_count + s.sell_count + s.hold_count + s.reject_count
            + s.other_action_count) == s.decision_events_recorded


def test_executed_count_is_the_event_type_executed_subset():
    decs = [
        _dec("D1", "C1", seq=10, action="BUY", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
        _dec("D2", "C2", seq=20, action="SELL", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
        _dec("D3", "C3", seq=30, action="REJECT", risk_checks=_REJECT_GATE),
    ]
    _, s = _summary([_cand(f"C{i}", seq=i) for i in range(1, 4)], decs)
    assert s.executed_count == 2                  # 3 BUY/EXEC + 2 SELL/EXEC shape
    assert s.reject_count == 1


def test_unknown_action_lands_in_other_and_still_reconciles():
    decs = [_dec("D1", "C1", seq=10, action="DEFER", event_type="X")]
    _, s = _summary([_cand("C1", seq=1)], decs)
    assert s.other_action_count == 1
    assert (s.buy_count + s.sell_count + s.hold_count + s.reject_count
            + s.other_action_count) == s.decision_events_recorded == 1


# --- 5. candidate-with-decision vs candidate-without-decision --------

def test_candidate_with_and_without_decision_partition_the_candidates():
    _, s = _summary(
        [_cand("C1", seq=1), _cand("C2", seq=2), _cand("C3", seq=3)],
        [_dec("D1", "C1", seq=10)],
    )
    assert s.candidates_with_decision == 1
    assert s.candidates_without_decision == 2
    assert (s.candidates_with_decision
            + s.candidates_without_decision) == s.total_candidates


def test_per_candidate_filter_buckets_are_mutually_exclusive_and_total():
    decs = [
        _dec("D1", "C1", seq=10, action="BUY", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
        _dec("D2", "C2", seq=20, action="HOLD", event_type="QUALIFIED_REJECTION",
             risk_checks=_HOLD_RC),
        _dec("D3", "C3", seq=30, action="REJECT", risk_checks=_REJECT_GATE),
    ]
    cands = [_cand("C1", seq=1), _cand("C2", seq=2), _cand("C3", seq=3),
             _cand("C4", seq=4, completed=1),              # completed, no decision
             _cand("C5", seq=5, completed=0)]              # incomplete
    _, s = _summary(cands, decs)
    assert s.candidates_executed == 1
    assert s.candidates_hold == 1
    assert s.candidates_rejected == 1
    assert s.candidates_no_decision == 1
    assert s.candidates_incomplete == 1
    assert s.candidates_other == 0
    assert (s.candidates_executed + s.candidates_hold + s.candidates_rejected
            + s.candidates_no_decision + s.candidates_incomplete
            + s.candidates_other) == s.total_candidates


# --- 6. multiple decisions for one candidate ------------------------

def test_candidate_that_rejected_then_executed_is_bucketed_executed():
    decs = [
        _dec("D1", "C1", seq=10, action="REJECT", risk_checks=_REJECT_GATE),
        _dec("D2", "C1", seq=20, action="REJECT", risk_checks=_REJECT_GATE),
        _dec("D3", "C1", seq=99, action="BUY", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
    ]
    insp, s = _summary([_cand("C1", seq=1)], decs)
    assert C.candidate_filter_state(insp.candidates[0]) == C.FILTER_STATE_EXECUTED
    assert s.candidates_executed == 1
    assert s.candidates_rejected == 0
    # the recorded REJECT events are still counted as events
    assert s.reject_count == 2
    assert s.executed_count == 1


# --- 7. sequence_number semantics unchanged ------------------------

def test_summary_does_not_reorder_or_mutate_the_inspection():
    decs = [_dec("D3", "C1", seq=30), _dec("D1", "C1", seq=10),
            _dec("D2", "C1", seq=20)]
    insp, _ = _summary([_cand("C2", seq=5), _cand("C1", seq=2)], decs)
    before_candidates = [c.candidate_event_id for c in insp.candidates]
    before_decisions = [d.decision_id for d in insp.candidates[
        [c.candidate_event_id for c in insp.candidates].index("C1")].decisions]
    # a second summary call must not have changed anything
    build_ledger_funnel_summary(insp)
    after_candidates = [c.candidate_event_id for c in insp.candidates]
    c1 = insp.candidates[after_candidates.index("C1")]
    assert before_candidates == after_candidates == ["C1", "C2"]     # seq order
    assert before_decisions == [d.decision_id for d in c1.decisions] == [
        "D1", "D2", "D3"]                                            # seq order
    assert c1.latest_decision.decision_id == "D3"                    # unchanged


# --- 8. rejection gate aggregation --------------------------------

def test_rejection_reasons_aggregate_recorded_gates_sorted_by_count_desc():
    def rej(did, cid, seq, gate):
        return _dec(did, cid, seq=seq, action="REJECT",
                    risk_checks={"gate_trace": [{"gate": gate, "passed": False,
                                                 "detail": "d"}]})
    decs = [
        rej("D1", "C1", 10, "volume"), rej("D2", "C2", 20, "volume"),
        rej("D3", "C3", 30, "volume"), rej("D4", "C4", 40, "regime"),
        rej("D5", "C5", 50, "regime"), rej("D6", "C6", 60, "relative_strength"),
    ]
    cands = [_cand(f"C{i}", seq=i) for i in range(1, 7)]
    _, s = _summary(cands, decs)
    assert [(r.gate, r.count) for r in s.rejection_reasons] == [
        ("volume", 3), ("regime", 2), ("relative_strength", 1)]
    assert sum(r.count for r in s.rejection_reasons) == s.reject_count == 6


def test_rejection_reasons_ties_break_by_gate_name_ascending():
    def rej(did, cid, seq, gate):
        return _dec(did, cid, seq=seq, action="REJECT",
                    risk_checks={"gate_trace": [{"gate": gate, "passed": False,
                                                 "detail": "d"}]})
    decs = [rej("D1", "C1", 10, "regime"), rej("D2", "C2", 20, "volume")]
    _, s = _summary([_cand("C1", seq=1), _cand("C2", seq=2)], decs)
    assert [r.gate for r in s.rejection_reasons] == ["regime", "volume"]


def test_hold_and_executed_events_are_not_in_the_rejection_breakdown():
    decs = [
        _dec("D1", "C1", seq=10, action="HOLD", event_type="QUALIFIED_REJECTION",
             risk_checks=_HOLD_RC),
        _dec("D2", "C2", seq=20, action="BUY", event_type="EXECUTED",
             risk_checks=_ENTRY_PASSED),
    ]
    _, s = _summary([_cand("C1", seq=1), _cand("C2", seq=2)], decs)
    assert s.rejection_reasons == ()
    assert s.reject_count == 0


# --- 9. missing gate --------------------------------------------

def test_reject_with_empty_gate_trace_is_classified_gate_not_recorded():
    decs = [_dec("D1", "C1", seq=10, action="REJECT",
                 risk_checks={"gate_trace": []})]
    _, s = _summary([_cand("C1", seq=1)], decs)
    assert [(r.gate, r.count) for r in s.rejection_reasons] == [
        (C.GATE_NOT_RECORDED_LABEL, 1)]
    assert C.GATE_NOT_RECORDED_LABEL == "Gate not recorded"


# --- 10. malformed gate JSON ----------------------------------

def test_reject_with_wave3a_degraded_none_risk_checks_is_gate_not_recorded():
    # Wave 3A degrades malformed JSON to None; the funnel must not infer.
    decs = [_dec("D1", "C1", seq=10, action="REJECT", risk_checks=None),
            _dec("D2", "C2", seq=20, action="REJECT",
                 risk_checks={"gate_trace": [{"gate": "volume", "passed": False,
                                              "detail": "d"}]})]
    _, s = _summary([_cand("C1", seq=1), _cand("C2", seq=2)], decs)
    reasons = {r.gate: r.count for r in s.rejection_reasons}
    assert reasons == {"volume": 1, C.GATE_NOT_RECORDED_LABEL: 1}


# --- 17. no outcome fields introduced -----------------------

def test_funnel_contract_carries_no_outcome_or_trade_field():
    forbidden = {
        "realized_pnl", "pnl", "gross_return", "net_return", "holding_period",
        "holding_days", "outcome_direction", "direction", "exit_price",
        "trade_id", "order_id", "win", "loss", "calibration", "attribution",
        "decision_quality", "win_rate", "pct", "percent", "percentage",
    }
    for cls in (C.LedgerFunnelSummary, C.RejectionReasonCount):
        names = {f.name for f in dataclasses.fields(cls)}
        assert not (names & forbidden), f"{cls.__name__} has {names & forbidden}"


# --- 18. no trade linkage introduced -----------------------

def test_funnel_builder_never_references_trades_or_outcome_stores():
    src = _inspect.getsource(build_ledger_funnel_summary)
    for token in ("trades.db", "trade_id", "order_id", "decision_outcome_events",
                  "realized", "pnl", "holding_period", "JOIN"):
        assert token not in src
    # no clock invented, no percentage math
    assert "datetime" not in src and "time.time" not in src


def test_funnel_builder_and_classifier_are_pure_no_io():
    for obj in (build_ledger_funnel_summary, C.candidate_filter_state):
        body = _inspect.getsource(obj)
        for token in ("open(", "sqlite3", "hf_hub_download", "requests",
                      "urllib", "socket", "subprocess"):
            assert token not in body


# --- classifier direct coverage ---------------------------

def test_candidate_filter_state_incomplete_wins_even_over_a_recorded_decision():
    # The ledger trigger blocks this in production; the classifier is still
    # deterministic if it ever occurs -- an incomplete evaluation is INCOMPLETE.
    insp = build_candidate_decision_inspection(LedgerInspection(
        candidates=(_cand("C1", seq=1, completed=0),),
        decisions=(_dec("D1", "C1", seq=10, action="REJECT",
                        risk_checks=_REJECT_GATE),),
        snapshot_mtime=None, data_through=None,
    ))
    assert C.candidate_filter_state(insp.candidates[0]) == C.FILTER_STATE_INCOMPLETE


def test_candidate_filter_state_completed_no_decision_is_no_decision():
    insp = build_candidate_decision_inspection(LedgerInspection(
        candidates=(_cand("C1", seq=1, completed=1),), decisions=(),
        snapshot_mtime=None, data_through=None,
    ))
    assert C.candidate_filter_state(insp.candidates[0]) == C.FILTER_STATE_NO_DECISION


def test_empty_inspection_yields_a_zeroed_summary():
    _, s = _summary([], [])
    assert s.total_candidates == 0
    assert s.decision_events_recorded == 0
    assert s.rejection_reasons == ()
    assert s.executed_count == 0
