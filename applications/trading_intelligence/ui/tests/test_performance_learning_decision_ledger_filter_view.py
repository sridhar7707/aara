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
from applications.trading_intelligence.ui.performance_learning.decision_ledger_funnel_view import (
    build_filter_controls_html,
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
    """The filter itself stays pure HTML radio + CSS with zero event wiring
    (ADR-064, no scope expansion) -- checked against its own module, not
    against PerformanceLearningUI.build(), which legitimately gained a
    shared Refresh button/`.load()`/`.click()` for the *other*, refreshable
    sections of the screen under the P0-2 correction (see gradio_view.py's
    _render() docstring). That shared mechanism deliberately never touches
    the filter or the rest of the Decision Ledger Inspection section."""
    filter_src = inspect.getsource(build_filter_controls_html)
    assert ".load(" not in filter_src
    assert ".click(" not in filter_src
    assert ".change(" not in filter_src
    assert "gr.Button" not in filter_src
    assert "gr.Radio" not in filter_src
    assert "interactive=True" not in filter_src


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
    # Scope the outcome-vocabulary guard to the Decision Ledger Inspection
    # panel only -- it is the decision-time-only surface. The separate
    # Model Confidence Calibration area (rendered above it) legitimately
    # uses "win rate" for its historical realized tally.
    ledger_panel = blob[blob.index("Decision Ledger Inspection"):]
    lowered = ledger_panel.lower()
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


# --- Sprint 4: Decision pipeline chart -------------------------------------
#
# Visible under EXACTLY the same condition the existing funnel text panel
# already uses (screen.ledger_funnel_available) -- no new threshold, no
# second read, no fabricated data. Answers "where do candidates get
# filtered out before becoming a decision?" -- a decision-pipeline view,
# not a performance/outcome chart.


def _demo(screen):
    return PerformanceLearningUI(screen=screen).build()


def _pipeline_chart(demo):
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.BarPlot) and "pl-pipeline-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def _pipeline_chart_card(demo):
    cards = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Column)
        and "aara-card" in (b.elem_classes or [])
        and "pl-pipeline-chart-card" in (b.elem_classes or [])
    ]
    assert len(cards) == 1
    return cards[0]


def test_pipeline_chart_visible_when_funnel_available():
    demo = _demo(_screen(_mixed_population()))

    assert _pipeline_chart(demo).visible is True
    assert _pipeline_chart_card(demo).visible is True


def test_pipeline_chart_hidden_when_ledger_unavailable():
    from dataclasses import replace

    unavailable = replace(
        build_mock_screen(),
        ledger_health=IntegrationHealth.unavailable(
            "trust_ledger_inspection", detail="snapshot not present"
        ),
        ledger_inspection=None, ledger_funnel_summary=None,
    )

    demo = _demo(unavailable)

    assert _pipeline_chart(demo).visible is False
    assert _pipeline_chart_card(demo).visible is False
    assert list(_pipeline_chart(demo).value["data"]) == []


def test_pipeline_chart_hidden_when_ledger_empty():
    """A HEALTHY read with zero candidate rows -- screen.ledger_funnel_
    available is False here even though a (zero-population) summary was
    computed, matching the existing funnel text panel's own behavior
    (test_funnel_and_filter_absent_in_empty_and_unavailable_states). The
    chart must not show six zero bars implying real data exists."""
    from dataclasses import replace

    empty_inspection = CandidateDecisionInspection((), (), None, None)
    empty = replace(
        build_mock_screen(),
        ledger_health=IntegrationHealth.healthy("trust_ledger_inspection"),
        ledger_inspection=empty_inspection,
        ledger_funnel_summary=build_ledger_funnel_summary(empty_inspection),
    )

    demo = _demo(empty)

    assert _pipeline_chart(demo).visible is False
    assert _pipeline_chart_card(demo).visible is False
    assert list(_pipeline_chart(demo).value["data"]) == []


def test_pipeline_chart_and_funnel_panel_visibility_always_match():
    from dataclasses import replace

    cases = [
        replace(
            build_mock_screen(),
            ledger_health=IntegrationHealth.unavailable("x", detail="d"),
            ledger_inspection=None, ledger_funnel_summary=None,
        ),
        _screen(_mixed_population()),
    ]
    for screen in cases:
        demo = _demo(screen)
        assert _pipeline_chart(demo).visible is screen.ledger_funnel_available
        assert _pipeline_chart_card(demo).visible is screen.ledger_funnel_available


def test_pipeline_chart_uses_the_existing_funnel_counts_verbatim():
    """No fabricated or recomputed counts: the chart's dataframe must carry
    the SAME literal counts LedgerFunnelSummary already provides -- the
    exact numbers test_funnel_panel_states_the_three_populations_distinctly
    / test_funnel_panel_shows_executed_held_rejected_and_the_action_line
    already assert appear in the text panel for this same fixture."""
    demo = _demo(_screen(_mixed_population()))

    chart = _pipeline_chart(demo)
    stage_col = chart.value["columns"].index("stage")
    count_col = chart.value["columns"].index("count")
    values = {row[stage_col]: row[count_col] for row in chart.value["data"]}
    assert values == {
        "Candidates": 7, "Evaluated": 6, "Decisions": 5,
        "Executed": 1, "Held": 1, "Rejected": 3,
    }


def test_pipeline_chart_preserves_the_authoritative_stage_order():
    demo = _demo(_screen(_mixed_population()))

    chart = _pipeline_chart(demo)
    stage_col = chart.value["columns"].index("stage")
    ordered_stages = [row[stage_col] for row in chart.value["data"]]
    assert ordered_stages == [
        "Candidates", "Evaluated", "Decisions", "Executed", "Held", "Rejected",
    ]
    assert chart.sort == [
        "Candidates", "Evaluated", "Decisions", "Executed", "Held", "Rejected",
    ]


def test_pipeline_chart_shows_zero_count_stage_honestly():
    """reject_count == 0 is a real, legitimate zero (nothing was rejected
    in this population) -- the Rejected stage must still appear, at 0,
    never omitted."""
    screen = _screen([_executed_candidate("C-x1", 1), _hold_candidate("C-h1", 2)])

    demo = _demo(screen)

    chart = _pipeline_chart(demo)
    stage_col = chart.value["columns"].index("stage")
    count_col = chart.value["columns"].index("count")
    values = {row[stage_col]: row[count_col] for row in chart.value["data"]}
    assert "Rejected" in values
    assert values["Rejected"] == 0
    assert values == {
        "Candidates": 2, "Evaluated": 2, "Decisions": 2,
        "Executed": 1, "Held": 1, "Rejected": 0,
    }


def test_pipeline_chart_title_and_description_render_verbatim_and_distinct_from_section_label():
    blob = _html_blob(_screen(_mixed_population()))

    assert "Decision pipeline" in blob
    assert "Candidate counts at each stage of the decision lifecycle." in blob
    # Distinct from the outer frozen section label -- never duplicated.
    assert "Decision pipeline" != "Decision Ledger Inspection"
    assert blob.count(
        '<div class="pl-section-label">Decision Ledger Inspection</div>'
    ) == 1


def test_pipeline_chart_height_is_220_not_320():
    demo = _demo(_screen(_mixed_population()))

    assert _pipeline_chart(demo).height == 220


def test_pipeline_chart_sits_inside_the_aara_card_treatment():
    demo = _demo(_screen(_mixed_population()))

    card = _pipeline_chart_card(demo)
    assert "aara-card" in (card.elem_classes or [])


def test_pipeline_chart_does_not_use_the_win_loss_color_map():
    """Not a Win/Loss chart -- single-series brand navy, never the
    calibration/regime charts' Win/Loss red-green-adjacent vocabulary."""
    demo = _demo(_screen(_mixed_population()))

    chart = _pipeline_chart(demo)
    assert chart.color_map != {"Win": "#0B1F3A", "Loss": "#7A2E2E"}
    assert set(chart.color_map.values()) == {"#0B1F3A"}


def test_pipeline_chart_does_not_duplicate_the_boundary_notice():
    """The existing decision-time-boundary notice is the closest thing to
    an authoritative disclaimer for this section -- it must still render
    exactly once, from the existing funnel body, never duplicated by the
    new chart card."""
    blob = _html_blob(_screen(_mixed_population()))
    assert blob.count(
        "END OF DECISION-TIME EVIDENCE — trade/outcome recorded separately, "
        "not linked by any deterministic key."
    ) == 1


def test_existing_funnel_panel_and_candidate_cards_still_render_unchanged():
    """The chart is additive -- the existing funnel text panel, filter
    chips, and candidate cards must render exactly as before, untouched."""
    blob = _html_blob(_screen(_mixed_population()))
    assert "7 candidates screened" in blob
    assert "1 executed" in blob and "1 held" in blob and "3 rejected" in blob
    assert 'class="pl-dli-filter"' in blob
    for state in ("executed", "hold", "rejected", "no-decision", "incomplete"):
        assert f"pl-dli-candidate--{state}" in blob


def test_pipeline_chart_introduces_no_new_data_source_import():
    """The chart must be driven purely by screen.ledger_funnel_summary
    already on PerformanceLearningScreen -- no new adapter/service import,
    no new database query, no new network dependency wired into the UI
    module."""
    import ast

    from applications.trading_intelligence.ui.performance_learning import (
        gradio_view as module,
    )

    tree = ast.parse(inspect.getsource(module))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)

    assert not any("candidate_decision_query_service" in name for name in imported_names)
    assert not any("trust_ledger" in name for name in imported_names)
    assert not any(
        name in ("requests", "httpx", "urllib.request", "sqlite3")
        for name in imported_names
    )
