from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.projections.calibration_band import CalibrationBand
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    CALIBRATION_CONTENT_HEADING,
    CALIBRATION_MIN_OUTCOMES,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
    OutcomeHistoryRow,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)

_PROVIDER = "trades_db_outcomes"


def _make_screen(**overrides):
    defaults = dict(
        outcome_history=PerformanceLearningSection(
            title=OUTCOME_HISTORY_TITLE, unavailable_message="unavailable-1",
        ),
        attribution_breakdown=PerformanceLearningSection(
            title=ATTRIBUTION_BREAKDOWN_TITLE, unavailable_message="unavailable-2",
        ),
        model_confidence_calibration=PerformanceLearningSection(
            title=MODEL_CONFIDENCE_CALIBRATION_TITLE, unavailable_message="unavailable-3",
        ),
    )
    defaults.update(overrides)
    return PerformanceLearningScreen(**defaults)


def _row(**overrides):
    defaults = dict(
        decision="AMZN BUY · trade-38",
        entry_date="2026-07-16 11:50 CDT",
        status="CLOSED",
        exit_date="2026-09-02 09:33 CDT",
        holding_days="47",
        realized_pnl_usd="-27.77",
        realized_pnl_pct="-0.23%",
        exit_basis="Bot fill",
        pairing_method="WINDOW_SINGLE_BOT_EXIT",
        pairing_confidence="HIGH",
        direction="LOSS",
    )
    defaults.update(overrides)
    return OutcomeHistoryRow(**defaults)


def test_frozen_ia_section_titles_are_exact():
    assert OUTCOME_HISTORY_TITLE == "Outcome History"
    assert ATTRIBUTION_BREAKDOWN_TITLE == "Attribution Breakdown"
    assert MODEL_CONFIDENCE_CALIBRATION_TITLE == "Model Confidence Calibration"


def test_sections_property_returns_all_three_in_frozen_ia_order():
    screen = _make_screen()

    titles = [section.title for section in screen.sections]

    assert titles == [
        OUTCOME_HISTORY_TITLE, ATTRIBUTION_BREAKDOWN_TITLE, MODEL_CONFIDENCE_CALIBRATION_TITLE,
    ]


def test_section_order_is_unchanged_regardless_of_outcome_state():
    populated = _make_screen(
        outcome_rows=(_row(),),
        outcome_health=IntegrationHealth.healthy(_PROVIDER),
        summary="1 BUY decisions — 1 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
    )
    assert [s.title for s in populated.sections] == [
        OUTCOME_HISTORY_TITLE, ATTRIBUTION_BREAKDOWN_TITLE, MODEL_CONFIDENCE_CALIBRATION_TITLE,
    ]


# --- state 1: no provider / non-HEALTHY -> unavailable ---------------------

def test_no_provider_screen_is_unavailable_and_empty():
    """The standalone / no-provider default: outcome_health is None."""
    screen = _make_screen()
    assert screen.outcome_health is None
    assert screen.outcome_history_available is False
    assert screen.is_empty is True


def test_non_healthy_read_is_unavailable_and_empty():
    screen = _make_screen(
        outcome_health=IntegrationHealth.unavailable(_PROVIDER, detail="trades snapshot is not present"),
    )
    assert screen.outcome_history_available is False
    assert screen.is_empty is True


# --- state 2: HEALTHY + zero decisions -> honest empty --------------------

def test_healthy_but_no_decisions_is_available_but_empty():
    screen = _make_screen(
        outcome_health=IntegrationHealth.healthy(_PROVIDER),
        outcome_rows=(),
        summary="0 BUY decisions — 0 CLOSED · 0 PARTIAL · 0 OPEN · 0 AMBIGUOUS.",
    )
    assert screen.outcome_history_available is True
    assert screen.outcome_history_is_empty is True
    assert screen.is_empty is True
    assert screen.outcome_history_empty_message == (
        "No BUY decisions are present in the current trades snapshot."
    )


# --- state 3: HEALTHY + decisions -> populated ---------------------------

def test_healthy_with_decisions_is_available_and_not_empty():
    screen = _make_screen(
        outcome_rows=(_row(), _row(decision="SLB BUY · trade-45", status="OPEN")),
        outcome_health=IntegrationHealth.healthy(_PROVIDER),
        summary="2 BUY decisions — 1 CLOSED · 0 PARTIAL · 1 OPEN · 0 AMBIGUOUS.",
    )
    assert screen.outcome_history_available is True
    assert screen.outcome_history_is_empty is False
    assert screen.is_empty is False
    assert len(screen.outcome_rows) == 2


def test_attribution_and_calibration_messages_are_preserved_when_populated():
    screen = _make_screen(
        outcome_rows=(_row(),),
        outcome_health=IntegrationHealth.healthy(_PROVIDER),
    )
    assert screen.attribution_breakdown.unavailable_message == "unavailable-2"
    assert screen.model_confidence_calibration.unavailable_message == "unavailable-3"


def test_empty_state_message_is_a_fixed_honest_string():
    assert _make_screen().empty_state_message == (
        "Performance & Learning has no wired data sources yet."
    )


def test_each_section_carries_its_own_unavailable_message():
    screen = _make_screen(
        outcome_history=PerformanceLearningSection(
            title=OUTCOME_HISTORY_TITLE, unavailable_message="no outcome source",
        ),
    )
    assert screen.outcome_history.unavailable_message == "no outcome source"


_HEALTHY = IntegrationHealth.healthy(_PROVIDER)


def _bands(*, first=(0, 0), second=(0, 0), third=(0, 0), fourth=(0, 0)):
    pairs = (
        ("0.50-0.55", first),
        ("0.55-0.60", second),
        ("0.60-0.65", third),
        ("0.65-1.00", fourth),
    )
    return tuple(
        CalibrationBand(label=label, wins=wins, losses=losses)
        for label, (wins, losses) in pairs
    )


def _fill_to_min(*, wins_share=1):
    """Bands whose total n is exactly CALIBRATION_MIN_OUTCOMES."""
    losses = CALIBRATION_MIN_OUTCOMES - wins_share
    return _bands(third=(wins_share, losses))


# --- Model Confidence Calibration state ----------------------------------


def test_calibration_content_heading_is_neutral_historical_wording():
    assert CALIBRATION_CONTENT_HEADING == "Historical outcome by ensemble score"
    lowered = CALIBRATION_CONTENT_HEADING.lower()
    for forbidden in ("predictive accuracy", "probability calibration",
                      "guaranteed", "certainty"):
        assert forbidden not in lowered


def test_no_provider_calibration_is_unavailable():
    screen = _make_screen()
    assert screen.calibration_health is None
    assert screen.calibration_available is False
    assert screen.calibration_total_outcomes == 0


def test_non_healthy_read_calibration_is_unavailable():
    screen = _make_screen(
        calibration_health=IntegrationHealth.unavailable(_PROVIDER, detail="x"),
        calibration_bands=_bands(),
    )
    assert screen.calibration_available is False


def test_healthy_but_zero_qualifying_outcomes_is_available_and_empty():
    screen = _make_screen(calibration_health=_HEALTHY, calibration_bands=_bands())
    assert screen.calibration_available is True
    assert screen.calibration_is_empty is True
    assert screen.calibration_has_enough_data is False
    assert "no closed buy" in screen.calibration_empty_message.lower()


def test_healthy_with_few_outcomes_is_available_but_below_the_min():
    screen = _make_screen(
        calibration_health=_HEALTHY,
        calibration_bands=_bands(third=(2, 1)),
    )
    assert screen.calibration_available is True
    assert screen.calibration_is_empty is False
    assert screen.calibration_total_outcomes == 3
    assert screen.calibration_has_enough_data is False
    message = screen.calibration_small_n_message
    assert "3" in message
    assert str(CALIBRATION_MIN_OUTCOMES) in message


def test_small_n_message_is_singular_for_one_outcome():
    screen = _make_screen(
        calibration_health=_HEALTHY, calibration_bands=_bands(first=(1, 0)),
    )
    assert "1 closed BUY outcome " in screen.calibration_small_n_message
    assert "outcomes" not in screen.calibration_small_n_message


def test_at_the_minimum_the_breakdown_is_shown():
    screen = _make_screen(
        calibration_health=_HEALTHY, calibration_bands=_fill_to_min(wins_share=10),
    )
    assert screen.calibration_total_outcomes == CALIBRATION_MIN_OUTCOMES
    assert screen.calibration_has_enough_data is True


def test_calibration_total_is_the_sum_of_band_n_without_cross_band_mixing():
    screen = _make_screen(
        calibration_health=_HEALTHY,
        calibration_bands=_bands(first=(3, 1), second=(0, 0), third=(4, 2), fourth=(1, 0)),
    )
    assert screen.calibration_total_outcomes == 3 + 1 + 4 + 2 + 1


def test_calibration_state_does_not_change_outcome_history_flags():
    screen = _make_screen(
        outcome_health=_HEALTHY,
        outcome_rows=(_row(),),
        calibration_health=_HEALTHY,
        calibration_bands=_bands(third=(5, 5)),
    )
    assert screen.outcome_history_available is True
    assert screen.is_empty is False


def test_outcome_history_populated_but_calibration_unavailable_is_independent():
    screen = _make_screen(
        outcome_health=_HEALTHY,
        outcome_rows=(_row(),),
    )
    assert screen.outcome_history_available is True
    assert screen.calibration_available is False


def test_outcome_history_row_blank_fields_stay_blank():
    """OPEN / PARTIAL / AMBIGUOUS rows carry empty strings for the exit and
    direction columns -- the screen layer never substitutes a placeholder."""
    row = OutcomeHistoryRow(
        decision="SLB BUY · trade-45", entry_date="2026-09-02 09:39 CDT", status="OPEN",
        exit_date="", holding_days="", realized_pnl_usd="", realized_pnl_pct="",
        exit_basis="", pairing_method="NONE_OPEN", pairing_confidence="NONE", direction="",
    )
    assert row.exit_date == ""
    assert row.realized_pnl_usd == ""
    assert row.direction == ""
