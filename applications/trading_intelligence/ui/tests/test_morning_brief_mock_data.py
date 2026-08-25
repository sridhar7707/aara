from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.ui.morning_brief.screen import (
    CANDIDATE_SCREENING_SUMMARY_TITLE,
    MARKET_MOOD_REGIME_TITLE,
    OVERNIGHT_HOLDINGS_NEWS_TITLE,
    PORTFOLIO_SNAPSHOT_TITLE,
)

# Terms that would indicate Candidate Screening Summary (or any other
# section) had been silently backed by decision-activity data instead of
# an honest unavailable message -- forbidden per the frozen IA semantic
# rule (Candidate Screening Summary must never be represented by Recent
# Decision Activity, DecisionProjection, or MorningBriefQuery output).
_FORBIDDEN_SUBSTITUTION_TERMS = (
    "Recent Decision Activity",
    "DecisionProjection",
    "MorningBriefQuery",
    "decision_id",
    "trade history",
    "recommendation history",
)


def test_build_mock_screen_returns_the_all_unavailable_screen():
    screen = build_mock_screen()

    assert screen.is_empty is True


def test_build_mock_screen_has_all_four_frozen_sections_with_correct_titles():
    screen = build_mock_screen()

    assert screen.portfolio_snapshot.title == PORTFOLIO_SNAPSHOT_TITLE
    assert screen.market_mood_regime.title == MARKET_MOOD_REGIME_TITLE
    assert screen.candidate_screening_summary.title == CANDIDATE_SCREENING_SUMMARY_TITLE
    assert screen.overnight_holdings_news.title == OVERNIGHT_HOLDINGS_NEWS_TITLE


def test_build_mock_screen_gives_every_section_a_non_empty_unavailable_message():
    screen = build_mock_screen()

    for section in screen.sections:
        assert isinstance(section.unavailable_message, str)
        assert section.unavailable_message.strip() != ""


def test_build_mock_screen_contains_no_fabricated_numeric_looking_data():
    """No dollar amounts, percentages, or other numeric-looking figures --
    unlike ui/portfolio_intelligence/mock_data.py and
    ui/risk_intelligence/mock_data.py, which deliberately use hand-picked
    illustrative numbers for their own, differently-scoped gaps, this
    screen's content rule forbids fabricated or illustrative
    production-looking data entirely."""
    screen = build_mock_screen()

    for section in screen.sections:
        assert "$" not in section.unavailable_message
        assert "%" not in section.unavailable_message


def test_build_mock_screen_never_substitutes_decision_activity_for_candidate_screening():
    screen = build_mock_screen()

    combined_text = " ".join(
        f"{section.title} {section.unavailable_message}" for section in screen.sections
    )
    for forbidden_term in _FORBIDDEN_SUBSTITUTION_TERMS:
        assert forbidden_term not in combined_text
