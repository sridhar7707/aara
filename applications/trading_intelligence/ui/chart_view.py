"""Shared, purely-presentational Gradio chart helpers for AARA Trading
Intelligence screens.

Sibling of ui/design_system.py and ui/integration_health_view.py: reused BY
VALUE (plain function calls over generic inputs), never by importing a
screen's own dataclass. Takes only primitive types -- (str, int, int)
tuples, plain strings -- never a screen-specific type like CalibrationBand
or RegimeOutcomeRow. No data source, no service, no business/governance
logic, and no visibility/gating decision: every threshold and every
availability check stays in the calling screen's own screen.py/
gradio_view.py, exactly as the existing render_unavailable() shared helper
(ui/integration_health_view.py) already establishes for the "unavailable
state" half of a chart's rendering -- this module is the "available state"
half's counterpart, kept just as free of screen-specific knowledge.

Introduced for Performance & Learning's Sprint 1 win/loss-by-category bar
charts (Model Confidence Calibration, Realized outcomes by entry regime).
Both need the identical "one category, two outcomes (Win/Loss), a count"
long-form shape gr.BarPlot's `color=` grouping expects, so the transform
and the title/description/disclaimer markup are shared rather than
duplicated twice in the same file -- but no abstraction beyond what these
two call sites actually need (no chart-type registry, no generic
"visualization config" object, no theming engine).
"""
import html
from typing import Dict, Iterable, Tuple

import pandas as pd

# Reuses the existing brand tokens verbatim (ui/design_system.py's
# --aara-navy and --aara-negative-fg) rather than a new red/green pair --
# brand/guidelines/FORBIDDEN_UI_PATTERNS.md forbids stoplight colours, and
# --aara-negative-fg is already the product's one restrained, desaturated
# "loss" cue used everywhere else a negative figure needs a colour. A
# gr.BarPlot color_map takes literal colour values (the chart renders its
# own SVG, not app DOM CSS), so these are the same hex literals design_
# system.py declares, not a CSS var() reference.
WIN_LOSS_COLOR_MAP: Dict[str, str] = {"Win": "#0B1F3A", "Loss": "#7A2E2E"}


def win_loss_long_dataframe(rows: Iterable[Tuple[str, int, int]]) -> pd.DataFrame:
    """Transform (category, wins, losses) tuples into the long-form shape a
    grouped/coloured gr.BarPlot needs: two rows per category, one per
    outcome. Input order is preserved verbatim in the output -- no sorting,
    no dedup, no re-grouping -- so the caller's own existing order (e.g.
    calibration's fixed band order, or regime's alpha-then-"Not recorded"-
    last order) is the only order this ever produces. A category with zero
    wins and zero losses still yields two zero-count rows, never dropped."""
    categories = []
    outcomes = []
    counts = []
    for category, wins, losses in rows:
        categories.append(category)
        outcomes.append("Win")
        counts.append(wins)
        categories.append(category)
        outcomes.append("Loss")
        counts.append(losses)
    return pd.DataFrame({"category": categories, "outcome": outcomes, "count": counts})


def chart_header_html(title: str, description: str) -> str:
    """Chart title + one-sentence description, rendered ABOVE the chart
    (per the AARA chart envelope: title -> description -> chart -> existing
    table -> existing disclaimer). Uses the shared `.aara-chart-title` /
    `.aara-chart-description` classes (ui/design_system.py) -- styled only
    when the composed app's DESIGN_SYSTEM_CSS is present, matching every
    other `.aara-*` primitive's existing standalone-vs-composed tradeoff.
    Every interpolated value is HTML-escaped."""
    return (
        f'<div class="aara-chart-title">{html.escape(title)}</div>'
        f'<div class="aara-chart-description">{html.escape(description)}</div>'
    )


def chart_disclaimer_html(text: str) -> str:
    """Optional contextual footer for a chart, using the shared
    `.aara-chart-disclaimer` class. HTML-escaped."""
    return f'<div class="aara-chart-disclaimer">{html.escape(text)}</div>'
