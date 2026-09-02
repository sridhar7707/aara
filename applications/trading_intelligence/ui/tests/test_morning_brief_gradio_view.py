import gradio as gr

from dataclasses import replace
from datetime import datetime, timezone

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.ui.morning_brief.gradio_view import (
    _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION,
    _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML,
    _RENDERED_AT_PREFIX,
    _SECTION_AS_OF_PREFIX,
    _SNAPSHOT_PREFIX,
    _SNAPSHOT_UNAVAILABLE,
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


def test_portfolio_snapshot_carries_a_data_source_caption():
    """MB-2: the Portfolio Snapshot section discloses that it is a
    different system of record from Portfolio Intelligence's Capital
    Summary. Rendered once, in every state (here: the default all-
    unavailable screen), and it must not claim the two are equivalent."""
    combined = "\n".join(_html_values(MorningBriefUI().build()))

    assert combined.count(_PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML) == 1
    assert "Tracked separately from Portfolio Intelligence" in _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION
    assert "the two are different systems and may not match" in _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION
    # never implies equivalence with the Capital Summary figure
    for equivalence_claim in ("same as", "identical to", "matches portfolio intelligence"):
        assert equivalence_claim not in _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION.lower()


def test_portfolio_snapshot_caption_is_static_not_a_dynamic_render_output():
    """The caption is a fixed disclosure -- it must not be wired into
    _render()'s output list, so _OUTPUT_COUNT stays 6."""
    ui = MorningBriefUI()

    assert len(ui._render()) == _OUTPUT_COUNT  # unchanged: 6
    combined = "\n".join(_html_values(ui.build()))
    assert _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML in combined


def test_source_caption_renders_with_a_real_portfolio_snapshot_too():
    screen = build_mock_screen()
    real_screen = replace(
        screen,
        portfolio_snapshot=replace(
            screen.portfolio_snapshot,
            available_summary="Total value $1.00 ($1.00 cash, $0.00 invested).",
        ),
    )
    combined = "\n".join(_html_values(MorningBriefUI(screen=real_screen).build()))

    assert combined.count(_PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML) == 1
    assert "Total value $1.00" in combined


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


# --- P1: per-section "as of" data-freshness line -------------------------


def test_section_as_of_line_renders_under_an_available_summary():
    """A section carrying `as_of` renders an extra `.mb-subtitle` line with
    that timestamp, immediately after its own available_summary."""
    screen = build_mock_screen()
    real_screen = replace(
        screen,
        portfolio_snapshot=replace(
            screen.portfolio_snapshot,
            available_summary="Total value $100,029.85 ($59,869.06 cash, $40,160.79 invested).",
            as_of="2026-08-31 14:39 CDT",
        ),
    )
    body = MorningBriefUI._format_available_summary_html(real_screen.portfolio_snapshot)

    assert "mb-available-summary" in body
    assert f'<div class="mb-subtitle">{_SECTION_AS_OF_PREFIX}2026-08-31 14:39 CDT</div>' in body
    # the freshness line comes after the summary, not before it
    assert body.index("mb-available-summary") < body.index("mb-subtitle")


def test_section_as_of_line_absent_when_as_of_is_none():
    section = replace(
        build_mock_screen().portfolio_snapshot,
        available_summary="Total value $1.00 ($1.00 cash, $0.00 invested).",
        as_of=None,
    )
    body = MorningBriefUI._format_available_summary_html(section)

    assert "mb-available-summary" in body
    assert "mb-subtitle" not in body
    assert _SECTION_AS_OF_PREFIX not in body


def test_section_as_of_prefix_is_distinct_from_the_page_render_clock_prefix():
    """Per-section 'as of ...' must not read as the page-level render clock
    ('Rendered at ...') -- requirement 5."""
    assert _SECTION_AS_OF_PREFIX != _RENDERED_AT_PREFIX
    assert _SECTION_AS_OF_PREFIX.strip() == "as of"


def test_section_as_of_line_is_present_in_the_full_built_screen():
    screen = build_mock_screen()
    real_screen = replace(
        screen,
        market_mood_regime=replace(
            screen.market_mood_regime,
            available_summary="Current market regime: HIGH_VOLATILITY.",
            as_of="2026-08-31 14:39 CDT",
        ),
    )
    combined = "\n".join(_html_values(MorningBriefUI(screen=real_screen).build()))

    assert "Current market regime: HIGH_VOLATILITY." in combined
    assert f"{_SECTION_AS_OF_PREFIX}2026-08-31 14:39 CDT" in combined
    # still a separate concept from the page-level lines
    assert _RENDERED_AT_PREFIX in combined
    assert _SNAPSHOT_PREFIX in combined or _SNAPSHOT_UNAVAILABLE in combined


def test_p2_spy_clause_rides_inside_the_existing_available_summary_output():
    """P2: the SPY daily-move clause is part of the regime section's
    available_summary string (composed in bootstrap.py) -- it renders
    inside the same `mb-available-summary` div, adds no new output
    component, and does not change _OUTPUT_COUNT."""
    spy_summary = (
        "Current market regime: HIGH_VOLATILITY. "
        "SPY 512.34, prev close 508.10 (+0.83% today) -- daily bar as of 2026-09-01."
    )
    real_screen = replace(
        build_mock_screen(),
        market_mood_regime=replace(
            build_mock_screen().market_mood_regime,
            available_summary=spy_summary,
            as_of="2026-08-31 14:39 CDT",
        ),
    )
    ui = MorningBriefUI(screen=real_screen)

    body = MorningBriefUI._format_available_summary_html(real_screen.market_mood_regime)
    assert "mb-available-summary" in body
    # whole clause is inside the summary div, before the per-section as-of line
    summary_div = body.split('<div class="mb-subtitle">')[0]
    assert "SPY 512.34, prev close 508.10 (+0.83% today) -- daily bar as of 2026-09-01." in summary_div

    combined = "\n".join(_html_values(ui.build()))
    assert spy_summary in combined
    assert len(ui._render()) == _OUTPUT_COUNT  # unchanged: 6


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
    '.mb-available-summary' blocks -- only the shared
    '.aara-integration-status' unavailable body (ADR-061 A4). A section can
    only render an available summary from a real, adapter-sourced value
    (see bootstrap.py)."""
    combined = "\n".join(_html_values(MorningBriefUI().build()))

    assert "mb-available-summary" not in combined
    assert "aara-integration-status" in combined


# --- Render-time fetch: Refresh button, demo.load, freshness indicators --


# render-clock line + operational-snapshot line + one body per
# MorningBriefScreen.sections (4)
_OUTPUT_COUNT = 6


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
    # output index 2 == Portfolio Snapshot body (index 0 = render clock,
    # index 1 = operational-snapshot line, then one per section)
    assert "Total value $1.00" in first[2]["value"]
    assert "mb-available-summary" in first[2]["value"]

    second = ui._render()  # provider repeats the last screen
    assert "Total value $1.00" in second[2]["value"]
    assert len(calls) == 3  # 1 in __init__ + 2 explicit _render calls


def test_render_preserves_unavailable_states_with_no_mock_fallback():
    """A provider that returns an all-unavailable screen collapses every
    section body back to its explicit unavailable message -- never
    fabricated content."""
    ui = MorningBriefUI(screen_provider=build_mock_screen)
    updates = ui._render()

    baseline = build_mock_screen()
    section_bodies = updates[2:]  # drop the render-clock + snapshot updates
    assert len(section_bodies) == len(baseline.sections)
    for update, section in zip(section_bodies, baseline.sections):
        assert section.unavailable_message in update["value"]
        assert "mb-available-summary" not in update["value"]


def test_rendered_at_indicator_is_present_at_build_and_refreshed_by_render():
    demo = MorningBriefUI().build()
    assert any(_RENDERED_AT_PREFIX in v for v in _html_values(demo))

    rendered_at_update = MorningBriefUI()._render()[0]  # output index 0
    assert _RENDERED_AT_PREFIX in rendered_at_update["value"]
    assert "CDT" in rendered_at_update["value"] or "CST" in rendered_at_update["value"]


def test_operational_snapshot_line_is_distinct_from_the_render_clock():
    """The two freshness lines are separate blocks with different wording:
    'Rendered at ...' is the UI render clock; 'Operational data snapshot:
    ...' is when the ADR-055 trades.db snapshot was fetched for this
    process. A stale snapshot must never be presented as the render time."""
    fetched = datetime(2026, 8, 31, 19, 39, tzinfo=timezone.utc)
    ui = MorningBriefUI(snapshot_fetched_at_provider=lambda: fetched)

    values = _html_values(ui.build())
    rendered_line = next(v for v in values if _RENDERED_AT_PREFIX in v)
    snapshot_line = next(v for v in values if _SNAPSHOT_PREFIX in v)

    assert rendered_line != snapshot_line
    assert _SNAPSHOT_PREFIX not in rendered_line
    assert _RENDERED_AT_PREFIX not in snapshot_line
    # 19:39 UTC on 2026-08-31 == 14:39 America/Chicago (CDT)
    assert "Operational data snapshot: 2026-08-31 14:39 CDT" in snapshot_line
    assert "not re-downloaded on Refresh" in snapshot_line


def test_operational_snapshot_line_stays_fixed_while_render_clock_advances_on_refresh():
    """Refresh re-reads the same snapshot file, so the snapshot line's
    value is byte-identical across renders even though the render clock
    line is recomputed each time."""
    fetched = datetime(2026, 8, 31, 19, 39, tzinfo=timezone.utc)
    ui = MorningBriefUI(
        screen_provider=build_mock_screen,
        snapshot_fetched_at_provider=lambda: fetched,
    )

    first, second = ui._render(), ui._render()

    # index 0 = render clock (recomputed), index 1 = snapshot line (fixed)
    assert first[1]["value"] == second[1]["value"]
    assert _SNAPSHOT_PREFIX in first[1]["value"]
    assert "2026-08-31 14:39 CDT" in first[1]["value"]
    assert _RENDERED_AT_PREFIX in first[0]["value"]


def test_operational_snapshot_line_reports_unavailable_when_no_snapshot():
    """No snapshot obtained (deployed Space fell back, local dev, tests):
    an honest 'unavailable', never a fabricated timestamp."""
    ui = MorningBriefUI()  # default provider returns None

    build_values = _html_values(ui.build())
    assert any(_SNAPSHOT_UNAVAILABLE in v for v in build_values)

    snapshot_update = ui._render()[1]
    assert snapshot_update["value"] == f'<div class="mb-subtitle">{_SNAPSHOT_UNAVAILABLE}</div>'


def test_snapshot_fetched_at_provider_is_re_called_every_render():
    """The provider is invoked on build and on each render (it re-stats the
    file) -- it is not cached at construction."""
    calls = []

    def _provider():
        calls.append(True)
        return datetime(2026, 8, 31, 19, 39, tzinfo=timezone.utc)

    ui = MorningBriefUI(
        screen_provider=build_mock_screen, snapshot_fetched_at_provider=_provider
    )
    ui.build()
    ui._render()
    ui._render()

    assert len(calls) == 3  # 1 in build() + 2 explicit _render calls


def test_no_screen_and_no_provider_uses_the_mock_unavailable_screen():
    ui = MorningBriefUI()

    assert ui._screen == build_mock_screen()
    assert ui._screen.is_empty
    body_updates = ui._render()[2:]  # drop render-clock + snapshot updates
    for update in body_updates:
        assert "aara-integration-status" in update["value"]


# --- ADR-061 A4: per-section IntegrationHealth in the unavailable body ---


def test_section_health_names_the_specific_reason_on_the_unavailable_path():
    """When bootstrap.py records a non-HEALTHY section.health on the
    unavailable path, the section body names that reason via the shared
    renderer; a section with health=None keeps its own fixed message."""
    screen = build_mock_screen()
    with_health = replace(
        screen,
        portfolio_snapshot=replace(
            screen.portfolio_snapshot,
            health=IntegrationHealth.not_configured("trades_db_capital"),
        ),
        market_mood_regime=replace(
            screen.market_mood_regime,
            health=IntegrationHealth.unavailable("trades_db_regime"),
        ),
    )
    combined = "\n".join(_html_values(MorningBriefUI(screen=with_health).build()))

    assert "not configured for this environment" in combined
    assert "provider could not be reached" in combined
    assert "aara-integration-status" in combined
    # the two sections with health=None keep their own fixed message
    assert screen.candidate_screening_summary.unavailable_message in combined
    assert screen.overnight_holdings_news.unavailable_message in combined
    # never fabricated content
    assert "mb-available-summary" not in combined


def test_section_health_does_not_change_availability():
    screen = build_mock_screen()
    with_health = replace(
        screen,
        portfolio_snapshot=replace(
            screen.portfolio_snapshot,
            health=IntegrationHealth.auth_failed("trades_db_capital"),
        ),
    )

    assert with_health.portfolio_snapshot.is_available is False
    assert with_health.is_empty is True
