"""Wave 3C: rendering tests for the Decision Ledger Inspection section
inside Performance & Learning (ADR-064).

The section is rendered once from an already-materialized Wave 3B
``CandidateDecisionInspection`` on the ``PerformanceLearningScreen``. No
provider call, no ``demo.load``, no Refresh in the view. Fixtures build
the Wave 3B contract objects directly -- no SQLite, no snapshot fetch, no
Wave 3A/3B service call from the test.
"""
import gradio as gr
import pytest

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    CandidateDecisionInspection,
    CandidateInspectionResult,
    DecisionInspectionResult,
    GateFinding,
)
from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    DECISION_LEDGER_INSPECTION_TITLE,
)


def _html_blob(screen) -> str:
    demo = PerformanceLearningUI(screen=screen).build()
    return "\n".join(
        b.value for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
    )


def _decision(**over):
    base = dict(
        decision_id="DEC-1", candidate_event_id="CAND-1",
        timestamp="2026-07-30T13:48:41+00:00", asset="BLK",
        action="REJECT", event_type="QUALIFIED_REJECTION", final_confidence=0.56,
        model_outputs={"xgboost": {"signal": "BUY", "confidence": 0.57},
                       "lstm": {"signal": "BUY", "confidence": 0.61},
                       "finbert": {"signal": "HOLD", "confidence": 0.5}},
        risk_checks={"gate_trace": [{"gate": "volume", "passed": False,
                                     "detail": "volume ratio 0.04 < 0.3"}]},
        intent={"primary_intent": "NO_ACTION"},
        market_context={"regime": "HIGH_VOLATILITY",
                        "decision_timestamp": "2026-07-30T13:48:41+00:00"},
        data_completeness={"status": "DEGRADED", "missing_inputs": [],
                           "stale_inputs": ["lstm"]},
        sequence_number=10, hold_message=None, entry_gates_passed=False,
        gate_finding=GateFinding(gate="volume", passed=False,
                                 detail="volume ratio 0.04 < 0.3"),
        missing_gate_detail_message=None,
    )
    base.update(over)
    return DecisionInspectionResult(**base)


def _candidate(**over):
    base = dict(
        candidate_event_id="CAND-1", timestamp="2026-07-29T14:33:22+00:00",
        asset="BLK", screening_version="screen_universe_v1",
        screening_results={"rank": 3, "composite_score": 0.62, "sector": "Financials"},
        data_available=True, required_models_available=False,
        evaluation_requested=True, evaluation_completed=True,
        sequence_number=1, decisions=(),
        evaluation_status_label="Evaluation completed", terminal_state_message=None,
    )
    base.update(over)
    return CandidateInspectionResult(**base)


def _inspection(candidates=(), *, mtime=None, data_through="2026-09-01T19:00:53+00:00"):
    import datetime as _dt
    return CandidateDecisionInspection(
        candidates=tuple(candidates), unmatched_decisions=(),
        snapshot_mtime=mtime or _dt.datetime(2026, 9, 1, 19, 0, 0,
                                             tzinfo=_dt.timezone.utc),
        data_through=data_through,
    )


def _screen(*, ledger_health=IntegrationHealth.healthy("trust_ledger_inspection"),
            ledger_inspection=None):
    from dataclasses import replace
    return replace(build_mock_screen(),
                   ledger_health=ledger_health, ledger_inspection=ledger_inspection)


# --- section presence / placement ---------------------------------

def test_section_label_is_present_and_after_the_two_unavailable_areas():
    blob = _html_blob(_screen(ledger_inspection=_inspection([_candidate()])))
    assert DECISION_LEDGER_INSPECTION_TITLE in blob
    assert blob.index("Attribution Breakdown") < blob.index(DECISION_LEDGER_INSPECTION_TITLE)
    assert blob.index("Model Confidence Calibration") < blob.index(DECISION_LEDGER_INSPECTION_TITLE)


def test_outcome_history_attribution_calibration_are_untouched():
    blob = _html_blob(_screen(ledger_inspection=_inspection([_candidate()])))
    assert "Outcome History" in blob
    assert "No Sentinel-side attribution contract is wired yet" in blob
    assert "No Sentinel-side model-calibration contract is wired yet" in blob


# --- health tri-state -------------------------------------------

def test_healthy_with_data_renders_candidate_content():
    blob = _html_blob(_screen(ledger_inspection=_inspection([_candidate()])))
    assert "CAND-1" in blob
    assert "BLK" in blob


def test_healthy_empty_renders_the_honest_empty_state_not_unavailable():
    blob = _html_blob(_screen(ledger_inspection=_inspection([])))
    assert "No decision ledger records available." in blob
    assert "Data unavailable" not in blob


def test_unavailable_renders_the_source_reason_not_empty():
    blob = _html_blob(_screen(
        ledger_health=IntegrationHealth.unavailable(
            "trust_ledger_inspection", detail="snapshot not present"),
        ledger_inspection=None))
    assert "Data unavailable" in blob
    assert "No decision ledger records available." not in blob


def test_no_health_standalone_build_renders_fixed_fallback():
    blob = _html_blob(_screen(ledger_health=None, ledger_inspection=None))
    assert "not available in this environment" in blob
    assert "Illustrative" not in blob


# --- freshness -------------------------------------------------

def test_freshness_is_rendered_from_supplied_values_only():
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate()], data_through="2026-08-31T00:00:00+00:00")))
    assert "2026-08-31T00:00:00+00:00" in blob        # data_through verbatim
    assert "2026-09-01" in blob                       # snapshot_mtime formatted
    # the view never generates a "now" timestamp
    import inspect
    from applications.trading_intelligence.ui.performance_learning import gradio_view
    src = inspect.getsource(gradio_view)
    for token in ("datetime.now", "utcnow", "time.time", "fetched_at", "rendered_at"):
        assert token not in src


def test_no_refresh_or_demoload_in_the_view():
    import inspect
    build_src = inspect.getsource(PerformanceLearningUI.build)
    assert ".load(" not in build_src        # no demo.load(...) call
    assert ".click(" not in build_src       # no event handler wiring
    assert "gr.Button" not in build_src     # no Refresh button
    assert "interactive=True" not in build_src


# --- candidate semantics --------------------------------------

def test_candidate_without_decision_remains_visible_with_exact_message():
    completed = _candidate(candidate_event_id="C-done", evaluation_completed=True,
                           decisions=(), terminal_state_message=(
                               "Evaluation completed — no decision event recorded"))
    incomplete = _candidate(candidate_event_id="C-inc", evaluation_completed=False,
                            evaluation_status_label="Evaluation Not Completed",
                            decisions=(), terminal_state_message=(
                                "Evaluation Not Completed — no decision recorded"))
    blob = _html_blob(_screen(ledger_inspection=_inspection([completed, incomplete])))
    assert "C-done" in blob and "C-inc" in blob
    assert "Evaluation completed — no decision event recorded" in blob
    assert "Evaluation Not Completed — no decision recorded" in blob
    assert "Evaluation Not Completed" in blob


def test_four_evaluation_booleans_are_all_shown():
    blob = _html_blob(_screen(ledger_inspection=_inspection([
        _candidate(data_available=True, required_models_available=False,
                   evaluation_requested=True, evaluation_completed=False,
                   evaluation_status_label="Evaluation Not Completed")])))
    for name in ("data_available", "required_models_available",
                 "evaluation_requested", "evaluation_completed"):
        assert name in blob


def test_candidate_state_never_uses_forbidden_verdict_words():
    blob = _html_blob(_screen(ledger_inspection=_inspection([
        _candidate(evaluation_completed=False,
                   evaluation_status_label="Evaluation Not Completed",
                   terminal_state_message="Evaluation Not Completed — no decision recorded")])))
    lowered = blob.lower()
    for banned in (">rejected<", "declined", "no-trade", "skipped", "failed screening"):
        assert banned not in lowered


# --- decision semantics -------------------------------------

def test_hold_wording_is_exact_and_no_gate_finding_shown():
    d = _decision(decision_id="DEC-hold", action="HOLD",
                  event_type="QUALIFIED_REJECTION",
                  risk_checks={"exit_reason": "no exit condition met"},
                  gate_finding=None, hold_message=(
                      "Position evaluated for exit — no exit condition met."))
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d,))])))
    assert "Position evaluated for exit — no exit condition met." in blob
    assert "no-buy" not in blob.lower()
    assert "Gate</span>" not in blob  # no gate KV rendered for HOLD


def test_reject_shows_recorded_gate_and_detail_verbatim():
    d = _decision(decision_id="DEC-rej", action="REJECT",
                  gate_finding=GateFinding(gate="relative_strength", passed=False,
                                           detail="RS weak (-0.4% vs SPY +0.6%)"),
                  risk_checks={"gate_trace": [{"gate": "relative_strength",
                                               "passed": False,
                                               "detail": "RS weak (-0.4% vs SPY +0.6%)"}]})
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d,))])))
    assert "relative_strength" in blob
    assert "RS weak (-0.4% vs SPY +0.6%)" in blob


def test_reject_missing_gate_detail_shows_exact_fallback():
    d = _decision(decision_id="DEC-nog", action="REJECT", gate_finding=None,
                  missing_gate_detail_message="No gate detail recorded.",
                  risk_checks={"gate_trace": []})
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d,))])))
    assert "No gate detail recorded." in blob


def test_executed_marker_does_not_enumerate_synthetic_gates():
    d = _decision(decision_id="DEC-exec", action="BUY", event_type="EXECUTED",
                  gate_finding=None, entry_gates_passed=True,
                  missing_gate_detail_message=None,
                  risk_checks={"gate_trace": [{"gate": "all_entry_gates",
                                               "passed": True,
                                               "detail": "all gates passed"}]})
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d,))])))
    assert "Entry gates passed" in blob
    for g in ("volume", "regime", "relative_strength", "earnings_proximity"):
        assert g not in blob  # no synthetic per-gate list


# --- multiple decisions -----------------------------------

def test_all_decisions_render_and_latest_is_default_expanded():
    d1 = _decision(decision_id="DEC-a", sequence_number=10)
    d2 = _decision(decision_id="DEC-b", sequence_number=20)
    d3 = _decision(decision_id="DEC-c", sequence_number=30, action="HOLD",
                   risk_checks={"exit_reason": "no exit condition met"},
                   gate_finding=None,
                   hold_message="Position evaluated for exit — no exit condition met.")
    cand = _candidate(decisions=(d1, d2, d3))
    blob = _html_blob(_screen(ledger_inspection=_inspection([cand])))
    for did in ("DEC-a", "DEC-b", "DEC-c"):
        assert did in blob
    # the latest (highest sequence_number) <details> carries `open`
    latest_pos = blob.index("DEC-c")
    open_details = [i for i in range(len(blob)) if blob.startswith("<details", i)
                    and "open" in blob[i:i + 40]]
    assert any(blob.index("DEC-c") - 200 < i < blob.index("DEC-c") for i in open_details) \
        or "<details class=\"pl-dli-decision\" open>" in blob[max(0, latest_pos - 400):latest_pos + 10]
    # exactly one `open` details in this single-candidate render
    assert blob.count('<details class="pl-dli-decision" open>') == 1


def test_decision_ordering_is_preserved_from_the_contract():
    d1 = _decision(decision_id="DEC-a", sequence_number=10)
    d2 = _decision(decision_id="DEC-b", sequence_number=20)
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d1, d2))])))
    assert blob.index("DEC-a") < blob.index("DEC-b")


# --- JSON restrictions --------------------------------------

def test_excluded_nested_fields_are_never_rendered_even_if_present():
    d = _decision(
        model_outputs={"xgboost": {"signal": "BUY", "confidence": 0.57,
                                   "metadata": {"shap_drivers": ["SECRET_SHAP"]}}},
        risk_checks={"gate_trace": [{"gate": "volume", "passed": False,
                                     "detail": "x"}],
                     "fill_price": 456.93, "fill_shares": 17.4, "notional": 7970.1},
        intent={"primary_intent": "OPPORTUNITY_ENTRY", "thesis": "t",
                "expected_return_basis_points": 2052},
        market_context={"regime": "BULL", "macro_score": 0.61},
    )
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d,))])))
    for leaked in ("SECRET_SHAP", "metadata", "456.93", "7970.1",
                   "expected_return_basis_points", "2052", "macro_score", "0.61"):
        assert leaked not in blob


def test_final_confidence_is_shown_as_recorded_not_as_a_probability():
    blob = _html_blob(_screen(ledger_inspection=_inspection([
        _candidate(decisions=(_decision(final_confidence=0.5646),))])))
    assert "Recorded confidence" in blob
    assert "0.56" in blob
    for banned in ("probability of profit", "win probability", "calibrated probability"):
        assert banned not in blob.lower()


# --- outcome boundary + absolute ban --------------------

def test_end_of_decision_time_boundary_notice_is_rendered_exactly():
    blob = _html_blob(_screen(ledger_inspection=_inspection([_candidate()])))
    assert ("END OF DECISION-TIME EVIDENCE — trade/outcome recorded separately, "
            "not linked by any deterministic key.") in blob


def test_no_outcome_or_trade_tokens_anywhere_in_the_section():
    d1 = _decision(decision_id="DEC-a", action="BUY", event_type="EXECUTED",
                   entry_gates_passed=True, gate_finding=None,
                   risk_checks={"gate_trace": [{"gate": "all_entry_gates",
                                                "passed": True, "detail": "x"}]})
    blob = _html_blob(_screen(ledger_inspection=_inspection(
        [_candidate(decisions=(d1,))]))).lower()
    for banned in ("realized_pnl", "p&l", "holding period", "holding_days",
                   "exit price", "trade_id", "order_id", ">win<", ">loss<",
                   "realized return", "outcome quality", "decision quality"):
        assert banned not in blob


# --- escaping ---------------------------------------------

def test_ledger_free_text_is_html_escaped():
    payload = '<script>alert(1)</script>'
    d = _decision(
        decision_id=payload, asset=payload,
        gate_finding=GateFinding(gate=payload, passed=False, detail=payload),
        risk_checks={"gate_trace": [{"gate": payload, "passed": False,
                                     "detail": payload}]},
        intent={"primary_intent": payload, "thesis": payload,
                "invalidation_point": payload},
        market_context={"regime": payload},
    )
    cand = _candidate(candidate_event_id=payload, asset=payload,
                      screening_version=payload,
                      screening_results={"note": payload}, decisions=(d,))
    blob = _html_blob(_screen(ledger_inspection=_inspection([cand])))
    assert "<script>alert(1)</script>" not in blob
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in blob


# --- structure: view stays contract-only ----------------

def test_view_imports_no_source_service_or_protected_package():
    import ast
    import inspect
    from applications.trading_intelligence.ui.performance_learning import gradio_view
    tree = ast.parse(inspect.getsource(gradio_view))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    for name in imported:
        assert not name.startswith((
            "bot", "ledger", "scheduler", "dashboard", "database", "sentinel_engine",
        ))
        # no data-access modules pulled into the view
        assert "trust_ledger_snapshot" not in name
        assert "trust_ledger_inspection_source" not in name
        assert "candidate_decision_query_service" not in name
    for io_token in ("sqlite3", "hf_hub_download", "requests", "urllib"):
        assert io_token not in inspect.getsource(gradio_view)
