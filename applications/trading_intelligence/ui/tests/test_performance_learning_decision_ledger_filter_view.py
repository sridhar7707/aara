"""Wave 3D: Decision Ledger Inspection funnel panel + decision-state
filter rendering (ADR-064, no scope expansion).

The section is still rendered once from an already-materialized Wave 3B
``CandidateDecisionInspection`` plus the derived
``LedgerFunnelSummary``, both attached to the
``PerformanceLearningScreen``. No provider call, no ``demo.load``, no
Refresh, no event handler -- the filter is pure HTML radio + CSS.
"""
import inspect

import gradio as gr

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    CandidateDecisionInspection,
    CandidateInspectionResult,
    DecisionInspectionResult,
    GateFinding,
)
from applications.trading_intelligence.services.candidate_decision_query_service import (
    build_ledger_funnel_summary,
)
from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen


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
        model_outputs={"xgboost": {"signal": "BUY", "confidence": 0.57}},
        risk_checks={"gate_trace": [{"gate": "volume", "passed": False,
                                     "detail": "d"}]},
        intent={"primary_intent": "NO_ACTION"},
        market_context={"regime": "BULL"},
        data_completeness={"status": "COMPLETE"},
        sequence_number=10, hold_message=None, entry_gates_passed=False,
        gate_finding=GateFinding(gate="volume", passed=False, detail="d"),
        missing_gate_detail_message=None,
    )
    base.update(over)
    return DecisionInspectionResult(**base)


def _candidate(**over):
    base = dict(
        candidate_event_id="CAND-1", timestamp="2026-07-29T14:33:22+00:00",
        asset="BLK", screening_version="screen_universe_v1",
        screening_results={"rank": 3, "composite_score": 0.62},
        data_available=True, required_models_available=False,
        evaluation_requested=True, evaluation_completed=True,
        sequence_number=1, decisions=(),
        evaluation_status_label="Evaluation completed", terminal_state_message=None,
    )
    base.update(over)
    return CandidateInspectionResult(**base)


def _executed_candidate(cid, seq):
    d = _decision(decision_id=f"{cid}-D", candidate_event_id=cid, action="BUY",
                  event_type="EXECUTED", entry_gates_passed=True, gate_finding=None,
                  risk_checks={"gate_trace": [{"gate": "all_entry_gates",
                                               "passed": True, "detail": "x"}]})
    return _candidate(candidate_event_id=cid, sequence_number=seq, decisions=(d,))


def _rejected_candidate(cid, seq, gate="volume"):
    d = _decision(decision_id=f"{cid}-D", candidate_event_id=cid, action="REJECT",
                  gate_finding=GateFinding(gate=gate, passed=False, detail="d"),
                  risk_checks={"gate_trace": [{"gate": gate, "passed": False,
                                               "detail": "d"}]})
    return _candidate(candidate_event_id=cid, sequence_number=seq, decisions=(d,),
                      terminal_state_message=None)


def _hold_candidate(cid, seq):
    d = _decision(decision_id=f"{cid}-D", candidate_event_id=cid, action="HOLD",
                  gate_finding=None,
                  hold_message="Position evaluated for exit — no exit condition met.",
                  risk_checks={"exit_reason": "no exit condition met"})
    return _candidate(candidate_event_id=cid, sequence_number=seq, decisions=(d,))


def _no_decision_candidate(cid, seq):
    return _candidate(candidate_event_id=cid, sequence_number=seq, decisions=(),
                      evaluation_completed=True,
                      terminal_state_message="Evaluation completed — no decision event recorded")


def _incomplete_candidate(cid, seq):
    return _candidate(candidate_event_id=cid, sequence_number=seq, decisions=(),
                      evaluation_completed=False,
                      evaluation_status_label="Evaluation Not Completed",
                      terminal_state_message="Evaluation Not Completed — no decision recorded")


def _inspection(candidates):
    import datetime as _dt
    return CandidateDecisionInspection(
        candidates=tuple(candidates), unmatched_decisions=(),
        snapshot_mtime=_dt.datetime(2026, 9, 1, 19, 0, 0, tzinfo=_dt.timezone.utc),
        data_through="2026-09-01T19:00:53+00:00",
    )


def _screen(candidates):
    from dataclasses import replace
    insp = _inspection(candidates)
    return replace(
        build_mock_screen(),
        ledger_health=IntegrationHealth.healthy("trust_ledger_inspection"),
        ledger_inspection=insp,
        ledger_funnel_summary=build_ledger_funnel_summary(insp),
    )


def _mixed_population():
    return [
        _rejected_candidate("C-r1", 1, gate="volume"),
        _rejected_candidate("C-r2", 2, gate="volume"),
        _rejected_candidate("C-r3", 3, gate="regime"),
        _hold_candidate("C-h1", 4),
        _no_decision_candidate("C-nd1", 5),
        _incomplete_candidate("C-inc1", 6),
        _executed_candidate("C-x1", 7),
    ]


# --- funnel panel -------------------------------------------------------

def test_funnel_panel_states_the_three_populations_distinctly():
    blob = _html_blob(_screen(_mixed_population()))
    assert "7 candidates screened" in blob
    assert "6 evaluations completed" in blob        # C-inc1 incomplete
    assert "5 decisions recorded" in blob           # r1 r2 r3 h1 x1
    # candidates-with-decision population is named separately from the
    # decision-event count and the candidate count
    assert "from 5 of 7 candidates" in blob


def test_funnel_panel_shows_executed_held_rejected_and_the_action_line():
    blob = _html_blob(_screen(_mixed_population()))
    assert "1 executed" in blob
    assert "1 held" in blob
    assert "3 rejected" in blob
    assert "BUY 1" in blob and "SELL 0" in blob and "HOLD 1" in blob and "REJECT 3" in blob


def test_funnel_rejection_breakdown_lists_recorded_gates_by_count_no_percentages():
    blob = _html_blob(_screen(_mixed_population()))
    assert "volume" in blob and "regime" in blob
    # counts, never percentages / ratios / causal narrative
    assert "%" not in blob.split("pl-dli-boundary")[0].split("pl-dli-funnel")[-1]
    for banned in ("because", "caused by", "due to", "likely", "probably"):
        assert banned not in blob.lower()


def test_funnel_rejection_breakdown_is_absent_when_nothing_was_rejected():
    blob = _html_blob(_screen([_executed_candidate("C-x1", 1),
                               _hold_candidate("C-h1", 2)]))
    assert "pl-dli-funnel" in blob                  # panel still renders
    assert "pl-dli-funnel-why" not in blob          # but no rejection block


def test_gate_not_recorded_is_shown_honestly_never_invented():
    d = _decision(decision_id="C-r0-D", candidate_event_id="C-r0", action="REJECT",
                  gate_finding=None, missing_gate_detail_message="No gate detail recorded.",
                  risk_checks={"gate_trace": []})
    cand = _candidate(candidate_event_id="C-r0", sequence_number=1, decisions=(d,))
    blob = _html_blob(_screen([cand]))
    assert "Gate not recorded" in blob


# --- filter control ---------------------------------------------------

def test_filter_offers_all_six_states_with_all_selected_by_default():
    blob = _html_blob(_screen(_mixed_population()))
    assert 'class="pl-dli-filter"' in blob
    for token in ('data-filter="all"', 'data-filter="executed"', 'data-filter="hold"',
                  'data-filter="rejected"', 'data-filter="no-decision"',
                  'data-filter="incomplete"'):
        assert token in blob
    # "All" radio is the one pre-checked (reversible default)
    assert 'id="pl-dli-filter-all"' in blob
    all_input = blob.split('id="pl-dli-filter-all"')[1].split(">")[0]
    assert "checked" in all_input
    for other in ("executed", "hold", "rejected", "no-decision", "incomplete"):
        seg = blob.split(f'id="pl-dli-filter-{other}"')[1].split(">")[0]
        assert "checked" not in seg


def test_filter_labels_carry_the_candidate_bucket_counts():
    blob = _html_blob(_screen(_mixed_population()))
    # 7 all · 1 executed · 1 hold · 3 rejected · 1 no-decision · 1 incomplete
    assert ">All" in blob
    # counts appear next to their labels
    import re
    def _count_for(state):
        m = re.search(rf'for="pl-dli-filter-{state}"[^>]*>(.*?)</label>', blob, re.S)
        assert m, state
        return m.group(1)
    assert "7" in _count_for("all")
    assert "1" in _count_for("executed")
    assert "1" in _count_for("hold")
    assert "3" in _count_for("rejected")
    assert "1" in _count_for("no-decision")
    assert "1" in _count_for("incomplete")


def test_filter_is_pure_css_no_handler_added_to_build():
    build_src = inspect.getsource(PerformanceLearningUI.build)
    assert ".load(" not in build_src
    assert ".click(" not in build_src
    assert ".change(" not in build_src
    assert "gr.Button" not in build_src
    assert "gr.Radio" not in build_src
    assert "interactive=True" not in build_src


def test_filter_css_rules_present_in_the_composed_stylesheet():
    demo = PerformanceLearningUI(screen=_screen(_mixed_population())).build()
    css = demo.css or ""
    assert ".pl-dli-filter" in css
    # a specific-filter selection hides non-matching candidate cards
    assert "#pl-dli-filter-executed:checked" in css
    assert ".pl-dli-candidate--executed" in css


# --- per-card state class + prioritization -------------------------

def test_every_candidate_card_carries_its_filter_state_class():
    blob = _html_blob(_screen(_mixed_population()))
    for state in ("executed", "hold", "rejected", "no-decision", "incomplete"):
        assert f"pl-dli-candidate--{state}" in blob


def test_executed_candidates_render_before_non_executed_by_default():
    # C-x1 has the highest sequence_number (7) yet must float to the top.
    blob = _html_blob(_screen(_mixed_population()))
    exec_pos = blob.index("C-x1")
    for other in ("C-r1", "C-r2", "C-r3", "C-h1", "C-nd1", "C-inc1"):
        assert exec_pos < blob.index(other), other


def test_prioritization_preserves_sequence_order_within_each_group():
    cands = [_rejected_candidate("C-r1", 1), _executed_candidate("C-x2", 2),
             _rejected_candidate("C-r3", 3), _executed_candidate("C-x4", 4)]
    blob = _html_blob(_screen(cands))
    # executed group first, each group still in ascending sequence order
    assert blob.index("C-x2") < blob.index("C-x4") < blob.index("C-r1") < blob.index("C-r3")


def test_decision_ordering_inside_a_candidate_is_untouched():
    d1 = _decision(decision_id="DEC-a", candidate_event_id="C1", sequence_number=10)
    d2 = _decision(decision_id="DEC-b", candidate_event_id="C1", sequence_number=20)
    cand = _candidate(candidate_event_id="C1", decisions=(d1, d2))
    blob = _html_blob(_screen([cand]))
    assert blob.index("DEC-a") < blob.index("DEC-b")


# --- existing Wave 3C guarantees still hold -----------------------

def test_boundary_notice_and_no_outcome_tokens_survive_the_new_panel():
    blob = _html_blob(_screen(_mixed_population()))
    assert ("END OF DECISION-TIME EVIDENCE — trade/outcome recorded separately, "
            "not linked by any deterministic key.") in blob
    lowered = blob.lower()
    for banned in ("realized_pnl", "p&l", "holding period", "holding_days",
                   "exit price", "trade_id", "order_id", ">win<", ">loss<",
                   "win rate", "probability of profit"):
        assert banned not in lowered


def test_funnel_and_filter_absent_in_empty_and_unavailable_states():
    from dataclasses import replace
    empty = replace(build_mock_screen(),
                    ledger_health=IntegrationHealth.healthy("trust_ledger_inspection"),
                    ledger_inspection=CandidateDecisionInspection((), (), None, None),
                    ledger_funnel_summary=build_ledger_funnel_summary(
                        CandidateDecisionInspection((), (), None, None)))
    blob = _html_blob(empty)
    assert "No decision ledger records available." in blob
    assert "pl-dli-funnel" not in blob
    assert 'class="pl-dli-filter"' not in blob

    unavailable = replace(build_mock_screen(),
                          ledger_health=IntegrationHealth.unavailable(
                              "trust_ledger_inspection", detail="snapshot not present"),
                          ledger_inspection=None, ledger_funnel_summary=None)
    blob2 = _html_blob(unavailable)
    assert "Data unavailable" in blob2
    assert "pl-dli-funnel" not in blob2


def test_funnel_view_module_is_contract_only_no_service_or_protected_import():
    import ast
    from applications.trading_intelligence.ui.performance_learning import (
        decision_ledger_funnel_view as mod,
    )
    tree = ast.parse(inspect.getsource(mod))
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
        assert "candidate_decision_query_service" not in name
        assert "trust_ledger_snapshot" not in name
        assert "trust_ledger_inspection_source" not in name
    src = inspect.getsource(mod)
    for io_token in ("sqlite3", "hf_hub_download", "requests", "urllib",
                     "gradio", "datetime.now", "%"):
        assert io_token not in src


def test_rejection_gate_names_are_html_escaped_in_the_funnel():
    payload = "<script>alert(1)</script>"
    d = _decision(decision_id="C-x-D", candidate_event_id="C-x", action="REJECT",
                  gate_finding=GateFinding(gate=payload, passed=False, detail="d"),
                  risk_checks={"gate_trace": [{"gate": payload, "passed": False,
                                               "detail": "d"}]})
    cand = _candidate(candidate_event_id="C-x", sequence_number=1, decisions=(d,))
    blob = _html_blob(_screen([cand]))
    assert "<script>alert(1)</script>" not in blob
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in blob
