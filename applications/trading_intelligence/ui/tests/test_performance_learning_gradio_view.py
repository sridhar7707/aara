from dataclasses import replace

import gradio as gr

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.projections.calibration_band import CalibrationBand
from applications.trading_intelligence.projections.regime_outcome_row import RegimeOutcomeRow
from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    _RENDERED_AT_PREFIX,
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import (
    build_calibration_preview_screen,
    build_mock_screen,
    build_regime_outcome_preview_screen,
)
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    CALIBRATION_CONTENT_HEADING,
    CALIBRATION_DISCLAIMER,
    CALIBRATION_MIN_OUTCOMES,
    EVIDENCE_MATURITY_DISCLAIMER,
    LOSS_REVIEW_DISCLAIMER,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
    REGIME_OUTCOMES_DISCLAIMER,
    REGIME_OUTCOMES_TITLE,
    OutcomeHistoryRow,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)
from applications.trading_intelligence.ui.performance_learning.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html


def _html_values(demo):
    return [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML) and isinstance(getattr(block, "value", None), str)
    ]


def _visible_html(demo):
    return "\n".join(
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML)
        and isinstance(getattr(block, "value", None), str)
        and block.visible
    )


_CAL_PROVIDER = "trades_db_outcomes"


def _calibration_screen(bands, *, health=None):
    base = build_mock_screen()
    return PerformanceLearningScreen(
        outcome_history=base.outcome_history,
        attribution_breakdown=base.attribution_breakdown,
        model_confidence_calibration=base.model_confidence_calibration,
        calibration_health=health or IntegrationHealth.healthy(_CAL_PROVIDER),
        calibration_bands=tuple(bands),
    )


def _band(label, wins, losses):
    return CalibrationBand(label=label, wins=wins, losses=losses)


def test_ui_can_be_constructed_with_default_mock_screen():
    ui = PerformanceLearningUI()

    assert ui._screen == build_mock_screen()


def test_build_returns_a_gradio_blocks_instance():
    ui = PerformanceLearningUI()

    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_shell_header_and_nav_are_present_in_the_built_layout():
    ui = PerformanceLearningUI()

    demo = ui.build()

    html_values = _html_values(demo)
    assert SHELL_IDENTITY_HTML in html_values
    assert build_shell_nav_html("Performance & Learning") in html_values


def test_shell_header_and_nav_blocks_carry_the_expected_elem_classes():
    ui = PerformanceLearningUI()

    demo = ui.build()

    html_blocks = [block for block in demo.blocks.values() if isinstance(block, gr.HTML)]
    assert any("aara-shell-header" in (block.elem_classes or []) for block in html_blocks)
    assert any("aara-shell-nav" in (block.elem_classes or []) for block in html_blocks)


def test_page_title_carries_the_shared_eyebrow_treatment():
    """Impeccable critique finding #4: the page title uses the shared
    .aara-page-title primitive (design_system.py) instead of a plain
    mixed-case <h2>, matching the treatment now applied consistently
    across all six screens."""
    ui = PerformanceLearningUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert '<h2 class="aara-page-title">Performance & Learning</h2>' in combined


def test_theme_mirrors_the_shared_page_title_treatment_for_standalone_render():
    """Visual-quality pass (2026-09-17): normal-case, not uppercase/
    tracked -- matches design_system.py's .aara-page-title primitive."""
    block = CSS.split(".pl-page-header h2 {")[1].split("}")[0]
    assert "text-transform" not in block
    assert "font-weight: 700;" in block
    assert "color: var(--pl-color-navy);" in block


def test_all_three_frozen_section_titles_render():
    ui = PerformanceLearningUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert OUTCOME_HISTORY_TITLE in combined
    assert ATTRIBUTION_BREAKDOWN_TITLE in combined
    assert MODEL_CONFIDENCE_CALIBRATION_TITLE in combined


def test_all_three_sections_render_their_own_unavailable_message():
    screen = build_mock_screen()
    ui = PerformanceLearningUI(screen=screen)

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    for section in screen.sections:
        assert section.unavailable_message in combined


def test_outcome_history_dataframe_is_present_but_hidden_when_unavailable():
    """Wave 2B: the Outcome History table is part of the stable component
    tree (like Risk Intelligence's history Dataframe), created once and
    hidden until a HEALTHY read with decisions exists. The no-provider
    default screen is unavailable, so the table must be present and
    `visible is False`."""
    ui = PerformanceLearningUI()

    demo = ui.build()

    dataframes = [block for block in demo.blocks.values() if isinstance(block, gr.Dataframe)]
    assert len(dataframes) == 1
    assert dataframes[0].visible is False
    assert "pl-outcome-table" in (dataframes[0].elem_classes or [])


def test_no_illustrative_data_disclosure_is_rendered():
    """Portfolio/Risk Intelligence show an "Illustrative Data" banner for
    their own fabricated numbers -- Performance & Learning must not, since
    it fabricates nothing (no fake numerical metrics or fake outcomes)."""
    ui = PerformanceLearningUI()

    demo = ui.build()

    combined = "\n".join(_html_values(demo))
    assert "Illustrative Data" not in combined


# --- Sprint 1 Phase 3: Loss/failure-analysis callout render ---------------


_OUTCOME_ROW = OutcomeHistoryRow(
    decision="AMZN BUY · trade-38", entry_date="2026-07-16 11:50 CDT", status="CLOSED",
    exit_date="2026-09-02 09:33 CDT", holding_days="47", realized_pnl_usd="-27.77",
    realized_pnl_pct="-0.23%", exit_basis="Bot fill",
    pairing_method="WINDOW_SINGLE_BOT_EXIT", pairing_confidence="HIGH", direction="LOSS",
)


def _populated_outcome_screen(*, loss_review_summary):
    return replace(
        build_mock_screen(),
        outcome_health=IntegrationHealth.healthy(_CAL_PROVIDER),
        outcome_rows=(_OUTCOME_ROW,),
        summary="1 BUY decisions — 1 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
        win_rate_summary="Not enough completed trades yet for a win rate (1 of 30 needed).",
        loss_review_summary=loss_review_summary,
    )


def _outcome_table(demo):
    dataframes = [b for b in demo.blocks.values() if isinstance(b, gr.Dataframe)]
    assert len(dataframes) == 1
    return dataframes[0]


# --- Impeccable critique finding #5: Realized P&L negative token --------


def test_negative_realized_pnl_renders_the_negative_token_in_the_table():
    """Realized P&L $ / % are the two Outcome History columns holding a
    signed P&L figure -- a real loss gets the product's one restrained
    --aara-negative-fg token, not a red/green stoplight color. The minus
    sign already in the cell's own text (e.g. "-27.77") is unchanged and
    remains the primary signal; this is reinforcement, not the only cue."""
    screen = replace(
        build_mock_screen(),
        outcome_health=IntegrationHealth.healthy(_CAL_PROVIDER),
        outcome_rows=(_OUTCOME_ROW,),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    row = _outcome_table(demo).value["data"][0]
    assert row[5] == '<span class="pl-negative-value">-27.77</span>'
    assert row[6] == '<span class="pl-negative-value">-0.23%</span>'


def test_positive_realized_pnl_does_not_render_the_negative_token_in_the_table():
    positive_row = replace(_OUTCOME_ROW, realized_pnl_usd="88.10", realized_pnl_pct="1.47%")
    screen = replace(
        build_mock_screen(),
        outcome_health=IntegrationHealth.healthy(_CAL_PROVIDER),
        outcome_rows=(positive_row,),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    row = _outcome_table(demo).value["data"][0]
    assert row[5] == "88.10"
    assert row[6] == "1.47%"
    assert "pl-negative-value" not in row[5]
    assert "pl-negative-value" not in row[6]


def test_not_applicable_realized_pnl_does_not_render_the_negative_token_in_the_table():
    """An OPEN/PENDING outcome's realized_pnl_usd/_pct is the empty string
    ("not applicable to this outcome's state", per OutcomeHistoryRow's own
    docstring) -- it must never be mistaken for a negative/zero value."""
    open_row = replace(
        _OUTCOME_ROW, status="OPEN", realized_pnl_usd="", realized_pnl_pct="",
    )
    screen = replace(
        build_mock_screen(),
        outcome_health=IntegrationHealth.healthy(_CAL_PROVIDER),
        outcome_rows=(open_row,),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    row = _outcome_table(demo).value["data"][0]
    assert row[5] == ""
    assert row[6] == ""


def test_only_the_two_realized_pnl_columns_use_markdown_datatype():
    """Every other Outcome History column must stay "str" -- unchanged,
    plain, Gradio-escaped text -- exactly as before this task."""
    demo = PerformanceLearningUI().build()

    table = _outcome_table(demo)
    assert table.datatype[5] == "markdown"
    assert table.datatype[6] == "markdown"
    other_indices = [i for i in range(len(table.datatype)) if i not in (5, 6)]
    assert all(table.datatype[i] == "str" for i in other_indices)


def test_theme_defines_the_negative_value_token_and_reuses_aara_negative_fg():
    assert "--pl-color-negative: var(--aara-negative-fg, #7A2E2E);" in CSS
    assert ".pl-outcome-table .pl-negative-value {" in CSS
    assert "color: var(--pl-color-negative);" in CSS


def test_loss_review_hidden_by_default_when_outcome_history_unavailable():
    demo = PerformanceLearningUI().build()

    visible = _visible_html(demo)
    assert LOSS_REVIEW_DISCLAIMER not in visible


def test_loss_review_callout_renders_the_summary_and_disclaimer_when_populated():
    screen = _populated_outcome_screen(
        loss_review_summary=(
            "1 of 1 closed BUY decisions realized a loss. "
            "Realized loss range: -0.23% to -0.23%. Holding period: 47 days."
        ),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "1 of 1 closed BUY decisions realized a loss." in visible
    assert "Realized loss range: -0.23% to -0.23%." in visible
    assert LOSS_REVIEW_DISCLAIMER in visible


def test_loss_review_callout_renders_the_honest_no_losses_message():
    screen = _populated_outcome_screen(
        loss_review_summary=(
            "No closed BUY decisions have realized a loss in the current "
            "trades snapshot."
        ),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "No closed BUY decisions have realized a loss" in visible
    # the disclaimer still accompanies the honest "no losses" fact
    assert LOSS_REVIEW_DISCLAIMER in visible


def test_loss_review_never_claims_a_cause_pattern_or_significance():
    """Task guardrail: the callout's own SUMMARY sentence must be
    descriptive, never predictive -- it must never claim a cause, an
    identified pattern, or statistical significance. (The accompanying
    LOSS_REVIEW_DISCLAIMER legitimately names and explicitly negates these
    same concepts -- e.g. "...does not explain why any decision lost,
    identify a pattern, or claim statistical significance" -- so this check
    is scoped to the summary text only, not the full rendered block.)"""
    summary = (
        "2 of 3 closed BUY decisions realized a loss. "
        "Realized loss range: -9.80% to -0.23%. "
        "Holding period range: 3 to 47 days."
    )
    screen = _populated_outcome_screen(loss_review_summary=summary)
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert summary in visible
    lowered = summary.lower()
    for forbidden in (
        "because", "caused by", "due to", "predict", "significant",
        "pattern", "likely to", "tends to", "correlat",
    ):
        assert forbidden not in lowered


def test_loss_review_html_escapes_interpolated_summary():
    html_out = PerformanceLearningUI._format_loss_review_html(
        _populated_outcome_screen(loss_review_summary="<script>alert(1)</script>")
    )
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_loss_review_is_empty_string_when_summary_is_none():
    screen = _populated_outcome_screen(loss_review_summary=None)
    assert PerformanceLearningUI._format_loss_review_html(screen) == ""


def test_loss_review_does_not_disturb_win_rate_or_summary_rendering():
    screen = _populated_outcome_screen(
        loss_review_summary=(
            "1 of 1 closed BUY decisions realized a loss. "
            "Realized loss range: -0.23% to -0.23%. Holding period: 47 days."
        ),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert screen.summary in visible
    assert screen.win_rate_summary in visible


# --- Sprint 4 #1: Model Confidence Calibration render ---------------------


def test_calibration_section_still_uses_the_frozen_ia_label():
    demo = PerformanceLearningUI().build()

    assert MODEL_CONFIDENCE_CALIBRATION_TITLE in "\n".join(_html_values(demo))


def test_calibration_unavailable_by_default_shows_section_message_hides_table():
    demo = PerformanceLearningUI().build()

    visible = _visible_html(demo)
    assert build_mock_screen().model_confidence_calibration.unavailable_message in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_renders_historical_outcome_heading_when_enough_data():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    assert CALIBRATION_CONTENT_HEADING in visible
    assert "predictive accuracy" not in visible.lower()
    assert "probability calibration" not in visible.lower()
    assert "guaranteed" not in visible.lower()
    assert "certainty" not in visible.lower()


def test_calibration_table_lists_every_band_with_counts_and_win_rate():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    for label in ("0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-1.00"):
        assert label in visible
    # 0.60-0.65 preview band is 9 wins / 6 losses -> 60%
    assert "60%" in visible
    # the empty 0.55-0.60 band shows a zero count and no fabricated rate
    assert ">0<" in visible


def test_calibration_small_n_shows_notice_not_table():
    screen = _calibration_screen([_band("0.60-0.65", 2, 1)])
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert str(CALIBRATION_MIN_OUTCOMES) in visible
    assert "Only 3 closed BUY outcomes" in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_empty_state_message_when_healthy_with_no_qualifying_outcomes():
    screen = _calibration_screen([_band("0.60-0.65", 0, 0)])
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "No closed BUY decisions with a recorded ensemble score" in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_non_healthy_read_uses_shared_unavailable_phrase():
    screen = _calibration_screen(
        [_band("0.60-0.65", 5, 5)],
        health=IntegrationHealth.unavailable(_CAL_PROVIDER, detail="no snapshot"),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "Data unavailable" in visible
    assert CALIBRATION_CONTENT_HEADING not in visible


def test_calibration_table_html_escapes_interpolated_values():
    html = PerformanceLearningUI._format_calibration_table_html(
        _calibration_screen([_band("<script>", 1, 0)] + [_band("x", 0, 0)] * 3)
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# --- Sprint 4 Item #4: Realized outcomes by entry regime render ---------


def _regime_screen(rows, *, health=None):
    return replace(
        build_mock_screen(),
        regime_outcome_health=health or IntegrationHealth.healthy(_CAL_PROVIDER),
        regime_outcome_rows=tuple(rows),
    )


def _rrow(label, wins, losses):
    return RegimeOutcomeRow(regime=label, wins=wins, losses=losses)


def test_regime_outcomes_section_title_renders():
    demo = PerformanceLearningUI().build()

    assert REGIME_OUTCOMES_TITLE in "\n".join(_html_values(demo))


def test_regime_outcomes_unavailable_by_default_hides_the_table():
    demo = PerformanceLearningUI().build()

    visible = _visible_html(demo)
    assert "Realized outcomes by regime are unavailable" in visible
    assert "Entry regime</th>" not in visible


def test_regime_outcomes_table_lists_each_regime_with_counts_and_win_rate():
    screen = build_regime_outcome_preview_screen()
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    for label in ("RANGING", "TRENDING", "VOLATILE", "Not recorded"):
        assert label in visible
    # RANGING preview row is 7 wins / 5 losses -> 58%
    assert "58%" in visible

    # neutral / non-predictive wording only, scoped to the regime block itself
    block = PerformanceLearningUI._format_regime_outcomes_table_html(screen).lower()
    for forbidden in ("predict", "probability", "calibrat", "ai score",
                      "guaranteed", "certainty"):
        assert forbidden not in block


def test_regime_outcomes_empty_state_when_healthy_with_no_rows():
    demo = PerformanceLearningUI(screen=_regime_screen([])).build()

    visible = _visible_html(demo)
    assert "No closed BUY decisions with a realized win or loss" in visible


def test_regime_outcomes_non_healthy_read_uses_shared_unavailable_phrase():
    screen = _regime_screen(
        [_rrow("RANGING", 5, 5)],
        health=IntegrationHealth.unavailable(_CAL_PROVIDER, detail="no snapshot"),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert "Data unavailable" in visible


def test_regime_outcomes_table_html_escapes_interpolated_values():
    out = PerformanceLearningUI._format_regime_outcomes_table_html(
        _regime_screen([_rrow("<script>", 1, 0), _rrow("RANGING", 0, 1)])
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_regime_outcomes_blank_win_rate_for_a_zero_count_row_is_not_rendered_as_zero_percent():
    out = PerformanceLearningUI._format_regime_outcomes_table_html(
        _regime_screen([_rrow("RANGING", 0, 0)])
    )
    assert "0%" not in out


def test_regime_outcomes_does_not_disturb_calibration_rendering():
    screen = replace(
        build_calibration_preview_screen(),
        regime_outcome_health=IntegrationHealth.healthy(_CAL_PROVIDER),
        regime_outcome_rows=(_rrow("RANGING", 5, 5),),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert CALIBRATION_CONTENT_HEADING in visible
    assert REGIME_OUTCOMES_TITLE in visible


# --- Prominent Sample-Size Banner -----------------------------------------


def _evidence_maturity_block(demo):
    blocks = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and "pl-evidence-maturity" in (b.elem_classes or [])
    ]
    assert len(blocks) == 1
    return blocks[0]


def test_evidence_maturity_unavailable_by_default():
    """Default mock screen: calibration_health is None (no provider)."""
    demo = PerformanceLearningUI().build()

    block = _evidence_maturity_block(demo)
    assert "not available" in block.value.lower()


def test_evidence_maturity_unavailable_on_non_healthy_read():
    screen = _calibration_screen(
        [_band("0.50-0.55", 5, 5)],
        health=IntegrationHealth.unavailable(_CAL_PROVIDER, detail="x"),
    )
    demo = PerformanceLearningUI(screen=screen).build()

    block = _evidence_maturity_block(demo)
    assert "unavailable" in block.value.lower() or "not available" in block.value.lower()


def test_evidence_maturity_empty_real_zero_renders_honestly():
    screen = _calibration_screen([
        _band("0.50-0.55", 0, 0), _band("0.55-0.60", 0, 0),
        _band("0.60-0.65", 0, 0), _band("0.65-1.00", 0, 0),
    ])
    demo = PerformanceLearningUI(screen=screen).build()

    block = _evidence_maturity_block(demo)
    assert f"0 of {CALIBRATION_MIN_OUTCOMES}" in block.value
    assert "Below the established floor" in block.value


def test_evidence_maturity_below_floor_renders_the_real_count_and_floor():
    screen = _calibration_screen([
        _band("0.50-0.55", 2, 2), _band("0.55-0.60", 3, 3),
        _band("0.60-0.65", 2, 3), _band("0.65-1.00", 0, 0),
    ])
    demo = PerformanceLearningUI(screen=screen).build()

    block = _evidence_maturity_block(demo)
    assert f"15 of {CALIBRATION_MIN_OUTCOMES}" in block.value
    assert "Below the established floor" in block.value
    assert EVIDENCE_MATURITY_DISCLAIMER in block.value


def test_evidence_maturity_exactly_at_floor_renders_reached():
    screen = _calibration_screen([
        _band("0.50-0.55", 4, 4), _band("0.55-0.60", 4, 4),
        _band("0.60-0.65", 4, 4), _band("0.65-1.00", 3, 3),
    ])
    demo = PerformanceLearningUI(screen=screen).build()

    block = _evidence_maturity_block(demo)
    assert f"{CALIBRATION_MIN_OUTCOMES} of {CALIBRATION_MIN_OUTCOMES}" in block.value
    assert "reached" in block.value.lower()
    assert "Below the established floor" not in block.value


def test_evidence_maturity_above_floor_renders_reached():
    screen = _calibration_screen([
        _band("0.50-0.55", 10, 10), _band("0.55-0.60", 10, 10),
        _band("0.60-0.65", 5, 5), _band("0.65-1.00", 0, 0),
    ])
    demo = PerformanceLearningUI(screen=screen).build()

    block = _evidence_maturity_block(demo)
    assert f"50 of {CALIBRATION_MIN_OUTCOMES}" in block.value
    assert "reached" in block.value.lower()


def test_evidence_maturity_never_implies_significance_predictive_validity_or_readiness():
    """Task guardrail. EVIDENCE_MATURITY_DISCLAIMER itself legitimately
    NAMES "statistical significance"/"predictive validity"/"trading
    readiness" while denying them ("does not by itself imply..."); these
    phrase-level checks target an AFFIRMATIVE claim, not that honest
    negation -- same guard-scoping pattern this codebase already uses for
    a constant's own disclaimer text elsewhere (e.g. Risk Intelligence's
    Concentration disclaimer)."""
    below = _calibration_screen([_band("0.50-0.55", 5, 5)])
    above = _calibration_screen([
        _band("0.50-0.55", 10, 10), _band("0.55-0.60", 10, 10), _band("0.60-0.65", 5, 5),
    ])
    for screen in (below, above):
        block = _evidence_maturity_block(PerformanceLearningUI(screen=screen).build())
        lowered = block.value.lower()
        assert "does not by itself imply" in lowered  # the honest disclaimer is present
        for forbidden in (
            "is statistically significant", "is predictive", "is trading ready",
            "is reliable", "is accurate", "is calibrated",
        ):
            assert forbidden not in lowered


def test_evidence_maturity_does_not_disturb_calibration_or_outcome_rendering():
    """Regression guard: the new banner reuses calibration data but must
    not change the existing calibration/outcome-history rendering."""
    screen = build_calibration_preview_screen()
    demo = PerformanceLearningUI(screen=screen).build()

    visible = _visible_html(demo)
    assert CALIBRATION_CONTENT_HEADING in visible
    assert OUTCOME_HISTORY_TITLE in visible
    _evidence_maturity_block(demo)  # still present, no crash, no duplicate


def test_evidence_maturity_banner_introduces_no_button_or_load_event_of_its_own():
    """P0-2 (Refresh): this screen now has exactly ONE Button/demo.load()
    pair -- the shared Refresh mechanism every other screen already uses.
    The banner itself must not introduce a second, banner-specific
    button or handler beyond that one shared mechanism. Updated from the
    original 'no Refresh exists at all' premise, which P0-2 intentionally
    changes; the test's actual intent (the banner adds nothing of its
    own) is preserved."""
    screen = _calibration_screen([_band("0.50-0.55", 5, 5)])
    demo = PerformanceLearningUI(screen=screen).build()

    buttons = [b for b in demo.blocks.values() if isinstance(b, gr.Button)]
    assert len(buttons) == 1
    assert "aara-refresh-button" in (buttons[0].elem_classes or [])


# --- Sprint 1: visualization convention -- calibration + regime charts ----
#
# Both charts must be visible under EXACTLY the same condition as their
# own existing table -- CALIBRATION_MIN_OUTCOMES stays the one authoritative
# calibration gate, and the regime chart introduces NO new threshold.


def _calibration_chart(demo):
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.BarPlot) and "pl-calibration-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def _regime_chart(demo):
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.BarPlot) and "pl-regime-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def test_calibration_min_outcomes_is_unchanged_by_this_sprint():
    """Regression guard: adding a chart must never touch the authoritative
    evidence-maturity floor."""
    assert CALIBRATION_MIN_OUTCOMES == 30


# --- Calibration chart: visibility follows the existing table exactly ---


def test_calibration_chart_hidden_when_unavailable():
    demo = PerformanceLearningUI().build()  # default mock: cal_unavailable

    assert _calibration_chart(demo).visible is False


def test_calibration_chart_hidden_when_empty():
    screen = _calibration_screen([_band("0.60-0.65", 0, 0)])
    demo = PerformanceLearningUI(screen=screen).build()

    assert _calibration_chart(demo).visible is False


def test_calibration_chart_hidden_when_small_n():
    """29 total outcomes -- one below CALIBRATION_MIN_OUTCOMES -- the SAME
    small-N state the existing table is gated on; the chart must stay
    hidden, not introduce its own separate threshold."""
    screen = _calibration_screen([_band("0.60-0.65", 15, 14)])
    demo = PerformanceLearningUI(screen=screen).build()

    assert _calibration_chart(demo).visible is False


def test_calibration_chart_visible_when_enough_data():
    """Exactly CALIBRATION_MIN_OUTCOMES (30) -- the SAME floor the existing
    table uses -- must show the chart."""
    screen = _calibration_screen([_band("0.60-0.65", 15, 15)])
    demo = PerformanceLearningUI(screen=screen).build()

    assert _calibration_chart(demo).visible is True


def test_calibration_chart_and_table_visibility_always_match():
    """The chart's own visibility must never diverge from the existing
    table's -- checked across every gate state, not just one."""
    cases = [
        build_mock_screen(),                                   # unavailable
        _calibration_screen([_band("0.60-0.65", 0, 0)]),        # empty
        _calibration_screen([_band("0.60-0.65", 2, 1)]),        # small-N
        build_calibration_preview_screen(),                     # enough data
    ]
    for screen in cases:
        demo = PerformanceLearningUI(screen=screen).build()
        table_visible = CALIBRATION_CONTENT_HEADING in _visible_html(demo)
        assert _calibration_chart(demo).visible is table_visible


def test_calibration_chart_contains_the_expected_band_outcome_count_data():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    chart = _calibration_chart(demo)
    assert chart.value["columns"] == ["category", "outcome", "count"]
    rows = {(r[0], r[1]): r[2] for r in chart.value["data"]}
    # _CALIBRATION_PREVIEW_COUNTS: 0.50-0.55=(3,5), 0.55-0.60=(0,0),
    # 0.60-0.65=(9,6), 0.65-1.00=(6,1) -- see mock_data.py.
    assert rows[("0.50-0.55", "Win")] == 3
    assert rows[("0.50-0.55", "Loss")] == 5
    assert rows[("0.55-0.60", "Win")] == 0
    assert rows[("0.55-0.60", "Loss")] == 0
    assert rows[("0.60-0.65", "Win")] == 9
    assert rows[("0.60-0.65", "Loss")] == 6
    assert rows[("0.65-1.00", "Win")] == 6
    assert rows[("0.65-1.00", "Loss")] == 1


def test_calibration_chart_x_y_color_and_band_order_are_wired():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    chart = _calibration_chart(demo)
    assert chart.x == "category"
    assert chart.y == "count"
    assert chart.color == "outcome"
    assert chart.sort == ["0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-1.00"]


def test_calibration_chart_height_is_220():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    assert _calibration_chart(demo).height == 220


def test_calibration_chart_title_and_description_render_verbatim():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    assert CALIBRATION_CONTENT_HEADING in visible
    assert (
        "Realized win/loss counts for closed BUY decisions, grouped by "
        "entry ensemble score." in visible
    )


def test_calibration_disclaimer_renders_exactly_once():
    """The calibration table already renders CALIBRATION_DISCLAIMER as its
    own authoritative disclaimer -- the chart card must not repeat it."""
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    assert visible.count(CALIBRATION_DISCLAIMER) == 1


def test_calibration_chart_sits_inside_the_aara_card_treatment():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    cards = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Column) and "aara-card" in (b.elem_classes or [])
        and "pl-calibration-chart-card" in (b.elem_classes or [])
    ]
    assert len(cards) == 1
    assert cards[0].visible is True


def test_calibration_table_still_renders_unchanged_alongside_the_chart():
    """The existing table must render exactly as before -- the chart is
    additive, not a replacement."""
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    visible = _visible_html(demo)
    for label in ("0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-1.00"):
        assert label in visible
    assert "60%" in visible


def test_calibration_chart_comes_before_the_existing_table_in_render_order():
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    combined = "\n".join(_html_values(demo))
    assert combined.index(CALIBRATION_CONTENT_HEADING) < combined.index('class="pl-cal-table"')


# --- Regime chart: visibility follows the existing table exactly, no ----
# --- 30-outcome gate is ever applied to it -------------------------------


def test_regime_chart_hidden_when_unavailable():
    demo = PerformanceLearningUI().build()  # default mock: unavailable

    assert _regime_chart(demo).visible is False


def test_regime_chart_hidden_when_empty():
    demo = PerformanceLearningUI(screen=_regime_screen([])).build()

    assert _regime_chart(demo).visible is False


def test_regime_chart_visible_when_populated_even_far_below_30_outcomes():
    """Critical regime gate: a single row, n=1 -- nowhere near
    CALIBRATION_MIN_OUTCOMES -- must still show the chart. The regime
    section has never had a 30-outcome floor and this chart must not
    invent one."""
    screen = _regime_screen([_rrow("RANGING", 1, 0)])
    demo = PerformanceLearningUI(screen=screen).build()

    assert _regime_chart(demo).visible is True


def test_regime_chart_and_table_visibility_always_match():
    cases = [
        build_mock_screen(),                        # unavailable
        _regime_screen([]),                          # empty
        _regime_screen([_rrow("RANGING", 1, 0)]),     # populated, tiny sample
        build_regime_outcome_preview_screen(),        # populated
    ]
    for screen in cases:
        demo = PerformanceLearningUI(screen=screen).build()
        table_visible = "Entry regime</th>" in _visible_html(demo)
        assert _regime_chart(demo).visible is table_visible


def test_regime_chart_contains_the_expected_regime_outcome_count_data():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    chart = _regime_chart(demo)
    assert chart.value["columns"] == ["category", "outcome", "count"]
    rows = {(r[0], r[1]): r[2] for r in chart.value["data"]}
    # _REGIME_PREVIEW_ROWS: RANGING=(7,5), TRENDING=(9,3), VOLATILE=(2,6),
    # "Not recorded"=(1,2) -- see mock_data.py.
    assert rows[("RANGING", "Win")] == 7
    assert rows[("RANGING", "Loss")] == 5
    assert rows[("TRENDING", "Win")] == 9
    assert rows[("VOLATILE", "Loss")] == 6
    assert rows[("Not recorded", "Win")] == 1
    assert rows[("Not recorded", "Loss")] == 2


def test_regime_chart_not_recorded_stays_last_in_the_existing_order():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    chart = _regime_chart(demo)
    assert chart.sort == ["RANGING", "TRENDING", "VOLATILE", "Not recorded"]
    categories_in_data_order = [r[0] for r in chart.value["data"]]
    assert categories_in_data_order[-1] == "Not recorded"
    assert categories_in_data_order[-2] == "Not recorded"


def test_regime_chart_x_y_color_are_wired():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    chart = _regime_chart(demo)
    assert chart.x == "category"
    assert chart.y == "count"
    assert chart.color == "outcome"


def test_regime_chart_height_is_220():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    assert _regime_chart(demo).height == 220


def test_regime_chart_title_description_render_verbatim():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    visible = _visible_html(demo)
    assert "Historical outcome by entry market regime" in visible
    assert (
        "Realized win/loss counts for closed BUY decisions, grouped by "
        "the market regime recorded at entry." in visible
    )


def test_regime_disclaimer_renders_exactly_once():
    """The regime table already renders REGIME_OUTCOMES_DISCLAIMER as its
    own authoritative disclaimer -- the chart card must not repeat it."""
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    visible = _visible_html(demo)
    assert visible.count(REGIME_OUTCOMES_DISCLAIMER) == 1


def test_regime_card_title_is_distinct_from_the_outer_section_label():
    """Regression guard: the card-local chart title must not repeat the
    outer .pl-section-label (REGIME_OUTCOMES_TITLE) verbatim -- Sprint 1
    originally rendered the same string twice back to back."""
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    visible = _visible_html(demo)
    assert "Historical outcome by entry market regime" != REGIME_OUTCOMES_TITLE
    assert visible.count(REGIME_OUTCOMES_TITLE) == 1


def test_regime_outer_section_label_is_unchanged():
    """The frozen-IA outer section label must keep rendering
    REGIME_OUTCOMES_TITLE verbatim -- only the card-local title changed."""
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    section_labels = [
        block.value for block in demo.blocks.values()
        if isinstance(block, gr.HTML)
        and isinstance(getattr(block, "value", None), str)
        and 'class="pl-section-label"' in block.value
    ]
    assert any(REGIME_OUTCOMES_TITLE in value for value in section_labels)


def test_regime_chart_sits_inside_the_aara_card_treatment():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    cards = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Column) and "aara-card" in (b.elem_classes or [])
        and "pl-regime-chart-card" in (b.elem_classes or [])
    ]
    assert len(cards) == 1
    assert cards[0].visible is True


def test_regime_table_still_renders_unchanged_alongside_the_chart():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    visible = _visible_html(demo)
    for label in ("RANGING", "TRENDING", "VOLATILE", "Not recorded"):
        assert label in visible
    assert "58%" in visible


def test_regime_chart_comes_before_the_existing_table_in_render_order():
    demo = PerformanceLearningUI(screen=build_regime_outcome_preview_screen()).build()

    combined = "\n".join(_html_values(demo))
    assert combined.index(REGIME_OUTCOMES_TITLE) < combined.index('class="pl-regime-table"')


def test_calibration_and_regime_charts_use_the_restrained_win_loss_colors():
    """No stoplight red/green -- brand/guidelines/FORBIDDEN_UI_PATTERNS.md."""
    demo = PerformanceLearningUI(
        screen=replace(
            build_calibration_preview_screen(),
            regime_outcome_health=IntegrationHealth.healthy(_CAL_PROVIDER),
            regime_outcome_rows=(_rrow("RANGING", 5, 5),),
        )
    ).build()

    for chart in (_calibration_chart(demo), _regime_chart(demo)):
        assert chart.color_map == {"Win": "#0B1F3A", "Loss": "#7A2E2E"}


def test_charts_add_no_button_or_load_event_of_their_own():
    """P0-2 (Refresh): the calibration/regime charts must not introduce
    their own button or handler beyond the one shared Refresh mechanism
    every dynamic component on this screen now updates through. Updated
    from the original 'no Refresh exists at all' premise, which P0-2
    intentionally changes; the test's actual intent (the charts add
    nothing of their own) is preserved."""
    demo = PerformanceLearningUI(screen=build_calibration_preview_screen()).build()

    buttons = [b for b in demo.blocks.values() if isinstance(b, gr.Button)]
    assert len(buttons) == 1
    assert "aara-refresh-button" in (buttons[0].elem_classes or [])


# --- Sprint 4: Decision pipeline chart does not disturb calibration/regime -

def _minimal_ledger_screen():
    """One executed candidate -- just enough for screen.ledger_funnel_
    available to be True (a real HEALTHY, non-empty inspection), so the
    calibration/regime charts can be regression-tested alongside a real,
    visible pipeline chart. Full candidate-population fixtures for the
    pipeline chart's own behavior live in
    test_performance_learning_decision_ledger_filter_view.py; this is
    deliberately minimal -- only this one regression check needs it."""
    import datetime as _dt

    from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
        CandidateDecisionInspection,
        CandidateInspectionResult,
        DecisionInspectionResult,
    )
    from applications.trading_intelligence.services.candidate_decision_query_service import (
        build_ledger_funnel_summary,
    )

    decision = DecisionInspectionResult(
        decision_id="DEC-1", candidate_event_id="CAND-1",
        timestamp="2026-07-30T13:48:41+00:00", asset="AAPL",
        action="BUY", event_type="EXECUTED", final_confidence=0.7,
        model_outputs={}, risk_checks={}, intent={}, market_context={},
        data_completeness={}, sequence_number=1, hold_message=None,
        entry_gates_passed=True, gate_finding=None,
        missing_gate_detail_message=None,
    )
    candidate = CandidateInspectionResult(
        candidate_event_id="CAND-1", timestamp="2026-07-29T14:33:22+00:00",
        asset="AAPL", screening_version="screen_universe_v1",
        screening_results={}, data_available=True,
        required_models_available=True, evaluation_requested=True,
        evaluation_completed=True, sequence_number=1, decisions=(decision,),
        evaluation_status_label="Evaluation completed",
        terminal_state_message=None,
    )
    inspection = CandidateDecisionInspection(
        candidates=(candidate,), unmatched_decisions=(),
        snapshot_mtime=_dt.datetime(2026, 9, 1, 19, 0, 0, tzinfo=_dt.timezone.utc),
        data_through="2026-09-01T19:00:53+00:00",
    )
    return replace(
        build_mock_screen(),
        ledger_health=IntegrationHealth.healthy("trust_ledger_inspection"),
        ledger_inspection=inspection,
        ledger_funnel_summary=build_ledger_funnel_summary(inspection),
    )


def _pipeline_chart(demo):
    charts = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.BarPlot) and "pl-pipeline-chart" in (b.elem_classes or [])
    ]
    assert len(charts) == 1
    return charts[0]


def test_calibration_chart_still_present_and_unchanged_alongside_pipeline_chart():
    ledger = _minimal_ledger_screen()
    screen = replace(
        build_calibration_preview_screen(),
        ledger_health=ledger.ledger_health,
        ledger_inspection=ledger.ledger_inspection,
        ledger_funnel_summary=ledger.ledger_funnel_summary,
    )
    demo = PerformanceLearningUI(screen=screen).build()

    cal_chart = _calibration_chart(demo)
    assert cal_chart.visible is True
    assert cal_chart.height == 220
    assert cal_chart.color_map == {"Win": "#0B1F3A", "Loss": "#7A2E2E"}
    assert _pipeline_chart(demo).visible is True


def test_regime_chart_still_present_and_unchanged_alongside_pipeline_chart():
    ledger = _minimal_ledger_screen()
    screen = replace(
        build_regime_outcome_preview_screen(),
        ledger_health=ledger.ledger_health,
        ledger_inspection=ledger.ledger_inspection,
        ledger_funnel_summary=ledger.ledger_funnel_summary,
    )
    demo = PerformanceLearningUI(screen=screen).build()

    reg_chart = _regime_chart(demo)
    assert reg_chart.visible is True
    assert reg_chart.height == 220
    assert reg_chart.color_map == {"Win": "#0B1F3A", "Loss": "#7A2E2E"}
    assert _pipeline_chart(demo).visible is True


# --- P0-2: Refresh ----------------------------------------------------------
#
# Same shared disable -> render -> enable double-submit guard chain every
# other Trading Intelligence screen already uses (Morning Brief, Risk
# Intelligence, Portfolio Intelligence, Decision Center). _render() reuses
# every existing formatting helper verbatim over a freshly-fetched screen
# -- no new rendering logic, no fabricated fallback data.

_OUTPUT_COUNT = 19  # see PerformanceLearningUI.build()'s `outputs` list --
# NARROW P0-2 CORRECTION: 23 minus the 4 Decision Ledger Inspection
# components (ledger_freshness_output, pipeline_chart_card, pipeline_chart,
# ledger_body_output), which ADR-064 §2.12 requires stay build()-time-only.


def _counting_provider(*screens):
    """Returns a provider yielding the given screens in order (repeating
    the last), plus a mutable call-count list. Mirrors ui/tests/
    test_morning_brief_gradio_view.py's own helper of the same name."""
    calls = []
    seq = list(screens)

    def provider():
        calls.append(True)
        return seq[min(len(calls) - 1, len(seq) - 1)]

    return provider, calls


def _refresh_button(demo):
    buttons = [
        b for b in demo.blocks.values()
        if isinstance(b, gr.Button) and "aara-refresh-button" in (b.elem_classes or [])
    ]
    assert len(buttons) == 1
    return buttons[0]


def test_build_has_a_single_refresh_button_with_the_shared_class():
    demo = PerformanceLearningUI().build()

    _refresh_button(demo)  # asserts exactly one, with the shared class


def test_disable_refresh_button_returns_a_not_interactive_update():
    assert PerformanceLearningUI._disable_refresh_button() == {
        "interactive": False, "__type__": "update",
    }


def test_enable_refresh_button_returns_an_interactive_update():
    assert PerformanceLearningUI._enable_refresh_button() == {
        "interactive": True, "__type__": "update",
    }


def test_refresh_click_chain_is_disable_then_render_then_enable():
    """Same disable -> render -> enable double-submit guard chain as
    every sibling screen: proves the click().then().then() wiring in
    build(), not just that the helper methods exist in isolation."""
    ui = PerformanceLearningUI()
    demo = ui.build()

    refresh_button = _refresh_button(demo)
    refresh_button_id = next(
        bid for bid, block in demo.blocks.items() if block is refresh_button
    )
    disable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is PerformanceLearningUI._disable_refresh_button
    )
    render_dep = next(
        dep for dep in demo.config["dependencies"]
        if dep.get("trigger_after") == disable_dep["id"]
    )
    enable_dep = next(
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn is PerformanceLearningUI._enable_refresh_button
    )

    assert disable_dep["targets"] == [(refresh_button_id, "click")]
    assert refresh_button_id in disable_dep["outputs"]
    assert demo.fns[render_dep["id"]].fn == ui._render
    assert enable_dep["trigger_after"] == render_dep["id"]
    assert refresh_button_id in enable_dep["outputs"]


def test_demo_load_and_the_refresh_chain_both_call_render():
    ui = PerformanceLearningUI()
    demo = ui.build()

    render_deps = [
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn == ui._render
    ]
    assert len(render_deps) == 2  # demo.load() + the Refresh .then() step


def test_render_returns_one_update_per_dynamic_output():
    updates = PerformanceLearningUI()._render()

    assert len(updates) == _OUTPUT_COUNT
    assert all(u.get("__type__") == "update" for u in updates)


def test_render_reflects_a_fresh_screen_from_the_provider_each_call():
    """No gr.State needed: proves _render() itself re-fetches via
    self._screen_provider() on every call, rather than reusing the
    __init__-time snapshot. With a 2-screen counting provider, call 1
    (in __init__) sees the first screen, and every call from here on
    (including the first explicit _render() below) sees the second --
    both `first` and `second` must show the SAME populated value, proving
    each _render() call re-fetches rather than caching."""
    provider, calls = _counting_provider(
        build_mock_screen(),
        _calibration_screen([
            _band("0.50-0.55", 2, 2), _band("0.55-0.60", 3, 3),
            _band("0.60-0.65", 2, 3), _band("0.65-1.00", 0, 0),
        ]),
    )
    ui = PerformanceLearningUI(screen_provider=provider)

    first = ui._render()
    second = ui._render()

    assert f"15 of {CALIBRATION_MIN_OUTCOMES}" in first[1]["value"]
    assert f"15 of {CALIBRATION_MIN_OUTCOMES}" in second[1]["value"]
    assert len(calls) == 3  # 1 in __init__ + 2 explicit _render() calls


def test_rendered_at_indicator_is_present_at_build_and_refreshed_by_render():
    demo = PerformanceLearningUI().build()
    assert any(_RENDERED_AT_PREFIX in v for v in _html_values(demo))

    updates = PerformanceLearningUI()._render()
    assert _RENDERED_AT_PREFIX in updates[0]["value"]


def test_evidence_maturity_updates_on_refresh():
    provider, _ = _counting_provider(
        build_mock_screen(),  # __init__ snapshot: calibration_health is None
        _calibration_screen([
            _band("0.50-0.55", 2, 2), _band("0.55-0.60", 3, 3),
            _band("0.60-0.65", 2, 3), _band("0.65-1.00", 0, 0),
        ]),
    )
    ui = PerformanceLearningUI(screen_provider=provider)

    updates = ui._render()

    assert f"15 of {CALIBRATION_MIN_OUTCOMES}" in updates[1]["value"]
    assert "Below the established floor" in updates[1]["value"]


def test_outcome_history_updates_on_refresh():
    provider, _ = _counting_provider(
        build_mock_screen(),
        _populated_outcome_screen(loss_review_summary=None),
    )
    ui = PerformanceLearningUI(screen_provider=provider)

    updates = ui._render()

    assert updates[7]["visible"] is True
    assert any("AMZN BUY · trade-38" in row for row in updates[7]["value"])


def test_regime_chart_updates_on_refresh():
    # Two "unavailable" screens then the populated one: call 1 (__init__)
    # and call 2 (the first explicit _render() below) both see the
    # unavailable screen; call 3 (second _render()) sees the populated
    # one -- see _counting_provider's own indexing note.
    provider, _ = _counting_provider(
        build_mock_screen(), build_mock_screen(),
        build_regime_outcome_preview_screen(),
    )
    ui = PerformanceLearningUI(screen_provider=provider)

    first = ui._render()
    second = ui._render()

    assert first[9]["visible"] is False
    assert second[9]["visible"] is True
    df = second[9]["value"]
    win_rows = df[(df["category"] == "RANGING") & (df["outcome"] == "Win")]
    assert win_rows["count"].tolist() == [7]


def test_calibration_chart_updates_on_refresh():
    provider, _ = _counting_provider(
        build_mock_screen(), build_mock_screen(),  # __init__ + 1st render
        build_calibration_preview_screen(),
    )
    ui = PerformanceLearningUI(screen_provider=provider)

    first = ui._render()
    second = ui._render()

    assert first[14]["visible"] is False
    assert second[14]["visible"] is True
    df = second[14]["value"]
    win_rows = df[(df["category"] == "0.60-0.65") & (df["outcome"] == "Win")]
    assert win_rows["count"].tolist() == [9]


# --- NARROW P0-2 CORRECTION: Decision Ledger Inspection stays outside the
# --- Refresh/_render() contract (ADR-064 §2.12) ----------------------------
#
# These are regression guards, not "the Ledger updates" tests -- the whole
# point of the narrow correction is that it does NOT update on Refresh.


def test_ledger_components_are_not_among_the_refresh_outputs():
    """The four Decision Ledger Inspection components (freshness line,
    pipeline chart card, pipeline chart, ledger body) must never be
    targeted by either the Refresh chain's render step or demo.load() --
    confirms the narrow correction at the wiring level, not just by
    counting the tuple length."""
    ui = PerformanceLearningUI(screen=_minimal_ledger_screen())
    demo = ui.build()

    ledger_component_ids = {
        bid for bid, block in demo.blocks.items()
        if any(
            cls in ("pl-dli", "pl-pipeline-chart-card", "pl-pipeline-chart")
            for cls in (getattr(block, "elem_classes", None) or [])
        )
    }
    assert ledger_component_ids, "sanity: the ledger components must exist in the built demo"

    render_deps = [
        dep for dep in demo.config["dependencies"]
        if demo.fns[dep["id"]].fn == ui._render
    ]
    assert len(render_deps) == 2  # demo.load() + the Refresh .then() step
    for dep in render_deps:
        assert not (set(dep["outputs"]) & ledger_component_ids)


def test_render_return_tuple_has_no_ledger_content():
    """_render()'s 19-element tuple must never contain Decision Ledger
    Inspection markup (its candidate-list/boundary classes, or
    ledger-only strings like "Entry gates passed" / a candidate's own
    asset symbol) -- proves the tuple's CONTENTS, not just its length,
    exclude the Ledger. (Deliberately NOT checking for the bare "pl-dli"
    substring: rendered_at_output legitimately reuses the existing
    .pl-dli-freshness class's styling for the page-level render clock --
    see _format_rendered_at_html's own docstring -- so "pl-dli" alone
    would false-positive against that intentional, unrelated reuse.)"""
    ui = PerformanceLearningUI(screen_provider=_minimal_ledger_screen)

    updates = ui._render()

    assert len(updates) == 19
    for update in updates:
        value = update.get("value")
        if isinstance(value, str):
            assert "pl-dli-list" not in value
            assert "pl-dli-candidate" not in value
            assert "pl-dli-boundary" not in value
            assert "Entry gates passed" not in value
            assert "AAPL" not in value


def test_ledger_content_reflects_only_the_original_build_time_screen():
    """The Decision Ledger Inspection section is constructed once from
    `self._screen` (the __init__-time snapshot) -- a screen_provider that
    would return DIFFERENT ledger data on a later call must have no
    effect on what build() actually rendered, since build() never calls
    the provider again and _render() never touches these components."""
    initial_screen = build_mock_screen()  # ledger unavailable
    provider, calls = _counting_provider(initial_screen, _minimal_ledger_screen())
    ui = PerformanceLearningUI(screen_provider=provider)

    demo = ui.build()

    combined = "\n".join(
        b.value for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
    )
    # Only the __init__-time (unavailable) screen's ledger state is
    # present -- the second screen's real candidate ("AAPL") never
    # appears, even though the provider is capable of returning it.
    assert "AAPL" not in combined
    assert len(calls) == 1  # __init__ only -- build() adds no second call

    # Refreshing the OTHER (refreshable) sections still works and still
    # does not touch the ledger's own already-rendered content.
    ui._render()
    assert len(calls) == 2  # the explicit _render() call above
    combined_after_render = "\n".join(
        b.value for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
    )
    assert combined_after_render == combined  # unchanged: build()'s own tree


def test_ledger_freshness_still_shows_the_snapshot_bound_not_the_render_clock():
    """Product Design requirement: the Ledger's own freshness caption
    must keep showing the SNAPSHOT's mtime/data-through bound (existing,
    unchanged _ledger_freshness_html), never the page-level render clock
    the refreshable sections now show."""
    demo = PerformanceLearningUI(screen=_minimal_ledger_screen()).build()

    combined = "\n".join(
        b.value for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
    )
    assert "Ledger snapshot:" in combined
    assert "data through" in combined
    # The render-clock prefix appears (once, for rendered_at_output) but
    # never inside the ledger's own freshness caption specifically.
    ledger_freshness_line = next(
        v for v in (
            b.value for b in demo.blocks.values()
            if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
        )
        if "Ledger snapshot:" in v
    )
    assert _RENDERED_AT_PREFIX not in ledger_freshness_line
