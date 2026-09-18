import gradio as gr

from dataclasses import replace
from datetime import datetime, timezone

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.ui.morning_brief.gradio_view import (
    _DECISION_ACTIVITY_UNAVAILABLE_MESSAGE,
    _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION,
    _PORTFOLIO_SNAPSHOT_SOURCE_CAPTION_HTML,
    _RENDERED_AT_PREFIX,
    _RISK_STATE_UNAVAILABLE_MESSAGE,
    _SECTION_AS_OF_PREFIX,
    _SNAPSHOT_PREFIX,
    _SNAPSHOT_UNAVAILABLE,
    MorningBriefUI,
)
from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.theme import CSS
from applications.trading_intelligence.ui.morning_brief.screen import (
    CANDIDATE_SCREENING_SUMMARY_TITLE,
    MARKET_MOOD_REGIME_TITLE,
    OVERNIGHT_HOLDINGS_NEWS_TITLE,
    PORTFOLIO_SNAPSHOT_TITLE,
    DrawdownPoint,
    PortfolioHistoryPoint,
    PortfolioKpis,
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


def test_page_title_carries_the_shared_eyebrow_treatment():
    """Impeccable critique finding #4: the page title uses the shared
    .aara-page-title primitive (design_system.py) instead of a plain
    mixed-case <h2>, matching the treatment now applied consistently
    across all six screens."""
    ui = MorningBriefUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert '<h2 class="aara-page-title">Morning Brief</h2>' in combined


def test_theme_mirrors_the_shared_page_title_treatment_for_standalone_render():
    """Visual-quality pass (2026-09-17): normal-case, not uppercase/
    tracked -- matches design_system.py's .aara-page-title primitive."""
    block = CSS.split(".mb-page-header h2 {")[1].split("}")[0]
    assert "text-transform" not in block
    assert "font-weight: 700;" in block
    assert "color: var(--mb-color-navy);" in block


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
    _render()'s output list, so _OUTPUT_COUNT is unaffected by it."""
    ui = MorningBriefUI()

    assert len(ui._render()) == _OUTPUT_COUNT
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
    assert len(ui._render()) == _OUTPUT_COUNT


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
# MorningBriefScreen.sections (4) + Sprint 1 portfolio-history message,
# chart, and caption (3) + Decision Activity & Risk State Context sprint's
# two independently-gated facts (2) + Sprint 8B (Command Center)'s KPI row
# (1) and drawdown message/chart/caption (3)
_OUTPUT_COUNT = 15


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
    # drop the render-clock + snapshot updates; stop before the Sprint 1
    # portfolio-history message/chart/caption outputs, which are covered
    # by their own dedicated tests.
    section_bodies = updates[2:2 + len(baseline.sections)]
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
    # drop render-clock + snapshot updates; stop before the Sprint 1
    # portfolio-history outputs (covered by their own dedicated tests).
    body_updates = ui._render()[2:2 + len(ui._screen.sections)]
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


# --- Sprint 1: Portfolio Value Trend chart --------------------------------


def _history_chart(demo):
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.LinePlot)
        and "mb-portfolio-history-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def test_portfolio_history_unavailable_renders_the_message_and_hides_the_chart():
    """Default mock screen: portfolio_history is None (unavailable)."""
    demo = MorningBriefUI().build()

    html_values = _html_values(demo)
    assert any("aara-integration-status" in v for v in html_values)
    assert _history_chart(demo).visible is False


def test_portfolio_history_empty_renders_the_message_and_hides_the_chart():
    screen = replace(build_mock_screen(), portfolio_history=())
    demo = MorningBriefUI(screen=screen).build()

    html_values = _html_values(demo)
    assert any("No portfolio history is recorded yet." in v for v in html_values)
    assert _history_chart(demo).visible is False


def test_portfolio_history_with_real_points_renders_the_chart_and_no_message():
    points = (
        PortfolioHistoryPoint(as_of="2026-09-01T12:00:00+00:00", portfolio_value=99000.0),
        PortfolioHistoryPoint(as_of="2026-09-13T12:00:00+00:00", portfolio_value=100500.0),
    )
    screen = replace(build_mock_screen(), portfolio_history=points)
    demo = MorningBriefUI(screen=screen).build()

    chart = _history_chart(demo)
    assert chart.visible is True
    assert [row[1] for row in chart.value["data"]] == [99000.0, 100500.0]
    # The portfolio-history message output specifically (index 6) is
    # empty/hidden when real points are present -- other sections' own
    # (unrelated, still-default-mock) unavailable text is out of scope here.
    message_update = MorningBriefUI(screen=screen)._render()[6]
    assert message_update["visible"] is False
    assert message_update["value"] == ""


def test_portfolio_history_caption_shows_the_most_recent_point_as_of():
    """Hardening (combined Sprint 5+6+7): the caption must use the SAME
    human-readable "%Y-%m-%d %H:%M %Z" America/Chicago format every other
    "as of" line on this screen already uses -- not the raw ISO-8601
    string. 2026-09-13T12:00:00+00:00 (UTC) is 2026-09-13 07:00 CDT."""
    points = (
        PortfolioHistoryPoint(as_of="2026-09-01T12:00:00+00:00", portfolio_value=99000.0),
        PortfolioHistoryPoint(as_of="2026-09-13T12:00:00+00:00", portfolio_value=100500.0),
    )
    screen = replace(build_mock_screen(), portfolio_history=points)

    combined = "\n".join(_html_values(MorningBriefUI(screen=screen).build()))

    assert f"{_SECTION_AS_OF_PREFIX}2026-09-13 07:00 CDT" in combined
    assert "2026-09-13T12:00:00+00:00" not in combined


def test_portfolio_history_caption_is_absent_when_unavailable_or_empty():
    # caption output is index 8 (see test_portfolio_history_refresh_updates_
    # the_chart's indexing note).
    unavailable_caption = MorningBriefUI()._render()[8]["value"]
    empty_screen = replace(build_mock_screen(), portfolio_history=())
    empty_caption = MorningBriefUI(screen=empty_screen)._render()[8]["value"]

    assert unavailable_caption == ""
    assert empty_caption == ""


def test_portfolio_history_chart_has_no_derived_performance_metrics():
    """Explicit scope guard, mirroring Portfolio Intelligence's own chart:
    only the two real columns (timestamp, portfolio value) may ever appear
    -- no Sharpe/alpha/beta/CAGR/ROI/drawdown or any other computed
    metric."""
    points = (PortfolioHistoryPoint(as_of="2026-09-13T12:00:00+00:00", portfolio_value=100500.0),)
    screen = replace(build_mock_screen(), portfolio_history=points)

    chart = _history_chart(MorningBriefUI(screen=screen).build())

    assert set(chart.value["columns"]) == {"as_of", "portfolio_value"}


def test_portfolio_history_refresh_updates_the_chart():
    """Proves the chart is wired into the dynamic _render() output list
    (not a static, build()-time-only component) -- a provider returning a
    different screen on the next call must change what _render() reports
    for the chart, exactly like every other dynamic output on this
    screen."""
    empty_screen = replace(build_mock_screen(), portfolio_history=())
    points = (PortfolioHistoryPoint(as_of="2026-09-13T12:00:00+00:00", portfolio_value=100500.0),)
    populated_screen = replace(build_mock_screen(), portfolio_history=points)
    calls = []

    def provider():
        calls.append(True)
        # call 1 is __init__'s own priming read; call 2 is the first
        # explicit _render() below -- both should still see the empty
        # screen, so `first` reflects unchanged state before the switch.
        return empty_screen if len(calls) <= 2 else populated_screen

    ui = MorningBriefUI(screen_provider=provider)
    first = ui._render()
    second = ui._render()

    # chart output is index 7: rendered_at(0), snapshot(1), 4 sections
    # (2-5), history message(6), history chart(7), history caption(8).
    assert first[7]["visible"] is False
    assert second[7]["visible"] is True
    assert second[7]["value"]["portfolio_value"].tolist() == [100500.0]


# --- Sprint 8B: Trading Intelligence Command Center -------------------------


def _kpi_block(demo):
    blocks = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and "mb-kpi-row" in (b.elem_classes or [])
    ]
    assert len(blocks) == 1
    return blocks[0]


def _drawdown_chart(demo):
    charts = [b for b in demo.blocks.values() if isinstance(b, gr.LinePlot)]
    assert len(charts) == 2  # value chart + drawdown chart
    drawdown = [
        c for c in charts if "mb-portfolio-drawdown-chart" in (c.elem_classes or [])
    ]
    assert len(drawdown) == 1
    return drawdown[0]


def _drilldown_cards(demo):
    return [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and "mb-drilldown-card" in (b.elem_classes or [])
    ]


# --- KPI row -----------------------------------------------------------


def test_kpi_row_unavailable_by_default():
    demo = MorningBriefUI().build()

    block = _kpi_block(demo)
    assert "not available" in block.value.lower()


def test_kpi_row_populated_renders_all_six_facts():
    kpis = PortfolioKpis(
        total_value=103000.0, available_cash=37000.0, invested_amount=66000.0,
        open_positions=7, risk_state="NORMAL",
        todays_change_usd=3000.0, todays_change_pct=3.0,
    )
    screen = replace(build_mock_screen(), kpis=kpis)
    demo = MorningBriefUI(screen=screen).build()

    block = _kpi_block(demo)
    assert "$103,000.00" in block.value
    assert "$37,000.00" in block.value
    assert "7" in block.value
    assert "NORMAL" in block.value
    assert "+$3,000.00" in block.value
    assert "+3.00%" in block.value
    assert "64.08%" in block.value  # invested_pct = 66000/103000*100


def test_kpi_row_negative_change_renders_the_minus_sign_and_the_negative_token():
    """Impeccable critique finding #5: a negative Today's Change gets the
    product's one restrained --aara-negative-fg token (mb-kpi-value--
    negative), not a red/green stoplight color -- and the minus sign in
    the text is unchanged and remains the primary signal either way."""
    kpis = PortfolioKpis(
        total_value=97000.0, available_cash=37000.0, invested_amount=60000.0,
        todays_change_usd=-3000.0, todays_change_pct=-3.0,
    )
    screen = replace(build_mock_screen(), kpis=kpis)
    demo = MorningBriefUI(screen=screen).build()

    block = _kpi_block(demo)
    assert "-$3,000.00" in block.value
    assert "-3.00%" in block.value
    assert "mb-kpi-value--negative" in block.value


def test_kpi_row_positive_change_does_not_render_the_negative_token():
    kpis = PortfolioKpis(
        total_value=103000.0, available_cash=37000.0, invested_amount=66000.0,
        todays_change_usd=3000.0, todays_change_pct=3.0,
    )
    screen = replace(build_mock_screen(), kpis=kpis)
    demo = MorningBriefUI(screen=screen).build()

    block = _kpi_block(demo)
    assert "+$3,000.00" in block.value
    assert "mb-kpi-value--negative" not in block.value


def test_kpi_row_zero_change_does_not_render_the_negative_token():
    """Zero is not negative -- it must retain the same plain treatment as
    a positive value."""
    kpis = PortfolioKpis(
        total_value=100000.0, available_cash=37000.0, invested_amount=63000.0,
        todays_change_usd=0.0, todays_change_pct=0.0,
    )
    screen = replace(build_mock_screen(), kpis=kpis)
    demo = MorningBriefUI(screen=screen).build()

    block = _kpi_block(demo)
    assert "+$0.00" in block.value
    assert "mb-kpi-value--negative" not in block.value


def test_kpi_row_only_todays_change_can_carry_the_negative_token():
    """The other five KPI values never take the negative modifier, even
    though this fixture's own totals could technically be read as signed
    numbers -- only Today's Change is a delta in this domain."""
    kpis = PortfolioKpis(
        total_value=97000.0, available_cash=37000.0, invested_amount=60000.0,
        open_positions=7, risk_state="NORMAL",
        todays_change_usd=-3000.0, todays_change_pct=-3.0,
    )
    screen = replace(build_mock_screen(), kpis=kpis)
    demo = MorningBriefUI(screen=screen).build()

    block = _kpi_block(demo)
    assert block.value.count("mb-kpi-value--negative") == 1


def test_theme_defines_the_negative_kpi_token_and_reuses_aara_negative_fg():
    assert "--mb-color-negative: var(--aara-negative-fg, #7A2E2E);" in CSS
    assert ".mb-kpi-value--negative {" in CSS
    assert "color: var(--mb-color-negative);" in CSS


def test_kpi_row_missing_optional_facts_render_an_honest_placeholder_not_fabricated_data():
    kpis = PortfolioKpis(total_value=100000.0, available_cash=40000.0, invested_amount=60000.0)
    screen = replace(build_mock_screen(), kpis=kpis)
    demo = MorningBriefUI(screen=screen).build()

    block = _kpi_block(demo)
    # No open_positions / risk_state / todays_change supplied -- must not
    # invent a count, a state, or a $/% figure.
    assert "None" not in block.value


# --- Drawdown chart ------------------------------------------------------


def test_drawdown_unavailable_by_default_renders_the_message_and_hides_the_chart():
    demo = MorningBriefUI().build()

    html_values = _html_values(demo)
    assert any("aara-integration-status" in v for v in html_values)
    assert _drawdown_chart(demo).visible is False


def test_drawdown_empty_renders_the_message_and_hides_the_chart():
    screen = replace(build_mock_screen(), drawdown_history=())
    demo = MorningBriefUI(screen=screen).build()

    html_values = _html_values(demo)
    assert any("No portfolio history is recorded yet." in v for v in html_values)
    assert _drawdown_chart(demo).visible is False


def test_drawdown_with_real_points_renders_the_chart():
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100000.0, drawdown_pct=0.0),
        DrawdownPoint(as_of="2026-09-02T00:00:00+00:00", portfolio_value=95000.0, drawdown_pct=5.0),
    )
    screen = replace(build_mock_screen(), drawdown_history=points)
    demo = MorningBriefUI(screen=screen).build()

    chart = _drawdown_chart(demo)
    assert chart.visible is True
    assert [row[1] for row in chart.value["data"]] == [0.0, 5.0]


def test_drawdown_chart_has_only_the_two_real_columns():
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100000.0, drawdown_pct=0.0),
    )
    screen = replace(build_mock_screen(), drawdown_history=points)
    chart = _drawdown_chart(MorningBriefUI(screen=screen).build())

    assert set(chart.value["columns"]) == {"as_of", "drawdown_pct"}


def test_drawdown_caption_shows_the_most_recent_point_as_of_human_readable():
    """Hardening (combined Sprint 5+6+7): mirrors the Portfolio Value
    Trend chart's own caption fix -- the raw ISO-8601 timestamp must never
    be shown verbatim; it must use the SAME human-readable "%Y-%m-%d %H:%M
    %Z" America/Chicago format every other "as of" line on this screen
    already uses. 2026-09-02T00:00:00+00:00 (UTC) is 2026-09-01 19:00 CDT."""
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100000.0, drawdown_pct=0.0),
        DrawdownPoint(as_of="2026-09-02T00:00:00+00:00", portfolio_value=95000.0, drawdown_pct=5.0),
    )
    screen = replace(build_mock_screen(), drawdown_history=points)

    combined = "\n".join(_html_values(MorningBriefUI(screen=screen).build()))

    assert f"{_SECTION_AS_OF_PREFIX}2026-09-01 19:00 CDT" in combined
    assert "2026-09-02T00:00:00+00:00" not in combined


def test_drawdown_refresh_updates_the_chart():
    empty_screen = replace(build_mock_screen(), drawdown_history=())
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100000.0, drawdown_pct=7.5),
    )
    populated_screen = replace(build_mock_screen(), drawdown_history=points)
    calls = []

    def provider():
        calls.append(True)
        return empty_screen if len(calls) <= 2 else populated_screen

    ui = MorningBriefUI(screen_provider=provider)
    first = ui._render()
    second = ui._render()

    # New outputs are appended at the end: index 11 is the KPI row, 12 is
    # the drawdown message, 13 is the drawdown chart, 14 is the caption.
    assert first[13]["visible"] is False
    assert second[13]["visible"] is True
    assert second[13]["value"]["drawdown_pct"].tolist() == [7.5]


# --- Condensed Morning Brief grid ----------------------------------------


def test_existing_sections_still_render_inside_the_condensed_grid():
    """Structural change only -- the four existing sections' own real
    content must render unchanged, just inside a new card-grid layout."""
    screen = _real_portfolio_screen()
    demo = MorningBriefUI(screen=screen).build()

    combined = "\n".join(_html_values(demo))
    assert "Total value $1.00" in combined
    assert PORTFOLIO_SNAPSHOT_TITLE in combined
    assert MARKET_MOOD_REGIME_TITLE in combined
    assert CANDIDATE_SCREENING_SUMMARY_TITLE in combined
    assert OVERNIGHT_HOLDINGS_NEWS_TITLE in combined


def test_brief_grid_wrapper_is_present():
    rows = [b for b in MorningBriefUI().build().blocks.values() if isinstance(b, gr.Row)]
    assert any("mb-brief-grid" in (r.elem_classes or []) for r in rows)


# --- Drill-down navigation cards ------------------------------------------


_EXPECTED_DRILLDOWN_TARGETS = (
    "Portfolio Intelligence", "Decision Center", "Risk Intelligence",
    "Performance & Learning",
)


def test_drilldown_cards_present_for_the_four_expected_screens():
    demo = MorningBriefUI().build()
    cards = _drilldown_cards(demo)

    assert len(cards) == 4
    values = "\n".join(c.value for c in cards)
    for label in _EXPECTED_DRILLDOWN_TARGETS:
        assert f'data-target-label="{label}"' in values


def test_drilldown_cards_are_present_regardless_of_screen_state():
    """Static, non-refreshed content -- present even on the fully
    unavailable default screen, and unaffected by Refresh."""
    demo = MorningBriefUI().build()
    cards = _drilldown_cards(demo)
    assert len(cards) == 4


def test_drilldown_cards_do_not_appear_in_render_outputs():
    """Fully static -- must not grow _OUTPUT_COUNT or the render tuple."""
    ui = MorningBriefUI()
    assert len(ui._render()) == _OUTPUT_COUNT


def test_drilldown_row_wrapper_is_present():
    rows = [b for b in MorningBriefUI().build().blocks.values() if isinstance(b, gr.Row)]
    assert any("mb-drilldown-row" in (r.elem_classes or []) for r in rows)


def test_no_fake_or_illustrative_data_anywhere_on_the_command_center():
    """Task guardrail: even fully populated, nothing on this screen may be
    invented -- every KPI/chart/drilldown value traces to a real seeded
    fact or a static, non-data label."""
    kpis = PortfolioKpis(
        total_value=103000.0, available_cash=37000.0, invested_amount=66000.0,
        open_positions=7, risk_state="NORMAL",
        todays_change_usd=3000.0, todays_change_pct=3.0,
    )
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=103000.0, drawdown_pct=0.0),
    )
    screen = replace(build_mock_screen(), kpis=kpis, drawdown_history=points)
    demo = MorningBriefUI(screen=screen).build()

    combined = "\n".join(_html_values(demo))
    assert "Illustrative Data" not in combined
    assert "illustrative" not in combined.lower()


# --- Decision Activity & Risk State Context sprint -------------------------


def _decision_activity_block(demo):
    return [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and "mb-decision-activity-output" in (b.elem_classes or [])
    ]


def _risk_state_block(demo):
    return [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and "mb-risk-state-output" in (b.elem_classes or [])
    ]


def test_decision_activity_unavailable_by_default():
    """Default mock screen: decision_activity_summary is None."""
    demo = MorningBriefUI().build()

    blocks = _decision_activity_block(demo)
    assert len(blocks) == 1
    assert blocks[0].visible is True
    assert _DECISION_ACTIVITY_UNAVAILABLE_MESSAGE in blocks[0].value


def test_decision_activity_populated_renders_the_real_summary():
    summary = "3 BUY decisions in the last 24h, 1 already resolved."
    screen = replace(build_mock_screen(), decision_activity_summary=summary)
    demo = MorningBriefUI(screen=screen).build()

    block = _decision_activity_block(demo)[0]
    assert block.visible is True
    assert summary in block.value
    assert _DECISION_ACTIVITY_UNAVAILABLE_MESSAGE not in block.value


def test_decision_activity_never_implies_recommendation_or_opportunity():
    """Task guardrail: this is a factual activity count, never a
    recommendation or a trading opportunity."""
    summary = "5 BUY decisions in the last 24h, 2 already resolved."
    screen = replace(build_mock_screen(), decision_activity_summary=summary)
    demo = MorningBriefUI(screen=screen).build()

    lowered = "\n".join(_html_values(demo)).lower()
    for forbidden in ("recommend", "opportunity", "you should", "consider buying"):
        assert forbidden not in lowered


def test_risk_state_unavailable_by_default():
    demo = MorningBriefUI().build()

    blocks = _risk_state_block(demo)
    assert len(blocks) == 1
    assert blocks[0].visible is True
    assert _RISK_STATE_UNAVAILABLE_MESSAGE in blocks[0].value


def test_risk_state_populated_renders_the_real_summary():
    summary = "Current risk state: NORMAL (as of 2026-09-01 14:00 CDT)."
    screen = replace(build_mock_screen(), current_risk_state_summary=summary)
    demo = MorningBriefUI(screen=screen).build()

    block = _risk_state_block(demo)[0]
    assert block.visible is True
    assert summary in block.value
    assert _RISK_STATE_UNAVAILABLE_MESSAGE not in block.value


def test_risk_state_never_implies_enforcement_causality_or_advice():
    summary = "Current risk state: WARNING (as of 2026-09-01 14:00 CDT)."
    screen = replace(build_mock_screen(), current_risk_state_summary=summary)
    demo = MorningBriefUI(screen=screen).build()

    lowered = "\n".join(_html_values(demo)).lower()
    for forbidden in ("enforced", "caused by", "predict", "you should", "recommend"):
        assert forbidden not in lowered


def test_decision_activity_unavailable_does_not_hide_risk_state():
    screen = replace(
        build_mock_screen(),
        current_risk_state_summary="Current risk state: NORMAL (as of 2026-09-01 14:00 CDT).",
    )
    demo = MorningBriefUI(screen=screen).build()

    assert _decision_activity_block(demo)[0].visible is True
    assert _DECISION_ACTIVITY_UNAVAILABLE_MESSAGE in _decision_activity_block(demo)[0].value
    assert "NORMAL" in _risk_state_block(demo)[0].value


def test_risk_state_unavailable_does_not_hide_decision_activity():
    screen = replace(
        build_mock_screen(),
        decision_activity_summary="2 BUY decisions in the last 24h, 0 already resolved.",
    )
    demo = MorningBriefUI(screen=screen).build()

    assert "2 BUY decisions" in _decision_activity_block(demo)[0].value
    assert _RISK_STATE_UNAVAILABLE_MESSAGE in _risk_state_block(demo)[0].value


def test_decision_activity_and_risk_state_both_unavailable():
    demo = MorningBriefUI().build()

    assert _DECISION_ACTIVITY_UNAVAILABLE_MESSAGE in _decision_activity_block(demo)[0].value
    assert _RISK_STATE_UNAVAILABLE_MESSAGE in _risk_state_block(demo)[0].value


def test_decision_activity_and_risk_state_both_populated():
    screen = replace(
        build_mock_screen(),
        decision_activity_summary="4 BUY decisions in the last 24h, 3 already resolved.",
        current_risk_state_summary="Current risk state: DEFENSIVE (as of 2026-09-01 14:00 CDT).",
    )
    demo = MorningBriefUI(screen=screen).build()

    assert "4 BUY decisions" in _decision_activity_block(demo)[0].value
    assert "DEFENSIVE" in _risk_state_block(demo)[0].value


def test_decision_activity_and_risk_state_do_not_disturb_existing_sections():
    """Regression guard: adding the two new facts must not disturb the
    existing four-section rendering or the portfolio history chart."""
    screen = replace(
        _real_portfolio_screen(),
        decision_activity_summary="1 BUY decisions in the last 24h, 0 already resolved.",
        current_risk_state_summary="Current risk state: NORMAL (as of 2026-09-01 14:00 CDT).",
    )
    combined = "\n".join(_html_values(MorningBriefUI(screen=screen).build()))

    assert "Total value $1.00" in combined
    assert PORTFOLIO_SNAPSHOT_TITLE in combined
    assert MARKET_MOOD_REGIME_TITLE in combined
    assert CANDIDATE_SCREENING_SUMMARY_TITLE in combined
    assert OVERNIGHT_HOLDINGS_NEWS_TITLE in combined


def test_decision_activity_and_risk_state_refresh_updates():
    empty_screen = build_mock_screen()
    populated_screen = replace(
        build_mock_screen(),
        decision_activity_summary="6 BUY decisions in the last 24h, 4 already resolved.",
        current_risk_state_summary="Current risk state: NORMAL (as of 2026-09-01 14:00 CDT).",
    )
    calls = []

    def provider():
        calls.append(True)
        return empty_screen if len(calls) <= 2 else populated_screen

    ui = MorningBriefUI(screen_provider=provider)
    first = ui._render()
    second = ui._render()

    # New outputs are appended at the end: index 9 is decision activity,
    # index 10 is current risk state.
    assert _DECISION_ACTIVITY_UNAVAILABLE_MESSAGE in first[9]["value"]
    assert "6 BUY decisions" in second[9]["value"]
    assert _RISK_STATE_UNAVAILABLE_MESSAGE in first[10]["value"]
    assert "NORMAL" in second[10]["value"]
