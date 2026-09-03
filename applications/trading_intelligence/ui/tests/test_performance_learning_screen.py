from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
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
