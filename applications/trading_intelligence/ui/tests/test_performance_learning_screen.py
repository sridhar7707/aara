from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)


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


def test_frozen_ia_section_titles_are_exact():
    """These three literal strings are the frozen IA's own "Required
    information" wording (docs/products/AARA_TRADING_INTELLIGENCE_UI_
    SPECIFICATION.md Section 2) -- this test locks them in verbatim."""
    assert OUTCOME_HISTORY_TITLE == "Outcome History"
    assert ATTRIBUTION_BREAKDOWN_TITLE == "Attribution Breakdown"
    assert MODEL_CONFIDENCE_CALIBRATION_TITLE == "Model Confidence Calibration"


def test_sections_property_returns_all_three_in_frozen_ia_order():
    screen = _make_screen()

    titles = [section.title for section in screen.sections]

    assert titles == [
        OUTCOME_HISTORY_TITLE, ATTRIBUTION_BREAKDOWN_TITLE, MODEL_CONFIDENCE_CALIBRATION_TITLE,
    ]


def test_screen_is_always_empty():
    """This shell has no code path that could ever report a section as
    available -- is_empty is always True, unconditionally."""
    screen = _make_screen()

    assert screen.is_empty is True


def test_empty_state_message_is_a_fixed_honest_string():
    screen = _make_screen()

    assert screen.empty_state_message == "Performance & Learning has no wired data sources yet."


def test_each_section_carries_its_own_unavailable_message():
    screen = _make_screen(
        outcome_history=PerformanceLearningSection(
            title=OUTCOME_HISTORY_TITLE, unavailable_message="no outcome source",
        ),
    )

    assert screen.outcome_history.unavailable_message == "no outcome source"
