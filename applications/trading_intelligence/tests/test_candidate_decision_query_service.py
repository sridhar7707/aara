"""Tests for
applications.trading_intelligence.services.candidate_decision_query_service.

The service is a pure, I/O-free transform of the Wave 3A
``LedgerInspection`` into the ADR-064 Section 2.7 Candidate -> Decision
inspection semantics. Fixtures are built as ``LedgerInspection`` objects
directly -- no SQLite, no snapshot fetch.

Covered: exact ``candidate_event_id`` grouping (and adversarial
non-association by asset / date / timestamp), multiple-decision
preservation + ``sequence_number`` ordering, the exact candidate and
decision semantic strings, JSON-field passthrough (no re-parse / no
re-redact / no excluded field), the decision-time boundary, ADR-061
health tri-state passthrough, freshness passthrough, and import isolation.
"""
import dataclasses
import inspect as _inspect
import os
from datetime import datetime, timezone

import pytest

from applications.platform.integrations import (
    IntegrationHealth,
    IntegrationStatus,
    ReadResult,
)
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
    CandidateDecisionQueryService,
    build_candidate_decision_inspection,
)

_MTIME = datetime(2026, 9, 1, 19, 0, 0, tzinfo=timezone.utc)
_UNSET = object()  # distinguishes "argument not given" from an explicit None


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
         final_confidence=0.56, model_outputs=_UNSET, risk_checks=_UNSET,
         intent=_UNSET, market_context=_UNSET, data_completeness=_UNSET):
    return DecisionInspectionRecord(
        decision_id=did, candidate_event_id=cid, timestamp=ts, asset=asset,
        action=action, event_type=event_type, final_confidence=final_confidence,
        model_outputs=({
            "xgboost": {"signal": "BUY", "confidence": 0.57},
            "lstm": {"signal": "BUY", "confidence": 0.61},
            "finbert": {"signal": "HOLD", "confidence": 0.5},
        } if model_outputs is _UNSET else model_outputs),
        risk_checks=({"gate_trace": [{"gate": "volume", "passed": False,
                                      "detail": "volume ratio 0.04 < 0.3"}]}
                     if risk_checks is _UNSET else risk_checks),
        intent=({"primary_intent": "NO_ACTION"} if intent is _UNSET else intent),
        market_context=({"regime": "HIGH_VOLATILITY"}
                        if market_context is _UNSET else market_context),
        data_completeness=({"status": "DEGRADED", "missing_inputs": [],
                            "stale_inputs": ["lstm"]}
                           if data_completeness is _UNSET else data_completeness),
        sequence_number=seq,
    )


def _inspection(candidates=(), decisions=(), data_through="2026-09-01T19:00:53+00:00"):
    return LedgerInspection(
        candidates=tuple(candidates), decisions=tuple(decisions),
        snapshot_mtime=_MTIME, data_through=data_through,
    )


def _build(candidates=(), decisions=(), **kw):
    return build_candidate_decision_inspection(_inspection(candidates, decisions, **kw))


# --- identity / grouping --------------------------------------------

def test_single_decision_groups_under_its_candidate_by_candidate_event_id():
    out = _build([_cand("C1", seq=1)], [_dec("DEC-1", "C1", seq=10)])
    assert len(out.candidates) == 1
    assert out.candidates[0].candidate_event_id == "C1"
    assert [d.decision_id for d in out.candidates[0].decisions] == ["DEC-1"]
    assert out.unmatched_decisions == ()


def test_candidate_with_zero_decisions_remains_visible():
    out = _build([_cand("C1", seq=1), _cand("C2", seq=2)], [_dec("DEC-1", "C1", seq=10)])
    by_cid = {c.candidate_event_id: c for c in out.candidates}
    assert set(by_cid) == {"C1", "C2"}
    assert by_cid["C2"].decisions == ()
    assert by_cid["C2"].has_decisions is False


def test_multiple_decisions_are_all_preserved_and_ordered_by_sequence_number():
    decs = [
        _dec("DEC-3", "C1", seq=30, action="HOLD"),
        _dec("DEC-1", "C1", seq=10),
        _dec("DEC-2", "C1", seq=20),
    ]
    out = _build([_cand("C1", seq=1)], decs)
    got = out.candidates[0].decisions
    assert [d.decision_id for d in got] == ["DEC-1", "DEC-2", "DEC-3"]
    assert [d.sequence_number for d in got] == [10, 20, 30]
    assert len(got) == 3  # never collapsed


def test_latest_decision_is_the_highest_sequence_number():
    decs = [_dec("DEC-1", "C1", seq=10), _dec("DEC-2", "C1", seq=99),
            _dec("DEC-3", "C1", seq=50)]
    out = _build([_cand("C1", seq=1)], decs)
    latest = out.candidates[0].latest_decision
    assert latest.decision_id == "DEC-2"
    assert latest.sequence_number == 99


def test_candidates_are_ordered_by_sequence_number():
    out = _build([_cand("C2", seq=5), _cand("C1", seq=2), _cand("C3", seq=9)], [])
    assert [c.candidate_event_id for c in out.candidates] == ["C1", "C2", "C3"]
    assert [c.sequence_number for c in out.candidates] == [2, 5, 9]


def test_ids_and_sequence_numbers_are_verbatim_never_synthesized():
    out = _build([_cand("CAND-abc", seq=7)],
                 [_dec("DEC-xyz", "CAND-abc", seq=42)])
    c = out.candidates[0]
    d = c.decisions[0]
    assert c.candidate_event_id == "CAND-abc" and c.sequence_number == 7
    assert d.decision_id == "DEC-xyz" and d.candidate_event_id == "CAND-abc"
    assert d.sequence_number == 42


# --- adversarial: no heuristic lineage -----------------------------

def test_same_asset_different_candidate_ids_stay_separate():
    out = _build(
        [_cand("C1", seq=1, asset="AAPL"), _cand("C2", seq=2, asset="AAPL")],
        [_dec("DEC-1", "C1", seq=10, asset="AAPL")],
    )
    by_cid = {c.candidate_event_id: c for c in out.candidates}
    assert [d.decision_id for d in by_cid["C1"].decisions] == ["DEC-1"]
    assert by_cid["C2"].decisions == ()


def test_same_asset_and_same_date_different_candidate_ids_do_not_associate():
    day = "2026-08-17T13:51:33+00:00"
    out = _build(
        [_cand("C1", seq=1, asset="MMM", ts=day)],
        [_dec("DEC-1", "C2", seq=10, asset="MMM", ts=day)],
    )
    assert out.candidates[0].decisions == ()          # C1 gets nothing
    assert [d.decision_id for d in out.unmatched_decisions] == ["DEC-1"]  # C2 has no candidate


def test_decision_asset_differs_from_candidate_asset_but_id_matches_still_associates():
    out = _build([_cand("C1", seq=1, asset="AAA")],
                 [_dec("DEC-1", "C1", seq=10, asset="ZZZ")])
    got = out.candidates[0].decisions
    assert [d.decision_id for d in got] == ["DEC-1"]
    assert got[0].asset == "ZZZ"                       # asset carried verbatim, not "corrected"


def test_matching_timestamps_different_candidate_ids_do_not_associate():
    ts = "2026-07-30T13:48:41+00:00"
    out = _build([_cand("C1", seq=1, ts=ts)],
                 [_dec("DEC-1", "C2", seq=10, ts=ts)])
    assert out.candidates[0].decisions == ()
    assert [d.decision_id for d in out.unmatched_decisions] == ["DEC-1"]


def test_no_join_helpers_reference_asset_date_or_other_stores():
    src = _inspect.getsource(S)
    assert "JOIN" not in src.upper()
    for token in ("trades.db", "screener_log", "signal_log", "trade_id",
                  "order_id", "decision_outcome_events"):
        assert token not in src


# --- candidate semantics -----------------------------------------

def test_evaluation_not_completed_label():
    out = _build([_cand("C1", seq=1, completed=0)], [])
    assert out.candidates[0].evaluation_status_label == "Evaluation Not Completed"


def test_completed_candidate_with_no_decision_message():
    out = _build([_cand("C1", seq=1, completed=1)], [])
    assert out.candidates[0].terminal_state_message == (
        "Evaluation completed — no decision event recorded")


def test_not_completed_candidate_with_no_decision_message():
    out = _build([_cand("C1", seq=1, completed=0)], [])
    assert out.candidates[0].terminal_state_message == (
        "Evaluation Not Completed — no decision recorded")


def test_candidate_with_decisions_has_no_terminal_message():
    out = _build([_cand("C1", seq=1, completed=1)], [_dec("DEC-1", "C1", seq=10)])
    assert out.candidates[0].terminal_state_message is None


def test_four_evaluation_booleans_preserved_verbatim():
    out = _build([_cand("C1", seq=1, completed=0, data_available=0,
                        required_models_available=0, evaluation_requested=1)], [])
    c = out.candidates[0]
    assert c.data_available is False
    assert c.required_models_available is False
    assert c.evaluation_requested is True
    assert c.evaluation_completed is False


def test_candidate_status_never_uses_forbidden_words():
    out = _build([_cand("C1", seq=1, completed=0)], [])
    c = out.candidates[0]
    blob = " ".join(str(x) for x in (c.evaluation_status_label,
                                     c.terminal_state_message)).lower()
    for banned in ("rejected", "declined", "failed", "no-trade", "held", "skipped"):
        assert banned not in blob


# --- decision semantics ----------------------------------------

def test_hold_is_exactly_the_exit_evaluation_wording():
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, action="HOLD",
                       risk_checks={"exit_reason": "no exit condition met"})])
    d = out.candidates[0].decisions[0]
    assert d.hold_message == "Position evaluated for exit — no exit condition met."
    assert d.gate_finding is None
    assert d.missing_gate_detail_message is None      # HOLD is not a rejection


def test_reject_exposes_the_recorded_failing_gate_verbatim():
    rc = {"gate_trace": [{"gate": "relative_strength", "passed": False,
                          "detail": "RS weak (-0.4% vs SPY +0.6%)"}]}
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, action="REJECT", risk_checks=rc)])
    gf = out.candidates[0].decisions[0].gate_finding
    assert gf.gate == "relative_strength"
    assert gf.passed is False
    assert gf.detail == "RS weak (-0.4% vs SPY +0.6%)"
    # no synthesized passed-gate list anywhere on the result
    assert not hasattr(out.candidates[0].decisions[0], "passed_gates")


def test_reject_with_no_gate_trace_uses_the_exact_fallback():
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, action="REJECT",
                       risk_checks={"gate_trace": []})])
    d = out.candidates[0].decisions[0]
    assert d.gate_finding is None
    assert d.missing_gate_detail_message == "No gate detail recorded."


def test_reject_with_missing_risk_checks_uses_the_exact_fallback():
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, action="REJECT", risk_checks=None)])
    assert out.candidates[0].decisions[0].missing_gate_detail_message == (
        "No gate detail recorded.")


def test_executed_buy_marks_entry_gates_passed_without_enumerating():
    rc = {"gate_trace": [{"gate": "all_entry_gates", "passed": True,
                          "detail": "all gates passed"}]}
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, action="BUY", event_type="EXECUTED",
                       risk_checks=rc)])
    d = out.candidates[0].decisions[0]
    assert d.entry_gates_passed is True
    assert d.gate_finding is None
    assert d.missing_gate_detail_message is None


def test_executed_facts_are_preserved_and_no_trade_data_attached():
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, action="BUY", event_type="EXECUTED",
                       final_confidence=0.59,
                       intent={"primary_intent": "OPPORTUNITY_ENTRY",
                               "thesis": "AMD ...", "invalidation_point": "..."})])
    d = out.candidates[0].decisions[0]
    assert d.event_type == "EXECUTED"
    assert d.final_confidence == pytest.approx(0.59)
    assert d.intent["thesis"] == "AMD ..."
    field_names = {f.name for f in dataclasses.fields(d)}
    assert not (field_names & {"trade_id", "order_id", "fill_price", "realized_pnl"})


# --- JSON boundary --------------------------------------------

def test_json_fields_pass_through_unchanged_no_reparse_or_reredact():
    mo = {"xgboost": {"signal": "BUY", "confidence": 0.57}}
    rc = {"gate_trace": [{"gate": "volume", "passed": False, "detail": "x"}]}
    it = {"primary_intent": "NO_ACTION"}
    mc = {"regime": "BULL"}
    dc = {"status": "COMPLETE", "missing_inputs": [], "stale_inputs": []}
    out = _build([_cand("C1", seq=1)],
                 [_dec("DEC-1", "C1", seq=10, model_outputs=mo, risk_checks=rc,
                       intent=it, market_context=mc, data_completeness=dc)])
    d = out.candidates[0].decisions[0]
    assert d.model_outputs is mo
    assert d.risk_checks is rc
    assert d.intent is it
    assert d.market_context is mc
    assert d.data_completeness is dc


def test_wave3a_degraded_none_field_stays_none():
    out = _build([_cand("C1", seq=1, screening_results=None)],
                 [_dec("DEC-1", "C1", seq=10, risk_checks=None, model_outputs=None,
                       intent=None, market_context=None, data_completeness=None)])
    c = out.candidates[0]
    d = c.decisions[0]
    assert c.screening_results is None
    assert (d.risk_checks, d.model_outputs, d.intent, d.market_context,
            d.data_completeness) == (None, None, None, None, None)


def test_service_never_introduces_excluded_nested_fields():
    src = _inspect.getsource(S)
    for excluded in ("fill_price", "fill_shares", "notional",
                     "expected_return_basis_points", "macro_score", "metadata"):
        assert excluded not in src


# --- outcome / decision-time boundary -------------------------

def test_result_contracts_carry_no_outcome_or_trade_field():
    forbidden = {
        "realized_pnl", "pnl", "gross_return", "net_return", "holding_period",
        "holding_days", "outcome_direction", "direction", "exit_price",
        "trade_id", "order_id", "win", "loss", "calibration", "attribution",
        "decision_quality",
    }
    for cls in (C.GateFinding, C.DecisionInspectionResult,
                C.CandidateInspectionResult, C.CandidateDecisionInspection):
        names = {f.name for f in dataclasses.fields(cls)}
        assert not (names & forbidden), f"{cls.__name__} has {names & forbidden}"


def test_decision_time_boundary_notice_is_the_exact_constant():
    expected = ("END OF DECISION-TIME EVIDENCE — trade/outcome recorded "
                "separately, not linked by any deterministic key.")
    assert C.DECISION_TIME_BOUNDARY_NOTICE == expected
    out = _build([_cand("C1", seq=1)], [])
    assert out.decision_time_boundary_notice == expected


# --- health / freshness passthrough -------------------------

def _svc_inspect(read_result):
    return CandidateDecisionQueryService().inspect(read_result)


def test_healthy_with_data_produces_a_healthy_inspection_result():
    src = ReadResult.healthy(
        _inspection([_cand("C1", seq=1)], [_dec("DEC-1", "C1", seq=10)]),
        "trust_ledger_inspection")
    out = _svc_inspect(src)
    assert out.is_healthy
    assert isinstance(out.value, C.CandidateDecisionInspection)
    assert out.value.is_empty is False
    assert out.value.decision_count == 1


def test_healthy_empty_stays_a_valid_empty_result_not_unavailable():
    src = ReadResult.healthy(_inspection([], []), "trust_ledger_inspection")
    out = _svc_inspect(src)
    assert out.is_healthy
    assert out.value.candidates == ()
    assert out.value.unmatched_decisions == ()
    assert out.value.is_empty is True


def test_unavailable_is_passed_through_with_the_source_reason():
    health = IntegrationHealth.unavailable(
        "trust_ledger_inspection", detail="trust ledger snapshot is not present")
    out = _svc_inspect(ReadResult.failed(health))
    assert out.value is None
    assert out.health.status is IntegrationStatus.UNAVAILABLE
    assert out.health is health  # verbatim, not turned into empty


def test_api_error_reason_is_preserved():
    health = IntegrationHealth.api_error("trust_ledger_inspection", detail="ValueError")
    out = _svc_inspect(ReadResult.failed(health))
    assert out.value is None
    assert out.health.status is IntegrationStatus.API_ERROR
    assert out.health.detail == "ValueError"


def test_freshness_is_passed_through_never_recomputed():
    src = ReadResult.healthy(
        _inspection([_cand("C1", seq=1)], [], data_through="2026-08-31T00:00:00+00:00"),
        "trust_ledger_inspection")
    out = _svc_inspect(src).value
    assert out.snapshot_mtime == _MTIME
    assert out.data_through == "2026-08-31T00:00:00+00:00"
    # the service module invents no clock
    body = _inspect.getsource(S)
    for token in ("fetched_at", "rendered_at", "datetime.now", "utcnow", "time.time"):
        assert token not in body


# --- import isolation ---------------------------------------

def test_service_and_contract_import_no_protected_or_ui_package():
    import ast
    forbidden = {"bot", "ledger", "scheduler", "dashboard", "database",
                 "sentinel_engine", "sentinel", "gradio", "sqlite3",
                 "huggingface_hub"}
    for module in (S, C):
        tree = ast.parse(_inspect.getsource(module))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for dotted in names:
                assert dotted.split(".")[0] not in forbidden, (
                    f"{module.__name__} imports {dotted!r}")


def test_service_does_no_io():
    body = _inspect.getsource(S)
    for token in ("open(", "sqlite3", "hf_hub_download", "requests",
                  "urllib", "socket", "subprocess", ".read_inspection("):
        assert token not in body


# --- opt-in production regression (read-only, via Wave 3A reader) ---

_PROD = os.environ.get("AARA_WAVE3A_LEDGER_SNAPSHOT")


@pytest.mark.skipif(
    not _PROD, reason="set AARA_WAVE3A_LEDGER_SNAPSHOT to a real trust_ledger.db")
def test_production_snapshot_grouping_uses_candidate_event_id_only():
    from applications.trading_intelligence.adapters.trust_ledger_inspection_source import (
        TrustLedgerInspectionReader,
    )

    read_result = TrustLedgerInspectionReader(db_path=_PROD).read_inspection()
    out = CandidateDecisionQueryService().inspect(read_result)
    assert out.is_healthy
    insp = out.value

    assert len(insp.candidates) == 202
    assert insp.decision_count == 135
    assert insp.unmatched_decisions == ()          # FK holds: no orphan decisions

    # grouping is candidate_event_id equality only
    for c in insp.candidates:
        for d in c.decisions:
            assert d.candidate_event_id == c.candidate_event_id

    # candidates with no decision remain visible
    no_decision = [c for c in insp.candidates if not c.has_decisions]
    assert len(no_decision) >= 1
    for c in no_decision:
        assert c.terminal_state_message in (
            "Evaluation completed — no decision event recorded",
            "Evaluation Not Completed — no decision recorded",
        )

    # multiple decisions, where present, remain separate and ordered
    multi = [c for c in insp.candidates if len(c.decisions) > 1]
    for c in multi:
        seqs = [d.sequence_number for d in c.decisions]
        assert seqs == sorted(seqs)
        assert len(set(d.decision_id for d in c.decisions)) == len(c.decisions)

    # no outcome leakage on any result record
    for cls_obj in [insp] + list(insp.candidates) + [
        d for c in insp.candidates for d in c.decisions
    ]:
        names = {f.name for f in dataclasses.fields(cls_obj)}
        assert not (names & {"realized_pnl", "pnl", "trade_id", "order_id",
                             "holding_period", "outcome_direction", "exit_price"})

    # freshness passthrough
    assert insp.data_through is not None
