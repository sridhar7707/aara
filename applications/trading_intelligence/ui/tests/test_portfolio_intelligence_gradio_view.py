import gradio as gr

from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
    _ILLUSTRATIVE_DATA_BODY,
    _ILLUSTRATIVE_DATA_HTML,
    _ILLUSTRATIVE_DATA_TITLE,
    PortfolioIntelligenceUI,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
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
