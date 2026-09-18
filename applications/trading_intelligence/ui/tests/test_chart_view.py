"""Tests for ui/chart_view.py -- the shared, purely-presentational chart
helpers introduced for Performance & Learning's Sprint 1 win/loss-by-
category bar charts.

Pure functions only: no Gradio component construction here (that is
exercised by test_performance_learning_gradio_view.py), no data source, no
screen-specific dataclass import (CalibrationBand / RegimeOutcomeRow stay
out of chart_view.py on purpose -- see its module docstring).
"""
import pandas as pd

from applications.trading_intelligence.ui.chart_view import (
    WIN_LOSS_COLOR_MAP,
    chart_disclaimer_html,
    chart_header_html,
    win_loss_long_dataframe,
)


# --- win_loss_long_dataframe -------------------------------------------


def test_win_loss_long_dataframe_produces_two_rows_per_category():
    df = win_loss_long_dataframe([("0.60-0.65", 9, 6)])

    assert list(df.columns) == ["category", "outcome", "count"]
    assert len(df) == 2
    assert df.iloc[0].to_dict() == {"category": "0.60-0.65", "outcome": "Win", "count": 9}
    assert df.iloc[1].to_dict() == {"category": "0.60-0.65", "outcome": "Loss", "count": 6}


def test_win_loss_long_dataframe_preserves_input_order_verbatim():
    """No sorting, no re-grouping -- callers (calibration's fixed band
    order, regime's alpha-then-"Not recorded"-last order) own ordering."""
    rows = [("VOLATILE", 2, 6), ("RANGING", 7, 5), ("Not recorded", 1, 2)]

    df = win_loss_long_dataframe(rows)

    assert list(df["category"]) == [
        "VOLATILE", "VOLATILE", "RANGING", "RANGING", "Not recorded", "Not recorded",
    ]


def test_win_loss_long_dataframe_of_empty_input_is_empty():
    df = win_loss_long_dataframe([])

    assert list(df.columns) == ["category", "outcome", "count"]
    assert len(df) == 0


def test_win_loss_long_dataframe_handles_a_zero_count_band_honestly():
    """A band/regime with zero wins and zero losses still produces two rows
    (count=0 each) -- never dropped, never fabricated."""
    df = win_loss_long_dataframe([("0.55-0.60", 0, 0)])

    assert list(df["count"]) == [0, 0]


def test_win_loss_long_dataframe_returns_a_real_dataframe():
    assert isinstance(win_loss_long_dataframe([("x", 1, 1)]), pd.DataFrame)


# --- chart_header_html ---------------------------------------------------


def test_chart_header_html_contains_title_and_description():
    html = chart_header_html("Historical outcome by ensemble score", "One sentence.")

    assert '<div class="aara-chart-title">Historical outcome by ensemble score</div>' in html
    assert '<div class="aara-chart-description">One sentence.</div>' in html


def test_chart_header_html_escapes_interpolated_values():
    html = chart_header_html("<script>", "<script>desc</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_chart_header_html_title_renders_before_description():
    html = chart_header_html("Title", "Description")

    assert html.index("aara-chart-title") < html.index("aara-chart-description")


# --- chart_disclaimer_html ------------------------------------------------


def test_chart_disclaimer_html_wraps_the_text():
    html = chart_disclaimer_html("A historical tally only.")

    assert html == '<div class="aara-chart-disclaimer">A historical tally only.</div>'


def test_chart_disclaimer_html_escapes_interpolated_values():
    html = chart_disclaimer_html("<script>bad</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# --- WIN_LOSS_COLOR_MAP ----------------------------------------------------


def test_win_loss_color_map_has_exactly_win_and_loss_keys():
    assert set(WIN_LOSS_COLOR_MAP.keys()) == {"Win", "Loss"}


def test_win_loss_color_map_uses_restrained_brand_tokens_not_stoplight_colors():
    """No bright-red/bright-green -- brand/guidelines/FORBIDDEN_UI_PATTERNS.md.
    Win reuses the brand navy token (#0B1F3A); Loss reuses the existing
    restrained/desaturated --aara-negative-fg token (#7A2E2E), the same
    literal already used product-wide for a loss cue, not a new colour."""
    assert WIN_LOSS_COLOR_MAP["Win"] == "#0B1F3A"
    assert WIN_LOSS_COLOR_MAP["Loss"] == "#7A2E2E"
    for value in WIN_LOSS_COLOR_MAP.values():
        assert value.lower() not in ("#ff0000", "#00ff00", "#00c853", "red", "green")
