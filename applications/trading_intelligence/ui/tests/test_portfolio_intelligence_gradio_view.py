import gradio as gr

from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
    _ALPACA_PAPER_BADGE_TEXT,
    _ALPACA_UNAVAILABLE_MESSAGE,
    _ILLUSTRATIVE_DATA_BODY,
    _ILLUSTRATIVE_DATA_HTML,
    _ILLUSTRATIVE_DATA_TITLE,
    _PARTIAL_ILLUSTRATIVE_DATA_HTML,
    _REAL_DATA_HTML,
    PortfolioIntelligenceUI,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaAccountSnapshot,
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


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = PortfolioIntelligenceUI()

    assert not ui._screen.is_empty


def test_build_returns_a_gradio_blocks_instance():
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_illustrative_data_disclosure_is_the_exact_fixed_text():
    assert _ILLUSTRATIVE_DATA_TITLE == "Illustrative Data"
    assert _ILLUSTRATIVE_DATA_HTML == (
        '<div class="pi-disclosure">'
        f'<div class="pi-disclosure-title">{_ILLUSTRATIVE_DATA_TITLE}</div>'
        f'<div class="pi-disclosure-body">{_ILLUSTRATIVE_DATA_BODY}</div>'
        "</div>"
    )


def test_illustrative_data_disclosure_block_is_present_in_the_built_layout():
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert _ILLUSTRATIVE_DATA_HTML in html_values


def test_shell_header_and_nav_are_present_in_the_built_layout():
    """AARA shell consistency pass: Portfolio Intelligence now renders the
    same shell header/nav Decision Center does, reused via ui/shell.py --
    see that module's docstring for why it isn't imported from
    ui/decision_center/ directly."""
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Portfolio Intelligence") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


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


def test_empty_message_html_renders_the_screens_own_message():
    screen = PortfolioScreen(capital=_make_capital())

    empty_html = PortfolioIntelligenceUI._format_empty_message_html(screen)

    assert 'class="pi-empty-message"' in empty_html
    assert "No holdings recorded yet." in empty_html


def test_build_renders_empty_message_instead_of_a_table_when_no_holdings():
    empty_screen = PortfolioScreen(capital=_make_capital())
    ui = PortfolioIntelligenceUI(screen=empty_screen)

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    html_values = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]
    assert dataframes == []
    assert any("No holdings recorded yet." in value for value in html_values)


def test_build_renders_a_dataframe_when_holdings_exist():
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert "pi-holdings-table" in dataframes[0].elem_classes


# --- Real Capital Summary/Allocation (legacy_capital_source) pass ------


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def test_real_supplied_capital_renders_real_values_when_capital_is_real():
    real_capital = _make_capital(
        allocated_amount=96933.32, available_cash=38850.78,
        invested_amount=58082.54, reserve=0.0, realized_profit=0.0,
    )
    screen = PortfolioScreen(capital=real_capital)
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=True)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "$96,933.32" in combined
    assert "$38,850.78" in combined
    assert "$58,082.54" in combined


def test_derived_allocation_values_render_correctly_for_a_real_screen():
    real_capital = _make_capital(available_cash=250.0, invested_amount=750.0)
    screen = PortfolioScreen(capital=real_capital)
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=True)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Invested 75.0%" in combined
    assert "Cash 25.0%" in combined


def test_disclosure_is_the_partial_variant_when_capital_is_real():
    ui = PortfolioIntelligenceUI(screen=PortfolioScreen(capital=_make_capital()), capital_is_real=True)

    demo = ui.build()

    html_values = _html_values(demo)
    assert _PARTIAL_ILLUSTRATIVE_DATA_HTML in html_values
    assert _ILLUSTRATIVE_DATA_HTML not in html_values


def test_disclosure_stays_the_original_fully_illustrative_variant_by_default():
    """Regression lock: constructing PortfolioIntelligenceUI exactly as
    every existing call site already does (no capital_is_real argument)
    must render byte-identical disclosure HTML to before this unit."""
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    html_values = _html_values(demo)
    assert _ILLUSTRATIVE_DATA_HTML in html_values
    assert _PARTIAL_ILLUSTRATIVE_DATA_HTML not in html_values


def test_illustrative_fallback_still_works_when_no_real_screen_is_supplied():
    """Mirrors what bootstrap.py does when LegacyCapitalSource returns
    None -- constructing PortfolioIntelligenceUI() with no args at all
    must still render the full illustrative mock screen unchanged."""
    ui = PortfolioIntelligenceUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert _ILLUSTRATIVE_DATA_HTML in _html_values(demo)


def test_holdings_remains_illustrative_and_unaffected_when_capital_is_real():
    """The one thing this unit must never do: make Holdings look real just
    because Capital Summary/Allocation are. Supplying a real capital value
    alongside the mock screen's own illustrative holdings must render
    those exact same illustrative holdings, unchanged."""
    from applications.trading_intelligence.ui.portfolio_intelligence.mock_data import (
        build_mock_screen,
    )
    from dataclasses import replace

    illustrative_screen = build_mock_screen()
    real_capital = _make_capital(allocated_amount=96933.32)
    screen = replace(illustrative_screen, capital=real_capital)
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=True)

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert dataframes[0].value["data"] == ui._format_holdings_rows(illustrative_screen.holdings)


# --- Real Holdings (legacy_position_source + live_price_source) pass ---


def test_disclosure_is_the_real_data_variant_when_capital_and_holdings_are_both_real():
    real_capital = _make_capital()
    holding = PortfolioHolding(
        symbol="AAPL", quantity=19.11, price=334.67, market_value=6396.0, weight_pct=100.0,
    )
    screen = PortfolioScreen(capital=real_capital, holdings=(holding,))
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=True, holdings_is_real=True)

    demo = ui.build()

    html_values = _html_values(demo)
    assert _REAL_DATA_HTML in html_values
    assert _PARTIAL_ILLUSTRATIVE_DATA_HTML not in html_values
    assert _ILLUSTRATIVE_DATA_HTML not in html_values


def test_disclosure_stays_partial_when_capital_is_real_but_holdings_is_not():
    """Regression lock: holdings_is_real defaults to False, so every
    existing capital_is_real=True call site (before this unit) keeps
    rendering the exact same partial-illustrative disclosure."""
    ui = PortfolioIntelligenceUI(screen=PortfolioScreen(capital=_make_capital()), capital_is_real=True)

    demo = ui.build()

    html_values = _html_values(demo)
    assert _PARTIAL_ILLUSTRATIVE_DATA_HTML in html_values
    assert _REAL_DATA_HTML not in html_values


def test_real_holdings_render_the_real_price_and_market_value_not_entry_price():
    real_capital = _make_capital()
    holding = PortfolioHolding(
        symbol="AAPL", quantity=19.11, price=334.67, market_value=6396.0359, weight_pct=100.0,
    )
    screen = PortfolioScreen(capital=real_capital, holdings=(holding,))
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=True, holdings_is_real=True)

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert dataframes[0].value["data"] == [["AAPL", "19.11", "$334.67", "$6,396.04", "100.0%"]]


def test_real_holdings_can_be_empty_with_the_real_data_disclosure():
    """A real position source reporting zero open positions is a genuine
    real state (not illustrative) -- the empty-state message still
    renders, but under the real-data disclosure rather than the
    illustrative one."""
    real_capital = _make_capital()
    screen = PortfolioScreen(capital=real_capital, holdings=())
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=True, holdings_is_real=True)

    demo = ui.build()

    html_values = _html_values(demo)
    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert dataframes == []
    assert _REAL_DATA_HTML in html_values
    assert any("No holdings recorded yet." in value for value in html_values)


# --- Alpaca Paper Account (alpaca_paper_source) pass -----------------


def test_alpaca_section_shows_unavailable_message_by_default():
    ui = PortfolioIntelligenceUI(screen=PortfolioScreen(capital=_make_capital()))

    demo = ui.build()

    html_values = _html_values(demo)
    assert any(_ALPACA_UNAVAILABLE_MESSAGE in value for value in html_values)


def test_alpaca_badge_is_always_present_regardless_of_availability():
    """Phase 4 safety requirement: the 'ALPACA PAPER' label must always be
    visible in the section header, whether or not real data is available,
    so the section can never be mistaken for anything else."""
    ui = PortfolioIntelligenceUI(screen=PortfolioScreen(capital=_make_capital()))

    demo = ui.build()

    html_values = _html_values(demo)
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
    ui = PortfolioIntelligenceUI(screen=screen)

    demo = ui.build()

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
    """A real, connected Alpaca account with zero open positions is a
    legitimate real state -- must render the Alpaca-specific empty
    message, never the unavailable message, and never a Holdings-style
    table."""
    screen = PortfolioScreen(
        capital=_make_capital(), alpaca_account=_make_alpaca_account(), alpaca_positions=(),
    )
    ui = PortfolioIntelligenceUI(screen=screen)

    demo = ui.build()

    html_values = _html_values(demo)
    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    alpaca_tables = [d for d in dataframes if "pi-alpaca-positions-table" in d.elem_classes]
    assert alpaca_tables == []
    assert any("Alpaca Paper account has no open positions." in v for v in html_values)
    assert not any(_ALPACA_UNAVAILABLE_MESSAGE in v for v in html_values)


def test_alpaca_section_is_independent_of_capital_and_holdings_reality():
    """The Alpaca section's availability must never be coupled to
    capital_is_real/holdings_is_real -- it can be real while Capital
    Summary/Holdings stay fully illustrative, and the illustrative
    disclosure must still read exactly as it always has."""
    screen = PortfolioScreen(
        capital=_make_capital(), alpaca_account=_make_alpaca_account(), alpaca_positions=(),
    )
    ui = PortfolioIntelligenceUI(screen=screen, capital_is_real=False, holdings_is_real=False)

    demo = ui.build()

    html_values = _html_values(demo)
    assert _ILLUSTRATIVE_DATA_HTML in html_values
    assert any(_ALPACA_PAPER_BADGE_TEXT in v for v in html_values)
    assert any("Alpaca Paper account has no open positions." in v for v in html_values)
