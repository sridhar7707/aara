from datetime import datetime, timedelta, timezone

import gradio as gr
import pandas as pd

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
    _ALPACA_ORDERS_SCOPE_CAPTION,
    _ALPACA_ORDERS_STATUS_NOTE,
    _ALPACA_ORDERS_TRUNCATION_NOTE,
    _ALPACA_ORDERS_UNAVAILABLE_MESSAGE,
    _ALPACA_ORDERS_WORKING_MARKER,
    _ALPACA_PAPER_BADGE_TEXT,
    _ALPACA_UNAVAILABLE_MESSAGE,
    _CAPITAL_SOURCE_CAPTION,
    _CAPITAL_UNAVAILABLE_MESSAGE,
    _HOLDINGS_UNAVAILABLE_MESSAGE,
    _DEFAULT_TIMEFRAME,
    _DRAWDOWN_DISCLAIMER,
    _DRAWDOWN_EMPTY_MESSAGE,
    _DRAWDOWN_NO_DATA_FOR_TIMEFRAME_MESSAGE,
    _DRAWDOWN_UNAVAILABLE_MESSAGE,
    _PARTIAL_DATA_BODY,
    _PARTIAL_DATA_HTML,
    _PARTIAL_DATA_TITLE,
    _PORTFOLIO_HISTORY_EMPTY_MESSAGE,
    _PORTFOLIO_HISTORY_NO_DATA_FOR_TIMEFRAME_MESSAGE,
    _PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE,
    _REAL_DATA_HTML,
    _RECONCILIATION_ALPACA_UNAVAILABLE_MESSAGE,
    _RECONCILIATION_INTERNAL_UNAVAILABLE_MESSAGE,
    _RECONCILIATION_SCOPE_CAPTION,
    _RENDERED_AT_PREFIX,
    _SNAPSHOT_PREFIX,
    _SNAPSHOT_UNAVAILABLE,
    _TIMEFRAME_CHOICES,
    _UNAVAILABLE_DATA_BODY,
    _UNAVAILABLE_DATA_HTML,
    _UNAVAILABLE_DATA_TITLE,
    PortfolioIntelligenceUI,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
    AlpacaOrder,
    AlpacaOrdersSnapshot,
    AlpacaPosition,
    CapitalSummary,
    PortfolioDrawdownPoint,
    PortfolioHistoryPoint,
    PortfolioHolding,
    PortfolioScreen,
    ReconciliationRow,
    ReconciliationStatus,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _make_capital(**overrides):
    defaults = dict(
        allocated_amount=1000.0,
        available_cash=400.0,
        invested_amount=600.0,
        reserve=100.0,
        realized_profit=50.0,
    )
    defaults.update(overrides)
    return CapitalSummary(**defaults)


def _make_alpaca_account(**overrides):
    defaults = dict(equity=100018.33, cash=59869.06, buying_power=351894.19, portfolio_value=100018.33)
    defaults.update(overrides)
    return AlpacaAccountSnapshot(**defaults)


def _make_holding(**overrides):
    defaults = dict(symbol="ZZZZ", quantity=1.0, price=1.0, market_value=1.0, weight_pct=100.0)
    defaults.update(overrides)
    return PortfolioHolding(**defaults)


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def _visible_dataframes(demo):
    """Data is fetched at render time now, so every dynamic gr.Dataframe
    is always present in the layout -- hidden (visible=False) when its
    section is unavailable/empty, shown when it has real rows. The old
    "no gr.Dataframe exists" assertions become "no gr.Dataframe is
    visible"."""
    return [
        block for block in demo.blocks.values()
        if isinstance(block, gr.Dataframe) and getattr(block, "visible", True)
    ]


def _rendered_surfaces(ui):
    """Returns (html_text, table_cells) for one build() -- html_text is the
    concatenated gr.HTML block values (capital summary, disclosure banner,
    labels, unavailable messages); table_cells is every gr.Dataframe cell
    string (Holdings / Alpaca positions / Alpaca orders rows)."""
    demo = ui.build()
    html_text = "\n".join(_html_values(demo))
    table_cells = []
    for block in demo.blocks.values():
        if isinstance(block, gr.Dataframe):
            val = getattr(block, "value", None)
            if isinstance(val, dict) and isinstance(val.get("data"), list):
                for row in val["data"]:
                    table_cells.extend(str(cell) for cell in row)
    return html_text, table_cells


# --- Default = explicit UNAVAILABLE state, never a mock screen --------


def test_ui_defaults_to_an_all_unavailable_screen():
    ui = PortfolioIntelligenceUI()

    assert ui._screen.capital is None
    assert ui._screen.holdings is None
    assert ui._screen.capital_is_available is False
    assert ui._screen.holdings_is_available is False


def test_build_returns_a_gradio_blocks_instance():
    demo = PortfolioIntelligenceUI().build()

    assert isinstance(demo, gr.Blocks)


def test_unavailable_data_disclosure_is_the_exact_fixed_text():
    assert _UNAVAILABLE_DATA_TITLE == "Data Unavailable"
    # B3 Tier 1: shared .aara-disclosure-title / .aara-disclosure-body are
    # wired alongside the local classes; the .pi-disclosure wrapper is
    # unchanged.
    assert _UNAVAILABLE_DATA_HTML == (
        '<div class="pi-disclosure">'
        f'<div class="pi-disclosure-title aara-disclosure-title">{_UNAVAILABLE_DATA_TITLE}</div>'
        f'<div class="pi-disclosure-body aara-disclosure-body">{_UNAVAILABLE_DATA_BODY}</div>'
        "</div>"
    )
    assert "illustrative" not in _UNAVAILABLE_DATA_BODY.lower()


def test_partial_disclosure_never_says_illustrative():
    assert _PARTIAL_DATA_TITLE == "Partial Data"
    assert "illustrative" not in _PARTIAL_DATA_BODY.lower()
    assert "unavailable" in _PARTIAL_DATA_BODY.lower()


def test_default_render_is_the_unavailable_state_with_no_dataframe():
    demo = PortfolioIntelligenceUI().build()
    html_text = "\n".join(_html_values(demo))

    assert _UNAVAILABLE_DATA_HTML in html_text
    assert _CAPITAL_UNAVAILABLE_MESSAGE in html_text
    assert _HOLDINGS_UNAVAILABLE_MESSAGE in html_text
    assert _visible_dataframes(demo) == []


def test_no_fabricated_capital_or_holdings_marker_reaches_any_rendered_state():
    """Production guarantee: the fabricated figures/symbols in
    portfolio_intelligence/mock_data.py never appear in any rendered
    PortfolioIntelligenceUI state -- UNAVAILABLE, PARTIAL, EMPTY, or REAL.
    mock_data.py itself is untouched and kept only for isolated unit
    tests; it must never reach a rendered screen."""
    from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import (
        build_mock_screen,
    )

    mock = build_mock_screen()
    mock_symbols = {h.symbol for h in mock.holdings}
    mock_capital_markers = (
        f"${mock.capital.allocated_amount:,.2f}",   # $50,000.00
        f"${mock.capital.realized_profit:,.2f}",    # $3,450.20
        f"${mock.capital.available_cash:,.2f}",     # $12,270.85
    )
    real_capital = _make_capital(allocated_amount=1234.0)

    states = {
        "UNAVAILABLE": PortfolioIntelligenceUI(),
        "PARTIAL": PortfolioIntelligenceUI(
            PortfolioScreen(capital=real_capital, holdings=None)
        ),
        "EMPTY": PortfolioIntelligenceUI(
            PortfolioScreen(capital=real_capital, holdings=())
        ),
        "REAL": PortfolioIntelligenceUI(
            PortfolioScreen(capital=real_capital, holdings=(_make_holding(),))
        ),
    }
    for name, ui in states.items():
        html_text, table_cells = _rendered_surfaces(ui)
        for marker in mock_capital_markers:
            assert marker not in html_text, f"{name}: fabricated capital {marker} rendered"
        assert not mock_symbols.issubset(set(table_cells)), (
            f"{name}: fabricated holdings symbols rendered"
        )


def test_alpaca_sections_render_only_unavailable_text_with_no_alpaca_data():
    """Units 1 & 3: a PortfolioScreen with no Alpaca account and no Alpaca
    orders renders the fixed unavailable message for both Alpaca blocks --
    there is no illustrative Alpaca fallback (real / unavailable / empty
    only)."""
    screen = PortfolioScreen(capital=_make_capital(), alpaca_account=None, alpaca_orders=None)
    html_text, table_cells = _rendered_surfaces(PortfolioIntelligenceUI(screen=screen))

    assert _ALPACA_UNAVAILABLE_MESSAGE in html_text
    assert _ALPACA_ORDERS_UNAVAILABLE_MESSAGE in html_text
    assert table_cells == []


def test_shell_header_and_nav_are_present_in_the_built_layout():
    demo = PortfolioIntelligenceUI().build()

    html_values = _html_values(demo)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Portfolio Intelligence") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    demo = PortfolioIntelligenceUI().build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


# --- Formatters (called directly, real inputs) ----------------------


def test_capital_summary_html_includes_every_metric():
    capital = _make_capital()

    summary_html = PortfolioIntelligenceUI._format_capital_summary_html(capital)

    assert "Allocated" in summary_html
    assert "$1,000.00" in summary_html
    assert "Available Cash" in summary_html
    assert "$400.00" in summary_html
    assert "Invested" in summary_html
    assert "$600.00" in summary_html
    assert "Reserve" in summary_html
    assert "$100.00" in summary_html
    assert "Tradeable Cash" in summary_html
    assert "$300.00" in summary_html
    assert "Total Value" in summary_html
    assert "Realized Profit" in summary_html
    assert "$50.00" in summary_html


def test_allocation_html_reflects_cash_and_invested_weights():
    capital = _make_capital(available_cash=400.0, invested_amount=600.0)

    allocation_html = PortfolioIntelligenceUI._format_allocation_html(capital)

    assert "Invested 60.0%" in allocation_html
    assert "Cash 40.0%" in allocation_html
    assert "width:60.0%" in allocation_html
    assert "width:40.0%" in allocation_html


def test_format_holdings_rows_maps_every_field():
    holding = PortfolioHolding(
        symbol="AAPL", quantity=10, price=100.5, market_value=1005.0, weight_pct=33.3,
    )

    rows = PortfolioIntelligenceUI._format_holdings_rows((holding,))

    assert rows == [["AAPL", "10", "$100.50", "$1,005.00", "33.3%"]]


def test_format_holdings_rows_handles_multiple_holdings_in_order():
    holding_a = PortfolioHolding(
        symbol="AAPL", quantity=10, price=100.0, market_value=1000.0, weight_pct=50.0,
    )
    holding_b = PortfolioHolding(
        symbol="MSFT", quantity=5, price=200.0, market_value=1000.0, weight_pct=50.0,
    )

    rows = PortfolioIntelligenceUI._format_holdings_rows((holding_a, holding_b))

    assert [row[0] for row in rows] == ["AAPL", "MSFT"]


# --- UNAVAILABLE state (capital source returned None) ---------------


def test_capital_unavailable_renders_the_message_not_a_summary_or_allocation_bar():
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=None, holdings=None))

    html_text, _ = _rendered_surfaces(ui)

    assert html_text.count(_CAPITAL_UNAVAILABLE_MESSAGE) == 2  # Summary + Allocation
    assert "pi-allocation-bar" not in html_text
    assert "pi-capital-summary" not in html_text
    assert _UNAVAILABLE_DATA_HTML in html_text


def test_holdings_unavailable_renders_the_message_and_no_table():
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital(), holdings=None))

    demo = ui.build()
    html_values = _html_values(demo)
    dataframes = _visible_dataframes(demo)

    assert any(_HOLDINGS_UNAVAILABLE_MESSAGE in v for v in html_values)
    assert not any(d for d in dataframes if "pi-holdings-table" in (d.elem_classes or []))


# --- Portfolio Value Over Time (real portfolio_snapshots history chart) --


def _history_chart(demo):
    """The Portfolio Value chart specifically -- scoped by elem_classes
    since Visual Dashboard Phase B added a second gr.LinePlot (the
    drawdown chart, see _drawdown_chart below)."""
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.LinePlot)
        and "pi-portfolio-history-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def _drawdown_chart(demo):
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.LinePlot)
        and "pi-portfolio-drawdown-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def test_portfolio_history_unavailable_renders_the_message_and_hides_the_chart():
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=None))

    demo = ui.build()
    html_values = _html_values(demo)

    assert any(_PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE in v for v in html_values)
    assert _history_chart(demo).visible is False


def test_portfolio_history_empty_renders_the_message_and_hides_the_chart():
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=()))

    demo = ui.build()
    html_values = _html_values(demo)

    assert any("No portfolio history is recorded yet." in v for v in html_values)
    assert _history_chart(demo).visible is False


def test_portfolio_history_with_real_points_renders_the_chart_and_no_message():
    points = (
        PortfolioHistoryPoint(as_of="2026-08-30T15:03:38+00:00", portfolio_value=90000.0),
        PortfolioHistoryPoint(as_of="2026-08-31T19:39:42+00:00", portfolio_value=100029.85),
    )
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=points))

    demo = ui.build()
    chart = _history_chart(demo)

    assert chart.visible is True
    assert [row[1] for row in chart.value["data"]] == [90000.0, 100029.85]
    # x is each point's own as_of instant (epoch ms), in the same order
    assert [row[0] for row in chart.value["data"]] == [
        int(pd.Timestamp(p.as_of).timestamp() * 1000) for p in points
    ]
    assert not any(
        "Portfolio value history" in v or "No portfolio history" in v
        for v in _html_values(demo)
    )


def test_portfolio_history_chart_has_no_derived_performance_metrics():
    """Explicit scope guard: only the two real columns (timestamp, portfolio
    value) may ever appear -- no Sharpe/alpha/beta/CAGR/ROI/drawdown or any
    other computed metric."""
    points = (PortfolioHistoryPoint(as_of="2026-08-31T00:00:00+00:00", portfolio_value=100000.0),)
    chart = _history_chart(PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=points)).build())

    assert set(chart.value["columns"]) == {"as_of", "portfolio_value"}


# --- Visual Dashboard Phase A: timeframe filtering (pure function) -------


_NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


def _point(days_ago, value):
    as_of = (_NOW - timedelta(days=days_ago)).isoformat()
    return PortfolioHistoryPoint(as_of=as_of, portfolio_value=value)


def test_filter_by_timeframe_all_returns_every_point_unchanged():
    points = (_point(400, 1.0), _point(10, 2.0), _point(0, 3.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "ALL", _NOW)
    assert result == points


def test_filter_by_timeframe_1d_keeps_only_points_within_the_last_day():
    points = (_point(2, 1.0), _point(1, 2.0), _point(0, 3.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "1D", _NOW)
    assert [p.portfolio_value for p in result] == [2.0, 3.0]


def test_filter_by_timeframe_1w_keeps_only_points_within_the_last_seven_days():
    points = (_point(10, 1.0), _point(7, 2.0), _point(1, 3.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "1W", _NOW)
    assert [p.portfolio_value for p in result] == [2.0, 3.0]


def test_filter_by_timeframe_1m_uses_a_thirty_day_window():
    points = (_point(31, 1.0), _point(30, 2.0), _point(1, 3.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "1M", _NOW)
    assert [p.portfolio_value for p in result] == [2.0, 3.0]


def test_filter_by_timeframe_3m_uses_a_ninety_day_window():
    points = (_point(91, 1.0), _point(90, 2.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "3M", _NOW)
    assert [p.portfolio_value for p in result] == [2.0]


def test_filter_by_timeframe_6m_uses_a_hundred_eighty_day_window():
    points = (_point(181, 1.0), _point(180, 2.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "6M", _NOW)
    assert [p.portfolio_value for p in result] == [2.0]


def test_filter_by_timeframe_1y_uses_a_three_hundred_sixty_five_day_window():
    points = (_point(366, 1.0), _point(365, 2.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "1Y", _NOW)
    assert [p.portfolio_value for p in result] == [2.0]


def test_filter_by_timeframe_ytd_uses_january_first_of_the_current_year():
    dec_31_last_year = PortfolioHistoryPoint(
        as_of=datetime(2025, 12, 31, tzinfo=timezone.utc).isoformat(), portfolio_value=1.0,
    )
    jan_1_this_year = PortfolioHistoryPoint(
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(), portfolio_value=2.0,
    )
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(
        (dec_31_last_year, jan_1_this_year), "YTD", _NOW,
    )
    assert [p.portfolio_value for p in result] == [2.0]


def test_filter_by_timeframe_preserves_ascending_order():
    points = (_point(5, 1.0), _point(3, 2.0), _point(1, 3.0))
    result = PortfolioIntelligenceUI._filter_history_by_timeframe(points, "1W", _NOW)
    assert result == points


def test_filter_by_timeframe_drops_unparseable_as_of_rather_than_guessing():
    bad = PortfolioHistoryPoint(as_of="not-a-timestamp", portfolio_value=99.0)
    good = _point(0, 1.0)
    result = PortfolioIntelligenceUI._filter_history_by_timeframe((bad, good), "1D", _NOW)
    assert result == (good,)


def test_filter_by_timeframe_naive_as_of_is_treated_as_utc():
    naive = PortfolioHistoryPoint(
        as_of=(_NOW - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
        portfolio_value=5.0,
    )
    result = PortfolioIntelligenceUI._filter_history_by_timeframe((naive,), "1D", _NOW)
    assert result == (naive,)


def test_filter_by_timeframe_empty_input_is_empty_output():
    assert PortfolioIntelligenceUI._filter_history_by_timeframe((), "1M", _NOW) == ()


# --- Visual Dashboard Phase A: summary calculation (pure function) -------


def test_compute_summary_none_for_empty_points():
    assert PortfolioIntelligenceUI._compute_portfolio_summary(()) is None


def test_compute_summary_current_is_the_most_recent_point():
    points = (_point(5, 100.0), _point(1, 150.0), _point(0, 120.0))
    summary = PortfolioIntelligenceUI._compute_portfolio_summary(points)
    assert summary["current"] == 120.0


def test_compute_summary_starting_is_the_earliest_point_in_the_window_not_all_time():
    """Starting value is the first point WITHIN the already-filtered window
    passed in -- this function never looks beyond what it's given."""
    points = (_point(5, 100.0), _point(1, 150.0))
    summary = PortfolioIntelligenceUI._compute_portfolio_summary(points)
    assert summary["starting"] == 100.0


def test_compute_summary_absolute_and_percentage_change_are_plain_arithmetic():
    points = (_point(5, 100.0), _point(0, 125.0))
    summary = PortfolioIntelligenceUI._compute_portfolio_summary(points)
    assert summary["absolute_change"] == 25.0
    assert summary["percentage_change"] == 25.0


def test_compute_summary_negative_change_is_a_real_negative_number():
    points = (_point(5, 200.0), _point(0, 150.0))
    summary = PortfolioIntelligenceUI._compute_portfolio_summary(points)
    assert summary["absolute_change"] == -50.0
    assert summary["percentage_change"] == -25.0


def test_compute_summary_single_point_is_zero_change_not_fabricated():
    points = (_point(0, 500.0),)
    summary = PortfolioIntelligenceUI._compute_portfolio_summary(points)
    assert summary["current"] == 500.0
    assert summary["starting"] == 500.0
    assert summary["absolute_change"] == 0.0
    assert summary["percentage_change"] == 0.0


def test_compute_summary_percentage_change_is_none_when_starting_value_is_zero():
    """Never a fabricated +/-inf or NaN -- division by a real zero starting
    value is left undefined (None), not computed."""
    points = (_point(5, 0.0), _point(0, 100.0))
    summary = PortfolioIntelligenceUI._compute_portfolio_summary(points)
    assert summary["absolute_change"] == 100.0
    assert summary["percentage_change"] is None


# --- Visual Dashboard Phase A: summary HTML rendering ---------------------


def test_format_summary_html_is_empty_string_for_none():
    assert PortfolioIntelligenceUI._format_portfolio_summary_html(None) == ""


def test_format_summary_html_includes_all_four_fields_when_percentage_is_defined():
    summary = {
        "current": 1250.5, "starting": 1000.0,
        "absolute_change": 250.5, "percentage_change": 25.05,
    }
    out = PortfolioIntelligenceUI._format_portfolio_summary_html(summary)
    assert "Current Value" in out and "$1,250.50" in out
    assert "Starting Value" in out and "$1,000.00" in out
    assert "Change" in out and "+$250.50" in out
    assert "% Change" in out and "+25.05%" in out


def test_format_summary_html_shows_negative_change_with_a_minus_sign():
    summary = {
        "current": 750.0, "starting": 1000.0,
        "absolute_change": -250.0, "percentage_change": -25.0,
    }
    out = PortfolioIntelligenceUI._format_portfolio_summary_html(summary)
    assert "-$250.00" in out
    assert "-25.00%" in out


def test_format_summary_html_omits_percentage_change_when_none():
    summary = {
        "current": 100.0, "starting": 0.0,
        "absolute_change": 100.0, "percentage_change": None,
    }
    out = PortfolioIntelligenceUI._format_portfolio_summary_html(summary)
    assert "Current Value" in out
    assert "% Change" not in out


def test_format_summary_html_reuses_the_existing_metric_markup_no_new_styling():
    summary = {
        "current": 100.0, "starting": 90.0,
        "absolute_change": 10.0, "percentage_change": 11.11,
    }
    out = PortfolioIntelligenceUI._format_portfolio_summary_html(summary)
    assert 'class="pi-capital-summary"' in out
    assert 'class="pi-metric"' in out
    assert 'class="pi-metric-label aara-metric-label"' in out
    assert 'class="pi-metric-value"' in out


# --- Visual Dashboard Phase B: drawdown calculation (pure function) ------


def test_drawdown_history_first_point_is_always_zero():
    points = (_point(5, 100.0),)
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert result == (
        PortfolioDrawdownPoint(as_of=points[0].as_of, portfolio_value=100.0, drawdown_pct=0.0),
    )


def test_drawdown_history_rising_series_stays_at_zero():
    points = (_point(3, 100.0), _point(2, 110.0), _point(1, 120.0), _point(0, 130.0))
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert [round(p.drawdown_pct, 4) for p in result] == [0.0, 0.0, 0.0, 0.0]


def test_drawdown_history_falling_series_is_negative_from_the_peak():
    points = (
        _point(3, 100.0),   # peak so far: 100 -> 0%
        _point(2, 90.0),    # 10% below peak -> -10%
        _point(1, 80.0),    # 20% below peak -> -20%
    )
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert [round(p.drawdown_pct, 4) for p in result] == [0.0, -10.0, -20.0]


def test_drawdown_history_new_peak_resets_to_zero():
    points = (
        _point(4, 100.0),  # peak: 100 -> 0%
        _point(3, 80.0),   # -20%
        _point(2, 120.0),  # new peak: 120 -> 0%
        _point(1, 90.0),   # -25% from the NEW peak (120), not the old one
    )
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert [round(p.drawdown_pct, 4) for p in result] == [0.0, -20.0, 0.0, -25.0]


def test_drawdown_history_recovery_back_to_the_original_peak():
    points = (
        _point(4, 100.0),  # peak: 100 -> 0%
        _point(3, 50.0),   # -50%
        _point(2, 100.0),  # back to the SAME peak, not a new one -> 0%
    )
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert [round(p.drawdown_pct, 4) for p in result] == [0.0, -50.0, 0.0]


def test_drawdown_history_zero_peak_is_handled_defensively_not_a_division_error():
    """A non-positive running peak should not occur for a real
    portfolio_snapshots row, but is handled defensively -- 0.0, never a
    ZeroDivisionError or a fabricated value."""
    points = (_point(1, 0.0), _point(0, 0.0))
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert [p.drawdown_pct for p in result] == [0.0, 0.0]


def test_drawdown_history_of_empty_points_is_empty():
    assert PortfolioIntelligenceUI._compute_portfolio_drawdown_history(()) == ()


def test_drawdown_history_preserves_portfolio_value_and_as_of_verbatim():
    points = (_point(0, 12345.67),)
    result = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
    assert result[0].as_of == points[0].as_of
    assert result[0].portfolio_value == 12345.67


def test_drawdown_summary_none_for_empty_points():
    assert PortfolioIntelligenceUI._compute_drawdown_summary(()) is None


def test_drawdown_summary_current_is_the_most_recent_points_own_drawdown():
    points = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(
        (_point(2, 100.0), _point(1, 80.0), _point(0, 90.0)),
    )
    summary = PortfolioIntelligenceUI._compute_drawdown_summary(points)
    assert round(summary["current_drawdown_pct"], 4) == -10.0


def test_drawdown_summary_max_is_the_deepest_drawdown_in_the_window():
    points = PortfolioIntelligenceUI._compute_portfolio_drawdown_history(
        (_point(2, 100.0), _point(1, 60.0), _point(0, 90.0)),
    )
    summary = PortfolioIntelligenceUI._compute_drawdown_summary(points)
    assert round(summary["max_drawdown_pct"], 4) == -40.0
    assert round(summary["current_drawdown_pct"], 4) == -10.0


def test_format_drawdown_summary_html_is_empty_string_for_none():
    assert PortfolioIntelligenceUI._format_drawdown_summary_html(None) == ""


def test_format_drawdown_summary_html_shows_both_fields():
    summary = {"current_drawdown_pct": -5.5, "max_drawdown_pct": -12.25}
    out = PortfolioIntelligenceUI._format_drawdown_summary_html(summary)
    assert "Current Drawdown" in out and "-5.50%" in out
    assert "Max Drawdown" in out and "-12.25%" in out
    assert 'class="pi-capital-summary"' in out


# --- Visual Dashboard Phase B: drawdown timeframe behavior ----------------
# Reuses the SAME _filter_history_by_timeframe function Phase A's value
# chart uses (duck-typed on `.as_of`) -- these tests prove the drawdown
# chart follows the identical selected timeframe, computed from the TRUE
# all-time peak before any filtering, never a peak reset by the window.


def test_drawdown_render_state_follows_the_selected_timeframe():
    points = (_point(400, 100.0), _point(200, 50.0), _point(0, 100.0))
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._drawdown_render_state(points, None, "1D")
    )
    assert message_visible is False
    assert chart_visible is True
    # Only the most recent point (0 days ago) falls inside "1D" -- its
    # drawdown is 0% (a new all-time peak), NOT recomputed relative to a
    # window-local peak.
    assert list(chart_df["drawdown_pct"]) == [0.0]


def test_drawdown_render_state_uses_the_true_all_time_peak_not_a_window_local_one():
    """The classic case this design exists to get right: a deep historical
    drawdown from an all-time peak, still correctly shown when the
    selected window only covers the recovery, not the original peak."""
    points = (
        _point(400, 200.0),  # true all-time peak
        _point(200, 100.0),  # -50% from the true peak
        _point(5, 150.0),    # still recovering: -25% from the TRUE peak
        _point(0, 160.0),    # -20% from the TRUE peak
    )
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._drawdown_render_state(points, None, "1W")
    )
    assert chart_visible is True
    # "1W" keeps only the last two points -- their drawdown is still
    # relative to the 200.0 all-time peak, never a peak reset to 150.0.
    assert [round(v, 4) for v in chart_df["drawdown_pct"]] == [-25.0, -20.0]


def test_drawdown_render_state_unavailable_when_history_is_none():
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._drawdown_render_state(None, None, "ALL")
    )
    assert message_visible is True
    assert _DRAWDOWN_UNAVAILABLE_MESSAGE in message
    assert chart_visible is False
    assert summary == ""


def test_drawdown_render_state_empty_when_history_has_zero_rows():
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._drawdown_render_state((), None, "ALL")
    )
    assert message_visible is True
    assert _DRAWDOWN_EMPTY_MESSAGE in message
    assert chart_visible is False


def test_drawdown_render_state_insufficient_for_timeframe_is_honest_and_distinct():
    old_point = _point(400, 100.0)
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._drawdown_render_state((old_point,), None, "1D")
    )
    assert message_visible is True
    assert _DRAWDOWN_NO_DATA_FOR_TIMEFRAME_MESSAGE in message
    assert _DRAWDOWN_EMPTY_MESSAGE not in message
    assert chart_visible is False


def test_drawdown_render_state_single_point_history_is_a_valid_new_peak():
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._drawdown_render_state((_point(0, 500.0),), None, "ALL")
    )
    assert chart_visible is True
    assert list(chart_df["drawdown_pct"]) == [0.0]
    assert "Current Drawdown" in summary


# --- Visual Dashboard Phase B: drawdown chart rendering -------------------


def test_drawdown_section_renders_the_chart_message_and_disclaimer():
    points = (_point(3, 100.0), _point(2, 90.0), _point(1, 80.0), _point(0, 100.0))
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=points))
    demo = ui.build()

    chart = _drawdown_chart(demo)
    assert chart.visible is True
    assert set(chart.value["columns"]) == {"as_of", "drawdown_pct"}
    combined = "\n".join(_html_values(demo))
    assert _DRAWDOWN_DISCLAIMER in combined
    assert "Drawdown" in combined


def test_drawdown_section_unavailable_message_and_hidden_chart():
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=None))
    demo = ui.build()

    assert any(_DRAWDOWN_UNAVAILABLE_MESSAGE in v for v in _html_values(demo))
    assert _drawdown_chart(demo).visible is False


def test_drawdown_section_empty_message_and_hidden_chart():
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=()))
    demo = ui.build()

    assert any(_DRAWDOWN_EMPTY_MESSAGE in v for v in _html_values(demo))
    assert _drawdown_chart(demo).visible is False


def test_drawdown_summary_renders_alongside_the_value_summary():
    points = (_point(2, 100.0), _point(1, 60.0), _point(0, 90.0))
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=points))
    demo = ui.build()

    value_summaries = _summary_html_values(demo)
    drawdown_summaries = _drawdown_summary_html_values(demo)
    assert len(value_summaries) == 1
    assert len(drawdown_summaries) == 1
    assert "-40.00%" in drawdown_summaries[0].value  # max drawdown
    assert "-10.00%" in drawdown_summaries[0].value  # current drawdown


def test_drawdown_never_uses_predictive_or_causal_language():
    """Task guardrail: the drawdown SUMMARY/chart values -- as opposed to
    _DRAWDOWN_DISCLAIMER's own explanatory sentence, which legitimately
    names and negates these exact words ("...does not predict, imply, or
    measure future risk") -- must never imply prediction, causality, or
    future risk."""
    points = (_point(2, 100.0), _point(1, 60.0), _point(0, 90.0))
    summary_html = PortfolioIntelligenceUI._format_drawdown_summary_html(
        PortfolioIntelligenceUI._compute_drawdown_summary(
            PortfolioIntelligenceUI._compute_portfolio_drawdown_history(points)
        )
    )
    lowered = summary_html.lower()
    for forbidden in (
        "predict", "will ", "forecast", "expected to", "likely to", "risk of future",
    ):
        assert forbidden not in lowered


# --- Visual Dashboard Phase B: allocation by holding ----------------------


def _holding_allocation_html_values(demo):
    return [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
        and 'class="pi-holding-allocation-list"' in b.value
    ]


def test_holding_allocation_renders_symbol_and_percentage():
    holdings = (
        _make_holding(symbol="AAPL", quantity=10.0, weight_pct=60.0),
        _make_holding(symbol="MSFT", quantity=5.0, weight_pct=40.0),
    )
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital(), holdings=holdings))
    demo = ui.build()

    blocks = _holding_allocation_html_values(demo)
    assert len(blocks) == 1
    assert "AAPL" in blocks[0].value and "60.0%" in blocks[0].value
    assert "MSFT" in blocks[0].value and "40.0%" in blocks[0].value


def test_holding_allocation_is_ordered_by_weight_descending_deterministically():
    holdings = (
        _make_holding(symbol="ZZZZ", weight_pct=10.0),
        _make_holding(symbol="AAAA", weight_pct=50.0),
        _make_holding(symbol="MMMM", weight_pct=10.0),  # tie with ZZZZ -> alpha order
    )
    out = PortfolioIntelligenceUI._format_holding_allocation_html(holdings)
    assert out.index("AAAA") < out.index("MMMM") < out.index("ZZZZ")


def test_holding_allocation_uses_the_existing_authoritative_weight_pct_verbatim():
    """No new valuation/recomputation -- the exact same weight_pct value
    Holdings' own table column already renders."""
    holdings = (_make_holding(symbol="AAPL", weight_pct=33.333),)
    out = PortfolioIntelligenceUI._format_holding_allocation_html(holdings)
    assert "33.3%" in out  # one decimal place, matches the Holdings table


def test_holding_allocation_empty_is_honest():
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital(), holdings=()))
    demo = ui.build()

    assert _holding_allocation_html_values(demo) == []
    assert any("No holdings recorded yet." in v for v in _html_values(demo))


def test_holding_allocation_unavailable_is_honest():
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital(), holdings=None))
    demo = ui.build()

    assert _holding_allocation_html_values(demo) == []
    assert any(_HOLDINGS_UNAVAILABLE_MESSAGE in v for v in _html_values(demo))


def test_holding_allocation_bar_width_is_clamped_to_a_valid_percentage():
    """Defensive clamp on the visual bar width only -- never on the
    displayed text, which always states the real weight_pct verbatim."""
    holdings = (_make_holding(symbol="AAPL", weight_pct=100.0),)
    out = PortfolioIntelligenceUI._format_holding_allocation_html(holdings)
    assert "width:100.0%" in out
    assert "100.0%" in out


# --- Visual Dashboard Phase A: rendered chart/message/summary states -----


def _summary_html_values(demo):
    """The Portfolio Value chart's own summary card specifically -- scoped
    by its "Current Value" label, since Visual Dashboard Phase B added a
    second .pi-capital-summary-classed card (the drawdown summary, "Current
    Drawdown"/"Max Drawdown" -- see _drawdown_summary_html_values below),
    and Capital Summary / Alpaca Account already share this same class too."""
    return [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
        and 'class="pi-capital-summary"' in b.value
        and "Current Value" in b.value
    ]


def _drawdown_summary_html_values(demo):
    return [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
        and 'class="pi-capital-summary"' in b.value
        and "Current Drawdown" in b.value
    ]


def test_timeframe_selector_offers_the_eight_required_choices():
    demo = PortfolioIntelligenceUI().build()
    radios = [b for b in demo.blocks.values() if isinstance(b, gr.Radio)]
    assert len(radios) == 1
    assert [label for label, _value in radios[0].choices] == _TIMEFRAME_CHOICES
    assert radios[0].value == _DEFAULT_TIMEFRAME


def test_summary_renders_for_a_populated_history_at_the_default_all_timeframe():
    points = (_point(400, 90000.0), _point(0, 100029.85))
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=points))
    demo = ui.build()

    summaries = _summary_html_values(demo)
    assert len(summaries) == 1
    assert "$90,000.00" in summaries[0].value  # starting (ALL = full history)
    assert "$100,029.85" in summaries[0].value  # current


def test_summary_is_empty_when_history_unavailable():
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=None))
    demo = ui.build()

    assert _summary_html_values(demo) == []


def test_summary_is_empty_when_history_is_globally_empty():
    ui = PortfolioIntelligenceUI(PortfolioScreen(portfolio_history=()))
    demo = ui.build()

    assert _summary_html_values(demo) == []


def test_history_render_state_insufficient_for_timeframe_is_honest_and_distinct():
    """Real, non-empty history exists, but none of it falls inside the
    selected timeframe's window -- a distinct message from the
    zero-rows-total empty state, never silently reused from it."""
    old_point = _point(400, 100.0)  # well outside any window but ALL/1Y
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._history_render_state((old_point,), None, "1D")
    )
    assert message_visible is True
    assert _PORTFOLIO_HISTORY_NO_DATA_FOR_TIMEFRAME_MESSAGE in message
    assert _PORTFOLIO_HISTORY_EMPTY_MESSAGE not in message
    assert chart_visible is False
    assert summary == ""


def test_history_render_state_populated_for_a_timeframe_with_matching_points():
    points = (_point(400, 1.0), _point(0, 2.0))
    message, message_visible, chart_df, chart_visible, summary = (
        PortfolioIntelligenceUI()._history_render_state(points, None, "1D")
    )
    assert message_visible is False
    assert chart_visible is True
    assert list(chart_df["portfolio_value"]) == [2.0]
    assert "Current Value" in summary


# --- Visual Dashboard Phase A: timeframe change event (no re-fetch) ------


def test_on_timeframe_change_filters_the_state_held_history_not_a_new_fetch():
    ui = PortfolioIntelligenceUI()
    points = (_point(400, 1.0), _point(0, 2.0))

    (
        message_update, chart_update, summary_update,
        drawdown_message_update, drawdown_chart_update, drawdown_summary_update,
    ) = ui._on_timeframe_change("1D", (points, None))

    assert chart_update["visible"] is True
    assert list(chart_update["value"]["portfolio_value"]) == [2.0]
    assert message_update["visible"] is False
    assert "Current Value" in summary_update["value"]
    # drawdown is re-filtered from the SAME state-held history, no re-fetch.
    assert drawdown_chart_update["visible"] is True
    assert list(drawdown_chart_update["value"]["drawdown_pct"]) == [0.0]
    assert drawdown_message_update["visible"] is False
    assert "Current Drawdown" in drawdown_summary_update["value"]


def test_on_timeframe_change_honors_unavailable_health():
    ui = PortfolioIntelligenceUI()
    health = IntegrationHealth.not_configured("trades_db_portfolio_history")

    (
        message_update, chart_update, summary_update,
        drawdown_message_update, drawdown_chart_update, drawdown_summary_update,
    ) = ui._on_timeframe_change("ALL", (None, health))

    assert message_update["visible"] is True
    assert chart_update["visible"] is False
    assert summary_update["value"] == ""
    assert drawdown_message_update["visible"] is True
    assert drawdown_chart_update["visible"] is False
    assert drawdown_summary_update["value"] == ""


def test_timeframe_change_event_only_touches_the_six_history_outputs():
    """Regression guard: the timeframe selector must never be wired to
    Capital Summary, Holdings, allocation-by-holding, Alpaca, or
    reconciliation outputs -- only the value-chart and drawdown-chart
    message/chart/summary sextet changing timeframe actually affects."""
    demo = PortfolioIntelligenceUI().build()

    radio_id = next(
        bid for bid, block in demo.blocks.items() if isinstance(block, gr.Radio)
    )
    change_dep = next(
        dep for dep in demo.config["dependencies"]
        if dep["targets"] == [(radio_id, "change")]
    )
    assert len(change_dep["outputs"]) == 6


def test_render_with_explicit_timeframe_filters_the_chart():
    points = (_point(400, 1.0), _point(0, 2.0))
    ui = PortfolioIntelligenceUI(screen_provider=lambda: PortfolioScreen(portfolio_history=points))

    updates = ui._render(timeframe="1D")

    chart_update = updates[8]  # see build()'s outputs ordering
    assert list(chart_update["value"]["portfolio_value"]) == [2.0]


def test_render_default_timeframe_is_all_full_history_unchanged():
    """No explicit timeframe passed (existing call sites, existing tests)
    -> ALL -> byte-identical full-history behavior to before this feature
    existed."""
    points = (_point(400, 1.0), _point(200, 2.0), _point(0, 3.0))
    ui = PortfolioIntelligenceUI(screen_provider=lambda: PortfolioScreen(portfolio_history=points))

    updates = ui._render()

    chart_update = updates[8]
    assert list(chart_update["value"]["portfolio_value"]) == [1.0, 2.0, 3.0]


def test_render_history_state_is_refreshed_with_the_latest_fetch():
    points = (_point(0, 42.0),)
    ui = PortfolioIntelligenceUI(screen_provider=lambda: PortfolioScreen(portfolio_history=points))

    updates = ui._render()

    history_state_update = updates[19]  # see build()'s outputs ordering
    assert history_state_update["value"][0] == points


# --- ADR-061 A4: per-section IntegrationHealth in the unavailable state ---


def test_capital_not_configured_health_renders_a_not_configured_message():
    screen = PortfolioScreen(
        capital=None,
        capital_health=IntegrationHealth.not_configured("trades_db_capital"),
        holdings=None,
        holdings_health=IntegrationHealth.not_configured("trades_db_positions"),
    )
    html_text, table_cells = _rendered_surfaces(PortfolioIntelligenceUI(screen=screen))

    assert "not configured for this environment" in html_text
    assert "aara-integration-status" in html_text
    assert table_cells == []


def test_alpaca_health_reason_is_named_in_the_alpaca_sections():
    screen = PortfolioScreen(
        capital=_make_capital(),
        alpaca_account=None,
        alpaca_health=IntegrationHealth.auth_failed("alpaca_paper"),
        alpaca_orders=None,
        alpaca_orders_health=IntegrationHealth.unavailable("alpaca_paper_orders"),
    )
    html_text, _ = _rendered_surfaces(PortfolioIntelligenceUI(screen=screen))

    assert "authentication failed" in html_text          # account/positions section
    assert "provider could not be reached" in html_text  # recent-orders section


def test_unavailable_sections_render_no_fabricated_numeric_data():
    """ADR-061 Section 2.5: a non-HEALTHY section must not be replaced by
    fabricated / defaulted / zero-valued figures."""
    from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import (
        build_mock_screen,
    )

    mock = build_mock_screen()
    screen = PortfolioScreen(
        capital=None,
        capital_health=IntegrationHealth.auth_failed("trades_db_capital"),
        holdings=None,
        holdings_health=IntegrationHealth.unavailable("trades_db_positions"),
        alpaca_health=IntegrationHealth.not_configured("alpaca_paper"),
        alpaca_orders_health=IntegrationHealth.not_configured("alpaca_paper_orders"),
    )
    html_text, table_cells = _rendered_surfaces(PortfolioIntelligenceUI(screen=screen))

    assert table_cells == []
    assert "$" not in html_text
    for marker in ("pi-capital-summary", "pi-allocation-bar", "pi-holdings-table"):
        assert marker not in html_text
    for fabricated in (
        f"${mock.capital.allocated_amount:,.2f}",
        f"${mock.capital.available_cash:,.2f}",
    ):
        assert fabricated not in html_text


def test_health_none_still_renders_the_fixed_fallback_message():
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=None, holdings=None))

    html_text, _ = _rendered_surfaces(ui)

    assert html_text.count(_CAPITAL_UNAVAILABLE_MESSAGE) == 2  # summary + allocation
    assert _HOLDINGS_UNAVAILABLE_MESSAGE in html_text


# --- PARTIAL state (real capital, holdings unavailable) ------------


def test_partial_state_renders_real_capital_and_holdings_unavailable_and_partial_banner():
    real_capital = _make_capital(
        allocated_amount=96933.32, available_cash=38850.78,
        invested_amount=58082.54, reserve=0.0, realized_profit=0.0,
    )
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=real_capital, holdings=None))

    demo = ui.build()
    combined = "\n".join(_html_values(demo))

    assert "$96,933.32" in combined
    assert "$38,850.78" in combined
    assert _HOLDINGS_UNAVAILABLE_MESSAGE in combined
    assert _PARTIAL_DATA_HTML in combined
    assert _REAL_DATA_HTML not in combined
    assert _UNAVAILABLE_DATA_HTML not in combined
    assert _visible_dataframes(demo) == []


def test_derived_allocation_values_render_correctly_for_a_real_capital_screen():
    real_capital = _make_capital(available_cash=250.0, invested_amount=750.0)
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=real_capital, holdings=None))

    combined = "\n".join(_html_values(ui.build()))

    assert "Invested 75.0%" in combined
    assert "Cash 25.0%" in combined


# --- REAL and EMPTY states -----------------------------------------


def test_disclosure_is_the_real_data_variant_when_capital_and_holdings_are_both_real():
    real_capital = _make_capital()
    holding = PortfolioHolding(
        symbol="AAPL", quantity=19.11, price=334.67, market_value=6396.0, weight_pct=100.0,
    )
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=real_capital, holdings=(holding,)))

    html_values = _html_values(ui.build())

    assert _REAL_DATA_HTML in html_values
    assert _PARTIAL_DATA_HTML not in html_values
    assert _UNAVAILABLE_DATA_HTML not in html_values


def test_real_holdings_render_the_real_price_and_market_value_not_entry_price():
    real_capital = _make_capital()
    holding = PortfolioHolding(
        symbol="AAPL", quantity=19.11, price=334.67, market_value=6396.0359, weight_pct=100.0,
    )
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=real_capital, holdings=(holding,)))

    demo = ui.build()
    holdings_tables = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Dataframe) and "pi-holdings-table" in (b.elem_classes or [])
    ]
    assert len(holdings_tables) == 1
    assert holdings_tables[0].value["data"] == [["AAPL", "19.11", "$334.67", "$6,396.04", "100.0%"]]


def test_real_holdings_can_be_empty_with_the_real_data_disclosure():
    """A real open-position source reporting zero positions is a genuine
    EMPTY state -- the empty-state message renders under the real-data
    disclosure, never a table and never the unavailable state."""
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital(), holdings=()))

    demo = ui.build()
    html_values = _html_values(demo)

    assert _visible_dataframes(demo) == []
    assert _REAL_DATA_HTML in html_values
    assert any("No holdings recorded yet." in value for value in html_values)
    assert not any(_HOLDINGS_UNAVAILABLE_MESSAGE in value for value in html_values)


def test_empty_state_message_helper_still_reads_the_screens_own_message():
    screen = PortfolioScreen(capital=_make_capital(), holdings=())

    empty_html = PortfolioIntelligenceUI._format_empty_message_html(screen)

    # B3 Tier 1: shared .aara-empty is wired alongside the local class.
    assert 'class="pi-empty-message aara-empty"' in empty_html
    assert "No holdings recorded yet." in empty_html


# --- Alpaca Paper Account (alpaca_paper_source) pass -----------------


def test_alpaca_section_shows_unavailable_message_by_default():
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital()))

    html_values = _html_values(ui.build())
    assert any(_ALPACA_UNAVAILABLE_MESSAGE in value for value in html_values)


def test_alpaca_badge_is_always_present_regardless_of_availability():
    """Phase 4 safety requirement: the 'ALPACA PAPER' label must always be
    visible in the section header, whether or not real data is available,
    so the section can never be mistaken for anything else."""
    ui = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital()))

    html_values = _html_values(ui.build())
    assert any(_ALPACA_PAPER_BADGE_TEXT in value for value in html_values)


def test_alpaca_account_and_positions_render_when_available():
    account = _make_alpaca_account()
    position = AlpacaPosition(
        symbol="AAPL", quantity=19.111355, avg_entry_price=315.012151, current_price=310.21,
        market_value=5928.533435, unrealized_pl=-91.775612, unrealized_plpc=-0.01524, side="long",
    )
    screen = PortfolioScreen(
        capital=_make_capital(), alpaca_account=account, alpaca_positions=(position,),
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    html_values = _html_values(demo)
    combined = "\n".join(html_values)
    assert "$100,018.33" in combined  # equity
    assert "$59,869.06" in combined  # cash
    assert "$351,894.19" in combined  # buying power
    assert not any(_ALPACA_UNAVAILABLE_MESSAGE in v for v in html_values)

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    alpaca_tables = [d for d in dataframes if "pi-alpaca-positions-table" in d.elem_classes]
    assert len(alpaca_tables) == 1
    assert alpaca_tables[0].value["data"] == [
        ["AAPL", "19.1114", "$315.01", "$310.21", "$5,928.53", "$-91.78", "-1.52%", "long"],
    ]


def test_alpaca_section_shows_empty_message_when_connected_with_zero_positions():
    screen = PortfolioScreen(
        capital=_make_capital(), alpaca_account=_make_alpaca_account(), alpaca_positions=(),
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    html_values = _html_values(demo)
    dataframes = _visible_dataframes(demo)
    alpaca_tables = [d for d in dataframes if "pi-alpaca-positions-table" in d.elem_classes]
    assert alpaca_tables == []
    assert any("Alpaca Paper account has no open positions." in v for v in html_values)
    assert not any(_ALPACA_UNAVAILABLE_MESSAGE in v for v in html_values)


def test_alpaca_section_is_independent_of_the_capital_holdings_disclosure_state():
    """The Alpaca section renders on its own availability regardless of
    the Capital Summary/Holdings disclosure state -- here the page is
    PARTIAL (real capital, holdings unavailable) and the Alpaca account
    section still renders its own empty state."""
    screen = PortfolioScreen(
        capital=_make_capital(), holdings=None,
        alpaca_account=_make_alpaca_account(), alpaca_positions=(),
    )
    html_values = _html_values(PortfolioIntelligenceUI(screen=screen).build())

    assert _PARTIAL_DATA_HTML in html_values
    assert any(_ALPACA_PAPER_BADGE_TEXT in v for v in html_values)
    assert any("Alpaca Paper account has no open positions." in v for v in html_values)


# --- Alpaca Paper Recent Orders (alpaca_paper_orders_source) pass -----


def _make_order(**overrides):
    defaults = dict(
        order_id="ord-abc-123",
        symbol="AAPL",
        side="buy",
        order_type="limit",
        quantity="10",
        filled_quantity="4",
        status="partially_filled",
        submitted_at=datetime(2026, 8, 27, 19, 30, tzinfo=timezone.utc),
        filled_at=None,
        limit_price="321.50",
        is_working=True,
    )
    defaults.update(overrides)
    return AlpacaOrder(**defaults)


def _orders_dataframe(demo):
    return [
        block
        for block in demo.blocks.values()
        if isinstance(block, gr.Dataframe)
        and "pi-alpaca-orders-table" in (block.elem_classes or [])
        and getattr(block, "visible", True)
    ]


def test_orders_section_shows_unavailable_message_by_default():
    demo = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital())).build()

    html_values = _html_values(demo)
    assert any(_ALPACA_ORDERS_UNAVAILABLE_MESSAGE in v for v in html_values)
    assert _orders_dataframe(demo) == []


def test_orders_section_header_always_carries_the_alpaca_paper_badge():
    demo = PortfolioIntelligenceUI(PortfolioScreen(capital=_make_capital())).build()

    combined = "\n".join(_html_values(demo))
    assert "Recent Orders" in combined
    assert combined.count(f">{_ALPACA_PAPER_BADGE_TEXT}<") >= 2


def test_orders_section_carries_the_not_linked_to_decision_center_caption_in_every_state():
    """UI hardening pass: the Recent Orders section is a broker-side
    observation only -- there is no decision->order linkage anywhere in
    this product -- so the caption must render unconditionally, in the
    unavailable / empty / populated states alike."""
    unavailable = PortfolioIntelligenceUI(
        PortfolioScreen(capital=_make_capital())
    ).build()
    empty = PortfolioIntelligenceUI(
        PortfolioScreen(
            capital=_make_capital(),
            alpaca_orders=AlpacaOrdersSnapshot(orders=(), truncated=False),
        )
    ).build()
    populated = PortfolioIntelligenceUI(
        PortfolioScreen(
            capital=_make_capital(),
            alpaca_orders=AlpacaOrdersSnapshot(orders=(_make_order(),), truncated=False),
        )
    ).build()

    for demo in (unavailable, empty, populated):
        assert any(_ALPACA_ORDERS_SCOPE_CAPTION in v for v in _html_values(demo))
    assert "Not linked to Decision Center." in _ALPACA_ORDERS_SCOPE_CAPTION


def test_orders_section_shows_empty_message_when_connected_with_zero_orders():
    screen = PortfolioScreen(
        capital=_make_capital(), alpaca_orders=AlpacaOrdersSnapshot(orders=(), truncated=False),
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    html_values = _html_values(demo)
    assert any("Alpaca Paper account has no recent orders." in v for v in html_values)
    assert not any(_ALPACA_ORDERS_UNAVAILABLE_MESSAGE in v for v in html_values)
    assert _orders_dataframe(demo) == []


def test_orders_render_in_a_dataframe_with_verbatim_side_and_status():
    order = _make_order(side="sell", status="pending_new", is_working=True)
    screen = PortfolioScreen(
        capital=_make_capital(),
        alpaca_orders=AlpacaOrdersSnapshot(orders=(order,), truncated=False),
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    tables = _orders_dataframe(demo)
    assert len(tables) == 1
    row = tables[0].value["data"][0]
    assert row[1] == "AAPL"
    assert row[2] == "sell"                       # broker-verbatim
    assert row[3] == "limit"
    assert row[4] == "10"
    assert row[5] == "4"
    assert row[6] == "321.50"
    assert row[7] == "pending_new"                # broker-verbatim, unaltered
    assert row[8] == _ALPACA_ORDERS_WORKING_MARKER
    assert row[9] == ""                           # no filled_at
    assert "CDT" in row[0] or "CST" in row[0]     # America/Chicago display


def test_non_working_order_has_an_empty_working_cell():
    order = _make_order(status="filled", is_working=False, filled_quantity="10",
                        filled_at=datetime(2026, 8, 27, 19, 45, tzinfo=timezone.utc))
    screen = PortfolioScreen(
        capital=_make_capital(),
        alpaca_orders=AlpacaOrdersSnapshot(orders=(order,), truncated=False),
    )

    demo = PortfolioIntelligenceUI(screen=screen).build()

    row = _orders_dataframe(demo)[0].value["data"][0]
    assert row[7] == "filled"
    assert row[8] == ""


def test_order_id_is_never_rendered_as_a_cell():
    order = _make_order(order_id="ord-should-not-appear-xyz")
    screen = PortfolioScreen(
        capital=_make_capital(),
        alpaca_orders=AlpacaOrdersSnapshot(orders=(order,), truncated=False),
    )

    demo = PortfolioIntelligenceUI(screen=screen).build()

    rendered = "\n".join(str(v) for v in _orders_dataframe(demo)[0].value["data"])
    assert "ord-should-not-appear-xyz" not in rendered


def test_truncation_note_is_shown_only_when_snapshot_is_truncated():
    order = _make_order()
    truncated_screen = PortfolioScreen(
        capital=_make_capital(),
        alpaca_orders=AlpacaOrdersSnapshot(orders=(order,), truncated=True),
    )
    not_truncated_screen = PortfolioScreen(
        capital=_make_capital(),
        alpaca_orders=AlpacaOrdersSnapshot(orders=(order,), truncated=False),
    )

    truncated_html = "\n".join(_html_values(PortfolioIntelligenceUI(screen=truncated_screen).build()))
    plain_html = "\n".join(_html_values(PortfolioIntelligenceUI(screen=not_truncated_screen).build()))

    assert _ALPACA_ORDERS_TRUNCATION_NOTE in truncated_html
    assert _ALPACA_ORDERS_TRUNCATION_NOTE not in plain_html


def test_orders_section_is_independent_of_account_and_disclosure_state():
    """Orders can be available while the Alpaca account section is
    unavailable and the Capital/Holdings page state is PARTIAL."""
    screen = PortfolioScreen(
        capital=_make_capital(),
        holdings=None,
        alpaca_account=None,
        alpaca_orders=AlpacaOrdersSnapshot(orders=(_make_order(),), truncated=False),
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    html_values = _html_values(demo)
    assert _PARTIAL_DATA_HTML in html_values
    assert any(_ALPACA_UNAVAILABLE_MESSAGE in v for v in html_values)   # account section
    assert len(_orders_dataframe(demo)) == 1                            # orders section
    assert not any(_ALPACA_ORDERS_UNAVAILABLE_MESSAGE in v for v in html_values)


# --- Internal vs Alpaca PAPER reconciliation ---------------------------


def _reconciliation_dataframe(demo):
    return [
        block
        for block in demo.blocks.values()
        if isinstance(block, gr.Dataframe)
        and "pi-reconciliation-table" in (block.elem_classes or [])
        and getattr(block, "visible", True)
    ]


def _make_alpaca_position(**overrides):
    defaults = dict(
        symbol="ZZZZ", quantity=1.0, avg_entry_price=1.0, current_price=1.0,
        market_value=1.0, unrealized_pl=0.0, unrealized_plpc=0.0, side="long",
    )
    defaults.update(overrides)
    return AlpacaPosition(**defaults)


def _make_reconciliation_row(**overrides):
    defaults = dict(symbol="ZZZZ", status=ReconciliationStatus.MATCHED)
    defaults.update(overrides)
    return ReconciliationRow(**defaults)


def _reconciliation_screen(reconciliation, *, holdings=(), alpaca_positions=()):
    """`reconciliation` is the already-computed tuple this screen carries
    (see bootstrap.py's _compute_portfolio_reconciliation) -- gradio_view.py
    only renders it, it never derives it from holdings/alpaca_positions
    itself, so these tests set it directly, matching how every other
    already-derived screen field (e.g. RiskScreen.drawdown_history) is
    tested at this layer."""
    return PortfolioScreen(
        capital=_make_capital(),
        holdings=holdings,
        alpaca_account=_make_alpaca_account(),
        alpaca_positions=alpaca_positions,
        reconciliation=reconciliation,
    )


def test_reconciliation_matched_when_quantities_agree_exactly():
    row = _make_reconciliation_row(
        symbol="AAPL", status=ReconciliationStatus.MATCHED,
        internal_quantity=10.0, alpaca_quantity=10.0, quantity_difference=0.0,
        internal_market_value=1.0, alpaca_market_value=1.0,
    )
    screen = _reconciliation_screen((row,))
    demo = PortfolioIntelligenceUI(screen=screen).build()

    tables = _reconciliation_dataframe(demo)
    assert len(tables) == 1
    assert tables[0].value["data"] == [
        ["AAPL", "MATCHED", "10", "10", "0", "$1.00", "$1.00"],
    ]
    combined = "\n".join(_html_values(demo))
    assert "1 matched" in combined
    assert "0 quantity difference" in combined


def test_reconciliation_quantity_difference_when_quantities_disagree():
    row = _make_reconciliation_row(
        symbol="AAPL", status=ReconciliationStatus.QUANTITY_DIFFERENCE,
        internal_quantity=10.0, alpaca_quantity=6.0, quantity_difference=4.0,
        internal_market_value=1.0, alpaca_market_value=1.0,
    )
    screen = _reconciliation_screen((row,))
    demo = PortfolioIntelligenceUI(screen=screen).build()

    tables = _reconciliation_dataframe(demo)
    assert tables[0].value["data"] == [
        ["AAPL", "QUANTITY DIFFERENCE", "10", "6", "4", "$1.00", "$1.00"],
    ]
    combined = "\n".join(_html_values(demo))
    assert "1 quantity difference" in combined


def test_reconciliation_internal_only_when_absent_from_alpaca():
    row = _make_reconciliation_row(
        symbol="BAC", status=ReconciliationStatus.INTERNAL_ONLY,
        internal_quantity=5.0, internal_market_value=1.0,
    )
    screen = _reconciliation_screen((row,))
    demo = PortfolioIntelligenceUI(screen=screen).build()

    tables = _reconciliation_dataframe(demo)
    assert tables[0].value["data"] == [
        ["BAC", "INTERNAL ONLY", "5", "", "", "$1.00", ""],
    ]
    combined = "\n".join(_html_values(demo))
    assert "1 internal only" in combined


def test_reconciliation_broker_only_when_absent_internally():
    row = _make_reconciliation_row(
        symbol="TSLA", status=ReconciliationStatus.BROKER_ONLY,
        alpaca_quantity=3.0, alpaca_market_value=1.0,
    )
    screen = _reconciliation_screen((row,))
    demo = PortfolioIntelligenceUI(screen=screen).build()

    tables = _reconciliation_dataframe(demo)
    assert tables[0].value["data"] == [
        ["TSLA", "BROKER ONLY", "", "3", "", "", "$1.00"],
    ]
    combined = "\n".join(_html_values(demo))
    assert "1 broker only" in combined


def test_reconciliation_multiple_symbols_are_ordered_alphabetically():
    """Rendering preserves whatever order the screen's own reconciliation
    tuple already carries -- bootstrap.py's _compute_portfolio_
    reconciliation is what establishes the alphabetical order (see the
    bootstrap-level test), this only proves the view does not reshuffle it."""
    rows = (
        _make_reconciliation_row(symbol="AAPL", status=ReconciliationStatus.MATCHED),
        _make_reconciliation_row(symbol="MSFT", status=ReconciliationStatus.BROKER_ONLY),
        _make_reconciliation_row(symbol="TSLA", status=ReconciliationStatus.INTERNAL_ONLY),
    )
    screen = _reconciliation_screen(rows)
    demo = PortfolioIntelligenceUI(screen=screen).build()

    tables = _reconciliation_dataframe(demo)
    symbols = [row[0] for row in tables[0].value["data"]]
    assert symbols == ["AAPL", "MSFT", "TSLA"]
    combined = "\n".join(_html_values(demo))
    assert "1 matched" in combined
    assert "1 internal only" in combined
    assert "1 broker only" in combined


def test_reconciliation_empty_when_both_sides_have_no_positions():
    screen = _reconciliation_screen(())
    demo = PortfolioIntelligenceUI(screen=screen).build()

    assert _reconciliation_dataframe(demo) == []
    html_values = _html_values(demo)
    assert any(
        "No internal or Alpaca Paper positions to reconcile." in v for v in html_values
    )


def test_reconciliation_unavailable_when_internal_holdings_unavailable():
    """Holdings unavailable -> reconciliation must not infer a match --
    honest unavailable state, never a fabricated comparison."""
    screen = PortfolioScreen(
        capital=_make_capital(), holdings=None,
        alpaca_account=_make_alpaca_account(),
        alpaca_positions=(_make_alpaca_position(symbol="AAPL"),),
        reconciliation=None,
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    assert _reconciliation_dataframe(demo) == []
    html_values = _html_values(demo)
    assert any(_RECONCILIATION_INTERNAL_UNAVAILABLE_MESSAGE in v for v in html_values)


def test_reconciliation_unavailable_when_alpaca_unavailable():
    """Alpaca account/positions unavailable -> reconciliation must not
    infer a match -- honest unavailable state, never a fabricated
    comparison."""
    screen = PortfolioScreen(
        capital=_make_capital(), holdings=(_make_holding(symbol="AAPL"),),
        alpaca_account=None,
        reconciliation=None,
    )
    demo = PortfolioIntelligenceUI(screen=screen).build()

    assert _reconciliation_dataframe(demo) == []
    html_values = _html_values(demo)
    assert any(_RECONCILIATION_ALPACA_UNAVAILABLE_MESSAGE in v for v in html_values)


def test_reconciliation_section_names_both_views_and_is_scoped_descriptively():
    row = _make_reconciliation_row(
        symbol="AAPL", status=ReconciliationStatus.MATCHED,
        internal_quantity=1.0, alpaca_quantity=1.0, quantity_difference=0.0,
    )
    screen = _reconciliation_screen((row,))
    demo = PortfolioIntelligenceUI(screen=screen).build()

    combined = "\n".join(_html_values(demo))
    assert "Internal Portfolio" in combined
    assert _ALPACA_PAPER_BADGE_TEXT in combined
    assert _RECONCILIATION_SCOPE_CAPTION in combined


def test_reconciliation_never_uses_risk_error_health_or_opportunity_language():
    """Task guardrail: the reconciliation SUMMARY and TABLE ROWS -- the
    actual per-position facts, as opposed to _RECONCILIATION_SCOPE_
    CAPTION's own explanatory disclaimer, which legitimately names and
    negates these exact words ("...is not evidence of an error, a risk, or
    a trading opportunity") -- must never label a mismatch a risk, error,
    unhealthy state, trading opportunity, or execution failure."""
    row = _make_reconciliation_row(
        symbol="AAPL", status=ReconciliationStatus.QUANTITY_DIFFERENCE,
        internal_quantity=10.0, alpaca_quantity=6.0, quantity_difference=4.0,
    )
    row_only = "\n".join([
        PortfolioIntelligenceUI._format_reconciliation_summary_html((row,)),
        "\n".join(cell for cell in PortfolioIntelligenceUI._format_reconciliation_rows((row,))[0]),
    ]).lower()

    for forbidden in (
        "risk", "error", "unhealthy", "trading opportunity",
        "execution failure", "tolerance", "health score",
    ):
        assert forbidden not in row_only


def test_reconciliation_row_helper_never_fabricates_a_one_sided_quantity_difference():
    """INTERNAL_ONLY / BROKER_ONLY rows must carry quantity_difference=None
    -- never a fabricated numeric difference against a side that has no
    position at all."""
    from applications.trading_intelligence.bootstrap import (
        _compute_portfolio_reconciliation,
    )

    rows = _compute_portfolio_reconciliation(
        holdings=(_make_holding(symbol="BAC", quantity=5.0),),
        alpaca_positions=(_make_alpaca_position(symbol="TSLA", quantity=3.0),),
    )
    by_symbol = {row.symbol: row for row in rows}
    assert by_symbol["BAC"].status is ReconciliationStatus.INTERNAL_ONLY
    assert by_symbol["BAC"].quantity_difference is None
    assert by_symbol["TSLA"].status is ReconciliationStatus.BROKER_ONLY
    assert by_symbol["TSLA"].quantity_difference is None


def test_default_screen_renders_zero_visible_dataframes():
    """The default (no screen) is fully unavailable: the Holdings, Alpaca
    positions, and Alpaca orders tables are all present in the layout (so
    Refresh can populate them) but hidden -- none is visible."""
    demo = PortfolioIntelligenceUI().build()

    assert _visible_dataframes(demo) == []


# --- Render-time fetch: Refresh button, demo.load, "as of" indicator ----


_OUTPUT_COUNT = 24  # see PortfolioIntelligenceUI.build()'s `outputs` list


def _refresh_button(demo):
    return next(
        block for block in demo.blocks.values()
        if isinstance(block, gr.Button) and "aara-refresh-button" in (block.elem_classes or [])
    )


def _counting_provider(*screens):
    """Returns a provider that yields the given screens in order (repeating
    the last one), plus a mutable call-count list."""
    calls = []
    seq = list(screens)

    def provider():
        calls.append(True)
        idx = min(len(calls) - 1, len(seq) - 1)
        return seq[idx]

    return provider, calls


def test_build_has_a_single_refresh_button_with_the_shared_class():
    demo = PortfolioIntelligenceUI().build()

    buttons = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Button) and "aara-refresh-button" in (b.elem_classes or [])
    ]
    assert len(buttons) == 1


def test_disable_refresh_button_returns_a_not_interactive_update():
    assert PortfolioIntelligenceUI._disable_refresh_button() == {
        "interactive": False, "__type__": "update",
    }


def test_enable_refresh_button_returns_an_interactive_update():
    assert PortfolioIntelligenceUI._enable_refresh_button() == {
        "interactive": True, "__type__": "update",
    }


def test_refresh_click_chain_is_disable_then_render_then_enable():
    """Same disable -> render -> enable double-submit guard chain as
    Decision Center: proves the click().then().then() wiring in build(),
    not just that the helper methods exist."""
    ui = PortfolioIntelligenceUI()
    demo = ui.build()

    refresh_button = _refresh_button(demo)
    refresh_button_id = next(
        bid for bid, block in demo.blocks.items() if block is refresh_button
    )
    disable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is PortfolioIntelligenceUI._disable_refresh_button
    )
    render_dep = next(
        dep for dep in demo.config["dependencies"]
        if dep.get("trigger_after") == disable_dep["id"]
    )
    enable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is PortfolioIntelligenceUI._enable_refresh_button
    )

    assert disable_dep["targets"] == [(refresh_button_id, "click")]
    assert refresh_button_id in disable_dep["outputs"]
    assert demo.fns[render_dep["id"]].fn == ui._render
    assert enable_dep["trigger_after"] == render_dep["id"]
    assert refresh_button_id in enable_dep["outputs"]


def test_demo_load_and_the_refresh_chain_both_call_render():
    ui = PortfolioIntelligenceUI()
    demo = ui.build()

    render_deps = [
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn == ui._render
    ]
    assert len(render_deps) == 2  # demo.load() + the Refresh .then() step


def test_render_returns_one_update_per_dynamic_output():
    updates = PortfolioIntelligenceUI()._render()

    assert len(updates) == _OUTPUT_COUNT
    assert all(u.get("__type__") == "update" for u in updates)


def test_render_reflects_a_fresh_screen_from_the_provider_each_call():
    real = _make_capital(allocated_amount=4321.0)
    provider, calls = _counting_provider(
        PortfolioScreen(),                                   # __init__ snapshot
        PortfolioScreen(capital=real, holdings=(_make_holding(),)),  # 1st _render
    )
    ui = PortfolioIntelligenceUI(screen_provider=provider)

    first = ui._render()
    # disclosure is output index 2 (rendered-at, snapshot line, then disclosure)
    assert first[2]["value"] == _REAL_DATA_HTML

    second = ui._render()  # provider now repeats the last screen
    assert second[2]["value"] == _REAL_DATA_HTML
    assert len(calls) == 3  # 1 in __init__ + 2 explicit _render calls


def test_render_preserves_unavailable_states_with_no_mock_fallback():
    """A provider that returns an all-unavailable screen collapses every
    section back to its explicit unavailable state -- never mock data."""
    from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import (
        build_mock_screen,
    )

    ui = PortfolioIntelligenceUI(screen_provider=PortfolioScreen)
    updates = ui._render()

    rendered_at, snapshot, disclosure, capital_summary, allocation, \
        holdings_msg, holdings_tbl, portfolio_history_msg, portfolio_history_chart, \
        alpaca_acct, alpaca_pos_msg, alpaca_pos_tbl, \
        orders_trunc, orders_msg, orders_tbl, \
        reconciliation_summary, reconciliation_msg, reconciliation_tbl, \
        portfolio_summary, history_state, \
        holding_allocation, drawdown_summary, drawdown_msg, drawdown_chart = updates

    assert _SNAPSHOT_UNAVAILABLE in snapshot["value"]
    assert disclosure["value"] == _UNAVAILABLE_DATA_HTML
    assert _CAPITAL_UNAVAILABLE_MESSAGE in capital_summary["value"]
    assert _CAPITAL_UNAVAILABLE_MESSAGE in allocation["value"]
    assert _HOLDINGS_UNAVAILABLE_MESSAGE in holdings_msg["value"]
    assert _PORTFOLIO_HISTORY_UNAVAILABLE_MESSAGE in portfolio_history_msg["value"]
    assert portfolio_history_chart["visible"] is False
    assert len(portfolio_history_chart["value"]) == 0
    assert _ALPACA_UNAVAILABLE_MESSAGE in alpaca_acct["value"]
    assert _ALPACA_ORDERS_UNAVAILABLE_MESSAGE in orders_msg["value"]
    assert _RECONCILIATION_INTERNAL_UNAVAILABLE_MESSAGE in reconciliation_msg["value"]
    assert reconciliation_summary["visible"] is False
    # every table hidden and empty
    for tbl in (holdings_tbl, alpaca_pos_tbl, orders_tbl, reconciliation_tbl):
        assert tbl["visible"] is False
        assert tbl["value"] == []
    # Visual Dashboard Phase A: no summary and an honestly-empty history
    # state when the underlying screen is fully unavailable.
    assert portfolio_summary["value"] == ""
    assert history_state["value"] == (None, None)
    # Visual Dashboard Phase B: allocation-by-holding follows Holdings'
    # own unavailable state; drawdown follows the value chart's own.
    assert _HOLDINGS_UNAVAILABLE_MESSAGE in holding_allocation["value"]
    assert _DRAWDOWN_UNAVAILABLE_MESSAGE in drawdown_msg["value"]
    assert drawdown_chart["visible"] is False
    assert len(drawdown_chart["value"]) == 0
    assert drawdown_summary["value"] == ""
    # no fabricated markers from mock_data.py
    mock = build_mock_screen()
    rendered = "\n".join(str(u.get("value")) for u in updates)
    assert f"${mock.capital.allocated_amount:,.2f}" not in rendered


def test_rendered_at_indicator_is_present_at_build_and_refreshed_by_render():
    demo = PortfolioIntelligenceUI().build()
    assert any(_RENDERED_AT_PREFIX in v for v in _html_values(demo))

    rendered_at_update = PortfolioIntelligenceUI()._render()[0]  # output index 0
    assert _RENDERED_AT_PREFIX in rendered_at_update["value"]
    assert "CDT" in rendered_at_update["value"] or "CST" in rendered_at_update["value"]


def test_snapshot_line_defaults_to_unavailable_and_is_separate_from_the_render_clock():
    """The page shows the ADR-055 operational-snapshot fetch time on its own
    line, distinct from the render clock, so a Refresh (which only re-reads
    the same snapshot) is never mistaken for a re-fetch. With no provider
    wired the snapshot line is an honest 'unavailable', never a timestamp."""
    demo = PortfolioIntelligenceUI().build()
    html_values = _html_values(demo)

    assert any(_SNAPSHOT_UNAVAILABLE in v for v in html_values)
    # render clock and snapshot line are two different lines
    assert any(_RENDERED_AT_PREFIX in v and _SNAPSHOT_PREFIX not in v for v in html_values)


def test_snapshot_line_shows_the_provider_time_and_is_stable_across_render():
    fetched = datetime(2026, 9, 2, 13, 40, tzinfo=timezone.utc)
    ui = PortfolioIntelligenceUI(
        PortfolioScreen(capital=_make_capital()),
        snapshot_fetched_at_provider=lambda: fetched,
    )

    build_html = "\n".join(_html_values(ui.build()))
    assert f"{_SNAPSHOT_PREFIX}2026-09-02 08:40 CDT" in build_html
    assert "not re-downloaded on Refresh" in build_html

    # output index 1 is the snapshot line; unchanged on a second render
    assert ui._render()[1]["value"] == ui._render()[1]["value"]
    assert _SNAPSHOT_PREFIX in ui._render()[1]["value"]


def test_capital_summary_carries_the_internal_ledger_source_caption_in_every_state():
    """Capital Summary / Allocation are the bot's internal managed
    capital-pool ledger, a separate system of record from the Alpaca Paper
    Account below; the caption saying so renders in the unavailable, real
    and partial states alike."""
    unavailable = PortfolioIntelligenceUI(PortfolioScreen()).build()
    real = PortfolioIntelligenceUI(
        PortfolioScreen(capital=_make_capital(), holdings=(_make_holding(),))
    ).build()
    partial = PortfolioIntelligenceUI(
        PortfolioScreen(capital=_make_capital(), holdings=None)
    ).build()

    for demo in (unavailable, real, partial):
        assert any(_CAPITAL_SOURCE_CAPTION in v for v in _html_values(demo))
    assert "Alpaca Paper Account" in _CAPITAL_SOURCE_CAPTION
    assert "may not match" in _CAPITAL_SOURCE_CAPTION


def test_orders_section_carries_the_verbatim_status_note_in_every_state():
    """A 'canceled' order that still shows a partial fill quantity/time is a
    faithful display of the broker record; the note saying so renders
    unconditionally."""
    for screen in (
        PortfolioScreen(capital=_make_capital()),
        PortfolioScreen(
            capital=_make_capital(),
            alpaca_orders=AlpacaOrdersSnapshot(orders=(), truncated=False),
        ),
        PortfolioScreen(
            capital=_make_capital(),
            alpaca_orders=AlpacaOrdersSnapshot(orders=(_make_order(),), truncated=False),
        ),
    ):
        demo = PortfolioIntelligenceUI(screen=screen).build()
        assert any(_ALPACA_ORDERS_STATUS_NOTE in v for v in _html_values(demo))
    assert "exactly as the broker reports them" in _ALPACA_ORDERS_STATUS_NOTE


def test_no_screen_and_no_provider_uses_the_all_unavailable_screen():
    ui = PortfolioIntelligenceUI()

    assert ui._screen.capital is None
    assert ui._screen.holdings is None
    assert ui._render()[2]["value"] == _UNAVAILABLE_DATA_HTML
