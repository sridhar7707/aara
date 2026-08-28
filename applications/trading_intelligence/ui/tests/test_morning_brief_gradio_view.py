import gradio as gr

from dataclasses import replace

from applications.trading_intelligence.ui.morning_brief.gradio_view import (
    _AS_OF_PREFIX,
    MorningBriefUI,
)
from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.screen import (
    CANDIDATE_SCREENING_SUMMARY_TITLE,
    MARKET_MOOD_REGIME_TITLE,
    OVERNIGHT_HOLDINGS_NEWS_TITLE,
    PORTFOLIO_SNAPSHOT_TITLE,
)
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = MorningBriefUI()

    assert ui._screen == build_mock_screen()


def test_build_returns_a_gradio_blocks_instance():
    ui = MorningBriefUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_shell_header_and_nav_are_present_in_the_built_layout():
    ui = MorningBriefUI()

    demo = ui.build()

    html_values = _html_values(demo)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Morning Brief") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = MorningBriefUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


def test_all_four_frozen_section_titles_render():
    ui = MorningBriefUI()

    demo = ui.build()

    html_values = _html_values(demo)
    combined = "\n".join(html_values)
    assert PORTFOLIO_SNAPSHOT_TITLE in combined
    assert MARKET_MOOD_REGIME_TITLE in combined
    assert CANDIDATE_SCREENING_SUMMARY_TITLE in combined
    assert OVERNIGHT_HOLDINGS_NEWS_TITLE in combined


def test_all_four_sections_render_their_own_unavailable_message():
    screen = build_mock_screen()
    ui = MorningBriefUI(screen=screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    for section in screen.sections:
        assert section.unavailable_message in combined


def test_no_gradio_dataframe_is_rendered():
    """Unlike Portfolio/Risk Intelligence (which render a gr.Dataframe once
    holdings/history exist), Morning Brief's available_summary is always
    plain text -- there must never be a table to render, whether or not a
    section is available."""
    ui = MorningBriefUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert dataframes == []


def test_no_illustrative_data_disclosure_is_rendered():
    """Portfolio/Risk Intelligence show an "Illustrative Data" banner for
    their own fabricated numbers -- Morning Brief must not, since nothing
    it ever shows (real or unavailable) is fabricated."""
    ui = MorningBriefUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Illustrative Data" not in combined


# --- Real Portfolio Snapshot / Market Mood/Regime (MB-1 + MB-2) pass ---


def test_real_available_summary_renders_instead_of_the_unavailable_message():
    screen = build_mock_screen()
    real_screen = replace(
        screen,
        portfolio_snapshot=replace(
            screen.portfolio_snapshot,
            available_summary="Total value $96,933.32 ($38,850.78 cash, $58,082.54 invested).",
        ),
    )
    ui = MorningBriefUI(screen=real_screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Total value $96,933.32" in combined
    assert screen.portfolio_snapshot.unavailable_message not in combined


def test_real_market_mood_regime_renders_instead_of_the_unavailable_message():
    screen = build_mock_screen()
    real_screen = replace(
        screen,
        market_mood_regime=replace(
            screen.market_mood_regime,
            available_summary="Current market regime: TRENDING_UP.",
        ),
    )
    ui = MorningBriefUI(screen=real_screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Current market regime: TRENDING_UP." in combined
    assert screen.market_mood_regime.unavailable_message not in combined


def test_candidate_screening_and_overnight_news_stay_unavailable_when_other_sections_are_real():
    """The one thing this unit must never do: make every section look
    available just because two of them are. Portfolio Snapshot and Market
    Mood/Regime being real must not affect Candidate Screening Summary or
    Overnight Holdings News."""
    screen = build_mock_screen()
    mixed_screen = replace(
        screen,
        portfolio_snapshot=replace(screen.portfolio_snapshot, available_summary="Real capital."),
        market_mood_regime=replace(screen.market_mood_regime, available_summary="Real regime."),
    )
    ui = MorningBriefUI(screen=mixed_screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert screen.candidate_screening_summary.unavailable_message in combined
    assert screen.overnight_holdings_news.unavailable_message in combined


def test_fallback_remains_fully_unavailable_when_no_real_screen_is_supplied():
    """Mirrors what bootstrap.py does when both LegacyCapitalSource and
    LegacyRegimeSource return None -- constructing MorningBriefUI() with
    no args at all must still render the full unavailable mock screen
    unchanged."""
    ui = MorningBriefUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    screen = build_mock_screen()
    for section in screen.sections:
        assert section.unavailable_message in combined
    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert dataframes == []


def test_default_render_shows_no_available_summary_markup():
    """Production guardrail: with no real screen supplied, every section
    is unavailable, so the rendered page contains zero
    '.mb-available-summary' blocks -- only '.mb-unavailable-message' ones.
    A section can only render an available summary from a real,
    adapter-sourced value (see bootstrap.py)."""
    combined = "\n".join(_html_values(MorningBriefUI().build()))

    assert "mb-available-summary" not in combined
    assert "mb-unavailable-message" in combined


# --- Render-time fetch: Refresh button, demo.load, "as of" indicator ----


_OUTPUT_COUNT = 5  # "As of" line + one body per MorningBriefScreen.sections (4)


def _refresh_button(demo):
    return next(
        block for block in demo.blocks.values()
        if isinstance(block, gr.Button) and "aara-refresh-button" in (block.elem_classes or [])
    )


def _counting_provider(*screens):
    """Returns a provider yielding the given screens in order (repeating
    the last), plus a mutable call-count list."""
    calls = []
    seq = list(screens)

    def provider():
        calls.append(True)
        return seq[min(len(calls) - 1, len(seq) - 1)]

    return provider, calls


def _real_portfolio_screen(summary="Total value $1.00 ($1.00 cash, $0.00 invested)."):
    base = build_mock_screen()
    return replace(
        base,
        portfolio_snapshot=replace(base.portfolio_snapshot, available_summary=summary),
    )


def test_build_has_a_single_refresh_button_with_the_shared_class():
    demo = MorningBriefUI().build()

    buttons = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Button) and "aara-refresh-button" in (b.elem_classes or [])
    ]
    assert len(buttons) == 1


def test_disable_refresh_button_returns_a_not_interactive_update():
    assert MorningBriefUI._disable_refresh_button() == {
        "interactive": False, "__type__": "update",
    }


def test_enable_refresh_button_returns_an_interactive_update():
    assert MorningBriefUI._enable_refresh_button() == {
        "interactive": True, "__type__": "update",
    }


def test_refresh_click_chain_is_disable_then_render_then_enable():
    """Same disable -> render -> enable double-submit guard chain as
    Decision Center / Portfolio Intelligence: proves the click().then().
    then() wiring in build(), not just that the helper methods exist."""
    ui = MorningBriefUI()
    demo = ui.build()

    refresh_button = _refresh_button(demo)
    refresh_button_id = next(
        bid for bid, block in demo.blocks.items() if block is refresh_button
    )
    disable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is MorningBriefUI._disable_refresh_button
    )
    render_dep = next(
        dep for dep in demo.config["dependencies"]
        if dep.get("trigger_after") == disable_dep["id"]
    )
    enable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is MorningBriefUI._enable_refresh_button
    )

    assert disable_dep["targets"] == [(refresh_button_id, "click")]
    assert refresh_button_id in disable_dep["outputs"]
    assert demo.fns[render_dep["id"]].fn == ui._render
    assert enable_dep["trigger_after"] == render_dep["id"]
    assert refresh_button_id in enable_dep["outputs"]


def test_demo_load_and_the_refresh_chain_both_call_render():
    ui = MorningBriefUI()
    demo = ui.build()

    render_deps = [
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn == ui._render
    ]
    assert len(render_deps) == 2  # demo.load() + the Refresh .then() step


def test_render_returns_one_update_per_dynamic_output():
    updates = MorningBriefUI()._render()

    assert len(updates) == _OUTPUT_COUNT
    assert all(u.get("__type__") == "update" for u in updates)


def test_render_reflects_a_fresh_screen_from_the_provider_each_call():
    provider, calls = _counting_provider(
        build_mock_screen(),          # __init__ snapshot (all unavailable)
        _real_portfolio_screen(),     # 1st _render
    )
    ui = MorningBriefUI(screen_provider=provider)

    first = ui._render()
    # output index 1 == Portfolio Snapshot body (first section)
    assert "Total value $1.00" in first[1]["value"]
    assert "mb-available-summary" in first[1]["value"]

    second = ui._render()  # provider repeats the last screen
    assert "Total value $1.00" in second[1]["value"]
    assert len(calls) == 3  # 1 in __init__ + 2 explicit _render calls


def test_render_preserves_unavailable_states_with_no_mock_fallback():
    """A provider that returns an all-unavailable screen collapses every
    section body back to its explicit unavailable message -- never
    fabricated content."""
    ui = MorningBriefUI(screen_provider=build_mock_screen)
    updates = ui._render()

    baseline = build_mock_screen()
    section_bodies = updates[1:]  # drop the "As of" update
    assert len(section_bodies) == len(baseline.sections)
    for update, section in zip(section_bodies, baseline.sections):
        assert section.unavailable_message in update["value"]
        assert "mb-available-summary" not in update["value"]


def test_as_of_indicator_is_present_at_build_and_refreshed_by_render():
    demo = MorningBriefUI().build()
    assert any(_AS_OF_PREFIX in v for v in _html_values(demo))

    as_of_update = MorningBriefUI()._render()[0]  # output index 0
    assert _AS_OF_PREFIX in as_of_update["value"]
    assert "CDT" in as_of_update["value"] or "CST" in as_of_update["value"]


def test_no_screen_and_no_provider_uses_the_mock_unavailable_screen():
    ui = MorningBriefUI()

    assert ui._screen == build_mock_screen()
    assert ui._screen.is_empty
    body_updates = ui._render()[1:]
    for update in body_updates:
        assert "mb-unavailable-message" in update["value"]
