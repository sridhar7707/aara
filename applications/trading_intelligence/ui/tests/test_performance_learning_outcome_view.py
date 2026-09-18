"""Wave 2B: rendering of the Outcome History area in Performance & Learning.

Every screen here is constructed directly (no bootstrap, no database);
the composition-root mapping is covered by
tests/test_bootstrap_performance_learning_wiring.py.
"""
import gradio as gr

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
    OutcomeHistoryRow,
    PerformanceLearningScreen,
)
from dataclasses import replace

_PROVIDER = "trades_db_outcomes"


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def _dataframe(demo):
    frames = [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)]
    assert len(frames) == 1
    return frames[0]


def _closed_row(**overrides):
    base = dict(
        decision="AMZN BUY · trade-38", entry_date="2026-07-16 11:50 CDT", status="CLOSED",
        exit_date="2026-09-02 09:33 CDT", holding_days="47",
        realized_pnl_usd="-27.77", realized_pnl_pct="-0.23%", exit_basis="Bot fill",
        pairing_method="WINDOW_SINGLE_BOT_EXIT", pairing_confidence="HIGH", direction="LOSS",
        decision_reference="trade-38",
    )
    base.update(overrides)
    return OutcomeHistoryRow(**base)


def _open_row(**overrides):
    base = dict(
        decision="SLB BUY · trade-45", entry_date="2026-09-02 09:39 CDT", status="OPEN",
        exit_date="", holding_days="", realized_pnl_usd="", realized_pnl_pct="",
        exit_basis="", pairing_method="NONE_OPEN", pairing_confidence="NONE", direction="",
        decision_reference="trade-45",
    )
    base.update(overrides)
    return OutcomeHistoryRow(**base)


def _populated_screen(rows, summary="X BUY decisions — ..."):
    return replace(
        build_mock_screen(),
        outcome_rows=tuple(rows),
        outcome_health=IntegrationHealth.healthy(_PROVIDER),
        summary=summary,
    )


def _unavailable_screen(health):
    return replace(build_mock_screen(), outcome_health=health)


def _empty_healthy_screen():
    return replace(
        build_mock_screen(),
        outcome_rows=(),
        outcome_health=IntegrationHealth.healthy(_PROVIDER),
        summary="0 BUY decisions — 0 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
    )


# --- populated -----------------------------------------------------------

def test_populated_outcome_history_renders_table_visible_with_one_row_per_outcome():
    rows = [_closed_row(), _open_row(), _closed_row(decision="GOOGL BUY · trade-4")]
    ui = PerformanceLearningUI(screen=_populated_screen(rows, summary="3 BUY decisions — 2 CLOSED · 0 PARTIAL · 1 OPEN · 0 AMBIGUOUS."))

    demo = ui.build()
    frame = _dataframe(demo)

    assert frame.visible is True
    assert len(frame.value["data"] if isinstance(frame.value, dict) else frame.value) == 3


def test_summary_line_is_rendered_when_populated():
    ui = PerformanceLearningUI(
        screen=_populated_screen([_closed_row()], summary="1 BUY decisions — 1 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS. 7 SELL rows excluded (6 phantom-reconcile-suppressed, 1 orphan)."),
    )
    combined = "\n".join(_html_values(ui.build()))
    assert "1 BUY decisions — 1 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS." in combined
    assert "7 SELL rows excluded (6 phantom-reconcile-suppressed, 1 orphan)." in combined


def test_win_rate_summary_line_is_rendered_when_populated():
    ui = PerformanceLearningUI(
        screen=replace(
            _populated_screen([_closed_row()]),
            win_rate_summary="18 wins / 30 closed (60%).",
        ),
    )
    combined = "\n".join(_html_values(ui.build()))
    assert "18 wins / 30 closed (60%)." in combined


def test_win_rate_not_enough_data_message_is_rendered_when_populated():
    ui = PerformanceLearningUI(
        screen=replace(
            _populated_screen([_closed_row()]),
            win_rate_summary="Not enough completed trades yet for a win rate (1 of 30 needed).",
        ),
    )
    combined = "\n".join(_html_values(ui.build()))
    assert "Not enough completed trades yet for a win rate (1 of 30 needed)." in combined


def test_win_rate_summary_absent_when_none():
    ui = PerformanceLearningUI(screen=_populated_screen([_closed_row()]))
    combined = "\n".join(_html_values(ui.build()))
    assert "wins /" not in combined
    assert "Not enough completed trades" not in combined


def test_win_rate_summary_hidden_when_outcome_history_unavailable():
    """Mirrors the existing summary/table visible=False convention: the
    component's value is still computed, but it must not be visible when
    the outcome read itself is unavailable (populated is False)."""
    health = IntegrationHealth.unavailable(_PROVIDER, detail="trades snapshot is not present")
    message = "Not enough completed trades yet for a win rate (0 of 30 needed)."
    ui = PerformanceLearningUI(
        screen=replace(_unavailable_screen(health), win_rate_summary=message),
    )
    demo = ui.build()
    win_rate_blocks = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and getattr(b, "value", None) == f'<div class="pl-summary">{message}</div>'
    ]
    assert len(win_rate_blocks) == 1
    assert win_rate_blocks[0].visible is False


def test_open_partial_ambiguous_rows_have_blank_exit_pnl_direction():
    rows = [
        _open_row(),
        _open_row(decision="NKE BUY · trade-40", status="PARTIAL",
                  pairing_method="WINDOW_PARTIAL_RECONCILE_MARK", pairing_confidence="LOW",
                  exit_basis="Reconciliation mark", exit_date="2026-09-01 11:45 CDT",
                  holding_days="45", realized_pnl_usd="-198.54", realized_pnl_pct="-12.85%"),
        _open_row(decision="XYZ BUY · trade-99", status="AMBIGUOUS",
                  pairing_method="UNRESOLVED_MULTIPLE", pairing_confidence="NONE"),
    ]
    frame = _dataframe(PerformanceLearningUI(screen=_populated_screen(rows)).build())
    data = frame.value["data"] if isinstance(frame.value, dict) else frame.value
    # Direction column (index 10) blank for every non-CLOSED row
    for cells in data:
        assert cells[2] in ("OPEN", "PARTIAL", "AMBIGUOUS")
        assert cells[10] == ""
    # OPEN row: exit/pnl blank
    assert data[0][3] == "" and data[0][5] == "" and data[0][6] == "" and data[0][7] == ""
    # AMBIGUOUS row: exit/pnl blank
    assert data[2][3] == "" and data[2][5] == "" and data[2][6] == ""


def test_closed_row_renders_persisted_outcome_values_verbatim():
    """Impeccable critique finding #5: a negative Realized P&L $/% value
    is wrapped in the pl-negative-value span (gradio_view.py's
    _pnl_cell) -- the number itself is still the persisted value
    verbatim, unrounded and unreformatted, just with the negative-token
    span added around it."""
    frame = _dataframe(PerformanceLearningUI(screen=_populated_screen([_closed_row()])).build())
    data = frame.value["data"] if isinstance(frame.value, dict) else frame.value
    cells = data[0]
    assert cells[2] == "CLOSED"
    assert cells[3] == "2026-09-02 09:33 CDT"
    assert cells[4] == "47"
    assert cells[5] == '<span class="pl-negative-value">-27.77</span>'
    assert cells[6] == '<span class="pl-negative-value">-0.23%</span>'
    assert cells[10] == "LOSS"


def test_exit_basis_labels():
    rows = [
        _closed_row(exit_basis="Bot fill"),
        _closed_row(decision="GOOGL BUY · trade-4", exit_basis="Reconciliation mark",
                    pairing_method="WINDOW_SINGLE_RECONCILE_MARK", pairing_confidence="MEDIUM",
                    direction="WIN", realized_pnl_usd="808.83", realized_pnl_pct="6.71%"),
    ]
    frame = _dataframe(PerformanceLearningUI(screen=_populated_screen(rows)).build())
    data = frame.value["data"] if isinstance(frame.value, dict) else frame.value
    assert data[0][7] == "Bot fill"
    assert data[1][7] == "Reconciliation mark"


def test_pairing_method_and_confidence_render():
    frame = _dataframe(PerformanceLearningUI(screen=_populated_screen([_closed_row()])).build())
    data = frame.value["data"] if isinstance(frame.value, dict) else frame.value
    assert data[0][8] == "WINDOW_SINGLE_BOT_EXIT"
    assert data[0][9] == "HIGH"


def test_headers_are_the_twelve_factual_columns():
    """Decision Quality Cross-Linking: a twelfth "Decision ID" column,
    appended at the end -- the existing eleven factual columns are
    unchanged, in the same order."""
    frame = _dataframe(PerformanceLearningUI(screen=_populated_screen([_closed_row()])).build())
    assert frame.headers == [
        "Decision", "Entry date", "Status", "Exit date", "Holding days",
        "Realized P&L $", "Realized P&L %", "Exit basis", "Pairing method",
        "Pairing confidence", "Direction", "Decision ID",
    ]


def test_decision_id_column_carries_the_real_decision_reference():
    """The new column's value is a clean, standalone decision_id -- the
    SAME identity Decision Center's own list table shows -- not a second
    composite string and not derived from the existing `decision` field."""
    row = _closed_row(decision="AMZN BUY · trade-38", decision_reference="trade-38")
    frame = _dataframe(PerformanceLearningUI(screen=_populated_screen([row])).build())
    data = frame.value["data"] if isinstance(frame.value, dict) else frame.value
    assert data[0][11] == "trade-38"


# --- unavailable / empty -----------------------------------------------

def test_non_healthy_read_renders_reason_and_hides_table():
    health = IntegrationHealth.unavailable(_PROVIDER, detail="trades snapshot is not present")
    demo = PerformanceLearningUI(screen=_unavailable_screen(health)).build()
    combined = "\n".join(_html_values(demo))
    assert "Data unavailable -- provider could not be reached" in combined
    assert _dataframe(demo).visible is False


def test_no_provider_default_renders_the_sections_own_unavailable_message():
    demo = PerformanceLearningUI().build()
    combined = "\n".join(_html_values(demo))
    assert build_mock_screen().outcome_history.unavailable_message in combined
    assert _dataframe(demo).visible is False


def test_healthy_but_empty_renders_honest_empty_message_and_hides_table():
    demo = PerformanceLearningUI(screen=_empty_healthy_screen()).build()
    combined = "\n".join(_html_values(demo))
    assert "No BUY decisions are present in the current trades snapshot." in combined
    assert _dataframe(demo).visible is False


# --- invariants across states ----------------------------------------

def test_attribution_and_calibration_stay_unavailable_in_every_state():
    for screen in (
        build_mock_screen(),
        _unavailable_screen(IntegrationHealth.api_error(_PROVIDER)),
        _empty_healthy_screen(),
        _populated_screen([_closed_row()]),
    ):
        combined = "\n".join(_html_values(PerformanceLearningUI(screen=screen).build()))
        assert screen.attribution_breakdown.unavailable_message in combined
        assert screen.model_confidence_calibration.unavailable_message in combined
        assert ATTRIBUTION_BREAKDOWN_TITLE in combined
        assert MODEL_CONFIDENCE_CALIBRATION_TITLE in combined
        assert OUTCOME_HISTORY_TITLE in combined


def test_no_illustrative_data_banner_in_any_state():
    for screen in (
        build_mock_screen(),
        _empty_healthy_screen(),
        _populated_screen([_closed_row()]),
    ):
        combined = "\n".join(_html_values(PerformanceLearningUI(screen=screen).build()))
        assert "Illustrative Data" not in combined


def _bound_render_functions(demo, ui):
    return [
        bf for bf in demo.fns.values()
        if getattr(bf.fn, "__func__", None) is PerformanceLearningUI._render
        and getattr(bf.fn, "__self__", None) is ui
    ]


def test_outcome_history_uses_the_one_shared_refresh_button_not_its_own():
    """Outcome History participates in the screen-level shared Refresh /
    demo.load() mechanism the P0-2 correction added (see gradio_view.py's
    _render() docstring) -- unlike the Decision Ledger Inspection section,
    which is deliberately excluded from it (ADR-064 SS2.12, see
    test_performance_learning_decision_ledger_view.py). This test previously
    asserted zero buttons/dependencies at all, which predates that shared
    mechanism; it now checks there is exactly one button (shared, not a
    second one of Outcome History's own) and that _render is bound to both
    the load and the click chain, matching every sibling screen's convention
    (e.g. ui/risk_intelligence/gradio_view.py)."""
    ui = PerformanceLearningUI(screen=_populated_screen([_closed_row()]))
    demo = ui.build()
    buttons = [b for b in demo.blocks.values() if isinstance(b, gr.Button)]
    assert len(buttons) == 1
    # one _render binding for demo.load(), one for the Refresh .then() chain
    assert len(_bound_render_functions(demo, ui)) == 2
