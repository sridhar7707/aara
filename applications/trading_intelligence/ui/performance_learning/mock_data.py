"""Deterministic data for the Performance & Learning screen shell.

No sentinel_engine/bot/dashboard import. `build_mock_screen()` -- the
production shell path and the sole data source for this screen when no
composition root supplies one (same role ui/morning_brief/mock_data.py and
ui/settings/mock_data.py play for their own screens) -- builds a fixed,
honest all-unavailable PerformanceLearningScreen. Unlike
ui/portfolio_intelligence/mock_data.py's and
ui/risk_intelligence/mock_data.py's mock data (hand-picked but fabricated
figures), no field on that screen is a number standing in for a real
outcome, attribution result, or calibration statistic -- every field is a
literal explanation of why that area has no source yet.

Outcome History's message additionally states the spec's own explicit
caveat -- outcomes, once wired, would be BUY-scoped only and would never
cover every decision -- so a future reader of this message never mistakes
today's total absence of data for a claim that all decisions get one.

`build_mock_screen()` -- the production shell path -- stays entirely
all-unavailable; nothing below it is a fabricated figure. The separate,
opt-in `build_calibration_preview_screen()` and
`build_regime_outcome_preview_screen()` builders DO carry deterministic
illustrative counts, used only by render tests / a standalone preview of
the Sprint 4 Item #1 "Historical outcome by ensemble score" table and the
Item #4 "Realized outcomes by entry market regime" table. Neither is
wired into `bootstrap.py`, so production behavior is unchanged.
"""
from dataclasses import replace

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.projections.calibration_band import CalibrationBand
from applications.trading_intelligence.projections.regime_outcome_row import (
    REGIME_NOT_RECORDED_LABEL,
    RegimeOutcomeRow,
)
from applications.trading_intelligence.services.decision_calibration_query_service import (
    BAND_LABELS,
)
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


# Deterministic illustrative band counts for the Sprint 4 #1 calibration
# render path. Two-plus populated bands (wins and losses both present),
# one deliberately empty band, and a total of exactly CALIBRATION_MIN_
# OUTCOMES so the full per-band table renders rather than the small-N
# notice. Order matches BAND_LABELS. Not real account data -- render
# fixtures only, never wired into bootstrap.py.
_CALIBRATION_PREVIEW_COUNTS = {
    "0.50-0.55": (3, 5),
    "0.55-0.60": (0, 0),
    "0.60-0.65": (9, 6),
    "0.65-1.00": (6, 1),
}
_CALIBRATION_PREVIEW_PROVIDER = "mock_calibration_preview"


def build_calibration_preview_screen() -> PerformanceLearningScreen:
    """`build_mock_screen()` plus a HEALTHY calibration read carrying the
    deterministic illustrative bands above. Outcome History and Attribution
    stay untouched (still unavailable) -- this builder illustrates only the
    calibration table's populated state and is used solely by render tests
    and a standalone preview."""
    bands = tuple(
        CalibrationBand(
            label=label,
            wins=_CALIBRATION_PREVIEW_COUNTS[label][0],
            losses=_CALIBRATION_PREVIEW_COUNTS[label][1],
        )
        for label in BAND_LABELS
    )
    return replace(
        build_mock_screen(),
        calibration_health=IntegrationHealth.healthy(_CALIBRATION_PREVIEW_PROVIDER),
        calibration_bands=bands,
    )


# Deterministic illustrative regime rows for the Sprint 4 Item #4 render
# path: three real regimes (verbatim strings, wins and losses both present)
# plus the explicit "Not recorded" bucket last. Not real account data --
# render fixtures only, never wired into bootstrap.py.
_REGIME_PREVIEW_ROWS = (
    ("RANGING", 7, 5),
    ("TRENDING", 9, 3),
    ("VOLATILE", 2, 6),
    (REGIME_NOT_RECORDED_LABEL, 1, 2),
)
_REGIME_PREVIEW_PROVIDER = "mock_regime_outcome_preview"


def build_regime_outcome_preview_screen() -> PerformanceLearningScreen:
    """`build_mock_screen()` plus a HEALTHY outcome read carrying the
    deterministic illustrative regime rows above. Outcome History,
    Attribution, and the calibration section stay untouched (still
    unavailable) -- this builder illustrates only the regime table's
    populated state and is used solely by render tests and a standalone
    preview."""
    rows = tuple(
        RegimeOutcomeRow(regime=label, wins=wins, losses=losses)
        for label, wins, losses in _REGIME_PREVIEW_ROWS
    )
    return replace(
        build_mock_screen(),
        regime_outcome_health=IntegrationHealth.healthy(_REGIME_PREVIEW_PROVIDER),
        regime_outcome_rows=rows,
    )
