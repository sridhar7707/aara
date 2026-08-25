"""Deterministic all-unavailable data for the Performance & Learning
screen shell.

No sentinel_engine/bot/dashboard import. No outcome/attribution/
calibration contract import or reference of any kind: per
docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2,
Performance & Learning names only a future, unwired Sentinel Engine input
(`DECISION_OUTCOME_RECORDED`), and no adapter for it is wired in this
application. This module -- the sole data source for this screen, same
role ui/morning_brief/mock_data.py and ui/settings/mock_data.py play for
their own screens -- builds a fixed, honest all-unavailable
PerformanceLearningScreen rather than illustrative figures. Unlike
ui/portfolio_intelligence/mock_data.py's and
ui/risk_intelligence/mock_data.py's mock data (hand-picked but fabricated
figures), nothing here is a number standing in for a real outcome,
attribution result, or calibration statistic -- every field is a literal
explanation of why that area has no source yet.

Outcome History's message additionally states the spec's own explicit
caveat -- outcomes, once wired, would be BUY-scoped only and would never
cover every decision -- so a future reader of this message never mistakes
today's total absence of data for a claim that all decisions get one.
"""
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)

_OUTCOME_HISTORY = PerformanceLearningSection(
    title=OUTCOME_HISTORY_TITLE,
    unavailable_message=(
        "No Sentinel-side outcome contract is wired yet -- this section "
        "has no source. Outcomes, once wired, would cover BUY decisions "
        "only, never every decision."
    ),
)

_ATTRIBUTION_BREAKDOWN = PerformanceLearningSection(
    title=ATTRIBUTION_BREAKDOWN_TITLE,
    unavailable_message=(
        "No Sentinel-side attribution contract is wired yet -- this "
        "section has no source."
    ),
)

_MODEL_CONFIDENCE_CALIBRATION = PerformanceLearningSection(
    title=MODEL_CONFIDENCE_CALIBRATION_TITLE,
    unavailable_message=(
        "No Sentinel-side model-calibration contract is wired yet -- "
        "this section has no source."
    ),
)


def build_mock_screen() -> PerformanceLearningScreen:
    """Named to match ui/morning_brief/mock_data.py's, ui/settings/
    mock_data.py's, ui/portfolio_intelligence/mock_data.py's, and
    ui/risk_intelligence/mock_data.py's build_mock_screen() so
    gradio_view.py's default-construction pattern stays identical across
    all six screens -- "mock" here means "this package's own fixed local
    state," not fabricated performance figures (see module docstring
    above)."""
    return PerformanceLearningScreen(
        outcome_history=_OUTCOME_HISTORY,
        attribution_breakdown=_ATTRIBUTION_BREAKDOWN,
        model_confidence_calibration=_MODEL_CONFIDENCE_CALIBRATION,
    )
