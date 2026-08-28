from datetime import datetime, timezone

import gradio as gr

from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
    _ALPACA_ORDERS_SCOPE_CAPTION,
    _ALPACA_ORDERS_TRUNCATION_NOTE,
    _ALPACA_ORDERS_UNAVAILABLE_MESSAGE,
    _ALPACA_ORDERS_WORKING_MARKER,
    _ALPACA_PAPER_BADGE_TEXT,
    _ALPACA_UNAVAILABLE_MESSAGE,
    _CAPITAL_UNAVAILABLE_MESSAGE,
    _HOLDINGS_UNAVAILABLE_MESSAGE,
    _PARTIAL_DATA_BODY,
    _PARTIAL_DATA_HTML,
    _PARTIAL_DATA_TITLE,
    _REAL_DATA_HTML,
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
    PortfolioHolding,
    PortfolioScreen,
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
    assert _UNAVAILABLE_DATA_HTML == (
        '<div class="pi-disclosure">'
        f'<div class="pi-disclosure-title">{_UNAVAILABLE_DATA_TITLE}</div>'
        f'<div class="pi-disclosure-body">{_UNAVAILABLE_DATA_BODY}</div>'
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
    assert [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)] == []


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


def test_unavailable_html_helper_uses_the_pi_unavailable_class():
    out = PortfolioIntelligenceUI._format_unavailable_html("nope")

    assert out == '<div class="pi-unavailable">nope</div>'


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
    dataframes = [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)]

    assert any(_HOLDINGS_UNAVAILABLE_MESSAGE in v for v in html_values)
    assert not any(d for d in dataframes if "pi-holdings-table" in (d.elem_classes or []))


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
    assert [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)] == []


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
    dataframes = [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)]

    assert dataframes == []
    assert _REAL_DATA_HTML in html_values
    assert any("No holdings recorded yet." in value for value in html_values)
    assert not any(_HOLDINGS_UNAVAILABLE_MESSAGE in value for value in html_values)


def test_empty_state_message_helper_still_reads_the_screens_own_message():
    screen = PortfolioScreen(capital=_make_capital(), holdings=())

    empty_html = PortfolioIntelligenceUI._format_empty_message_html(screen)

    assert 'class="pi-empty-message"' in empty_html
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
    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
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
        if isinstance(block, gr.Dataframe) and "pi-alpaca-orders-table" in (block.elem_classes or [])
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


def test_default_screen_renders_zero_dataframes():
    """The default (no screen) is fully unavailable: no Holdings table, no
    Alpaca positions table, no Alpaca orders table."""
    demo = PortfolioIntelligenceUI().build()

    all_dataframes = [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)]
    assert all_dataframes == []
