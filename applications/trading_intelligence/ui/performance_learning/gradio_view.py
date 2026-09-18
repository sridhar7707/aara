"""Gradio shell for Performance & Learning.

Self-contained: no import of any sibling screen package, no
sentinel_engine/bot/dashboard import, no service call, no database or
HuggingFace access. Renders whatever `PerformanceLearningScreen` it is
given. The production screen is built by bootstrap.py's
`_build_performance_learning_screen`, which maps the verified Wave 2A
decision-outcome lineage (`DecisionOutcomeQueryService`) into this
package's own `OutcomeHistoryRow` shape and attaches the Wave 3C
Decision Ledger Inspection result -- this view never touches Wave 2A/3A/3B
sources directly and never re-derives anything.

Wave 3C (ADR-064) adds one additive section, **Decision Ledger
Inspection**, rendered after the two still-unavailable frozen IA areas.
It shows the already-materialized Wave 3B `CandidateDecisionInspection`
(candidate -> evaluation state -> recorded decision(s) -> model evidence
-> recorded gate/exit fact -> decision-time context) and an explicit
end-of-decision-time-evidence boundary. It renders zero outcome / P&L /
trade-linked data, computes nothing, and every ledger-sourced free-text
string is HTML-escaped.

Three states for the Outcome History area, mirroring
ui/risk_intelligence/gradio_view.py's stable-tree pattern (every element
created once, visibility toggled):

  1. non-HEALTHY read  -> an unavailable message. `outcome_health is None`
     (standalone / no-provider build) renders this section's own fixed
     message verbatim; a real non-HEALTHY `IntegrationHealth` renders the
     shared ADR-061 "Data unavailable -- <reason>" phrase.
  2. HEALTHY, zero BUY decisions -> an honest empty-state message.
  3. HEALTHY, decisions present -> a factual summary line + a
     `gr.Dataframe` of one row per `DecisionOutcome`.

Attribution Breakdown and Model Confidence Calibration remain unavailable
in every state -- Wave 2A produces no attribution or calibration data and
none is fabricated here.

No Refresh button and no `demo.load()` in this slice: the screen is
rendered once at build time from the screen the provider returns.

Renders no "Illustrative Data" banner -- every value shown is real,
sourced verbatim from Wave 2A; nothing is illustrative.
"""
import html
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr
import pandas as pd

from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    CandidateDecisionInspection,
    CandidateInspectionResult,
    DecisionInspectionResult,
    LedgerFunnelSummary,
    candidate_filter_state,
)
from applications.trading_intelligence.ui.performance_learning.decision_ledger_funnel_view import (
    build_filter_controls_html,
    build_funnel_panel_html,
    prioritized_candidates,
)
from applications.trading_intelligence.ui.chart_view import (
    WIN_LOSS_COLOR_MAP,
    chart_header_html,
    win_loss_long_dataframe,
)
from applications.trading_intelligence.ui.integration_health_view import (
    CSS as _INTEGRATION_HEALTH_CSS,
    render_unavailable,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    CALIBRATION_CONTENT_HEADING,
    CALIBRATION_DISCLAIMER,
    DECISION_LEDGER_INSPECTION_TITLE,
    EVIDENCE_MATURITY_DISCLAIMER,
    LOSS_REVIEW_DISCLAIMER,
    REGIME_OUTCOMES_DISCLAIMER,
    REGIME_OUTCOMES_TITLE,
    OutcomeHistoryRow,
    PerformanceLearningScreen,
    PerformanceLearningSection,
)
from applications.trading_intelligence.ui.performance_learning.theme import CSS
from applications.trading_intelligence.ui.shell import SHELL_IDENTITY_HTML, build_shell_nav_html

# gr.Dataframe's row-height-budget kwarg is `height` on gradio 4.x and
# `max_height` on gradio 5.x -- same compat shim the other table screens
# keep as a local literal (no cross-package import).
_gr_major = int(gr.__version__.split(".")[0])
_DATAFRAME_HEIGHT_KWARG = "height" if _gr_major < 5 else "max_height"

# Sprint 1 (visualization convention): both new charts are supporting/
# secondary visualizations -- neither is this screen's single hero
# (there isn't one; the calibration and regime charts are two co-equal
# peers, each summarizing a table that stays the detail record right
# below it) -- so both use the "secondary chart" height (220px), not the
# 320px "hero chart" height ui/morning_brief/gradio_view.py's promoted
# Portfolio Value Trend chart uses.
_CHART_HEIGHT = 220

_CALIBRATION_CHART_DESCRIPTION = (
    "Realized win/loss counts for closed BUY decisions, grouped by entry "
    "ensemble score."
)
_REGIME_CHART_DESCRIPTION = (
    "Realized win/loss counts for closed BUY decisions, grouped by the "
    "market regime recorded at entry."
)
# Content-specific card title -- deliberately distinct from the outer
# REGIME_OUTCOMES_TITLE section label (.pl-section-label) rendered just
# above the card, so the two do not repeat the same string back to back.
_REGIME_CHART_TITLE = "Historical outcome by entry market regime"

_OUTCOME_HEADERS = [
    "Decision", "Entry date", "Status", "Exit date", "Holding days",
    "Realized P&L $", "Realized P&L %", "Exit basis", "Pairing method",
    "Pairing confidence", "Direction",
    # Decision Quality Cross-Linking: a clean, standalone reference back to
    # this outcome's originating Decision Center decision -- the SAME
    # "Decision ID" column header Decision Center's own list table uses
    # (ui/decision_center/gradio_view.py's _LIST_HEADERS), so the identity
    # is immediately recognizable across both screens. True deep-link
    # navigation to a specific decision is not supported by this product's
    # Gradio architecture (see gradio_view.py's own module docstring on the
    # shared shell nav -- it switches the outer tab, it does not target a
    # row within a tab), so this is a plain, honest text reference, not a
    # clickable link.
    "Decision ID",
]

# Impeccable critique finding #5: only the two Realized P&L columns need
# to render a negative value's colored span (see _pnl_cell above), so
# only those two columns use gr.Dataframe's "markdown" datatype -- every
# other column stays "str" (unchanged; still plain, HTML-escaped-by-
# Gradio text) exactly as before this task. Positional, matching
# _OUTCOME_HEADERS'/_outcome_row_cells' own fixed column order.
_OUTCOME_DATATYPES = [
    "markdown" if header in ("Realized P&L $", "Realized P&L %") else "str"
    for header in _OUTCOME_HEADERS
]

_PAGE_HEADER_HTML = (
    '<div class="pl-page-header">'
    '<h2 class="aara-page-title">Performance & Learning</h2>'
    '<div class="pl-subtitle">Outcome history, attribution, and model confidence calibration</div>'
    "</div>"
)

# Prominent Sample-Size Banner: reuses the SAME calibration_health /
# calibration_total_outcomes / CALIBRATION_MIN_OUTCOMES / calibration_has_
# enough_data the Model Confidence Calibration section below already
# gates on -- no new read, no new count. `calibration_health is None`
# (standalone / no-provider build) renders this fixed fallback verbatim,
# matching _format_calibration_unavailable_html's own two-branch rule; a
# real non-HEALTHY IntegrationHealth is routed through the shared
# render_unavailable() so the specific reason is named.
_EVIDENCE_MATURITY_UNAVAILABLE_MESSAGE = (
    "Evidence maturity is not available -- the outcome data source could not "
    "be read in this environment."
)


# Impeccable critique finding #5: Realized P&L $ / % are the two Outcome
# History columns holding a signed P&L figure. bootstrap.py's
# _outcome_history_row already formats them with Python's own f"{x:,.2f}"
# / f"{x:.2%}" -- a negative value's string always starts with "-" (never
# "+" for positive, per that formatting), and "" means "not applicable to
# this outcome's state" (OPEN/PENDING), never a fabricated zero. Detecting
# "negative" from that already-produced string, rather than re-deriving
# it from a raw float here, keeps this a presentation-only change: no new
# read, no recomputation, no touch to bootstrap.py's own P&L figures.
def _pnl_cell(value: str) -> str:
    """Wrap a negative Realized P&L $/% value in the shared
    .pl-negative-value span (see theme.py) -- positive values and the
    empty "not applicable" string render unchanged. The minus sign in the
    text is the primary signal either way; this is reinforcement only."""
    if not value.startswith("-"):
        return value
    return f'<span class="pl-negative-value">{html.escape(value)}</span>'


def _outcome_row_cells(row: OutcomeHistoryRow) -> List[str]:
    return [
        row.decision, row.entry_date, row.status, row.exit_date, row.holding_days,
        _pnl_cell(row.realized_pnl_usd), _pnl_cell(row.realized_pnl_pct), row.exit_basis,
        row.pairing_method, row.pairing_confidence, row.direction,
        row.decision_reference,
    ]


# Sprint 4: Decision pipeline chart -- an overview layer above the existing
# Decision Ledger Inspection funnel text panel, answering "where do
# candidates get filtered out before becoming a decision?". This is a
# decision-pipeline visualization, not a performance/outcome chart, so it
# does not reuse WIN_LOSS_COLOR_MAP or win_loss_long_dataframe (both scoped
# to the win/loss-by-category shape calibration/regime use). Single series
# -> the existing brand navy literal (#0B1F3A), same one WIN_LOSS_COLOR_MAP's
# own "Win" entry and ui/portfolio_intelligence/gradio_view.py's Allocation
# chart already reuse -- not a new palette entry.
_PIPELINE_CHART_TITLE = "Decision pipeline"
# Deliberately NOT "volume" -- the existing
# test_executed_marker_does_not_enumerate_synthetic_gates guard (test_
# performance_learning_decision_ledger_view.py) scans this whole panel for
# the literal word "volume" (a real recorded gate name) to prove no
# synthetic per-gate list is ever fabricated; "volume" in a chart
# description would be a false positive against that unrelated, real
# safety guard, so "counts" is used instead of "volume" here.
_PIPELINE_CHART_DESCRIPTION = "Candidate counts at each stage of the decision lifecycle."
# Authoritative stage order: the SAME narrative sequence build_funnel_panel_
# html (decision_ledger_funnel_view.py) already presents -- total candidates
# -> evaluations completed -> decisions recorded -> the executed/held/
# rejected decision-event breakdown. Never sorted alphabetically or by
# count.
_PIPELINE_STAGE_LABELS = ("Candidates", "Evaluated", "Decisions", "Executed", "Held", "Rejected")
_PIPELINE_SERIES_LABEL = "Stage"
_PIPELINE_COLOR_MAP = {_PIPELINE_SERIES_LABEL: "#0B1F3A"}


def _pipeline_chart_dataframe(summary: Optional[LedgerFunnelSummary]) -> pd.DataFrame:
    """The Decision pipeline chart's dataframe -- six literal counts taken
    verbatim from the SAME LedgerFunnelSummary the funnel text panel above
    already reads (never a second read, never a recomputed figure), in the
    authoritative _PIPELINE_STAGE_LABELS order. A stage legitimately at
    zero (e.g. reject_count == 0) is still included at 0 -- never omitted.
    `summary` is None whenever the caller has already determined the
    funnel is unavailable (screen.ledger_funnel_available is False,
    including the "HEALTHY but zero candidates" case) -- an empty,
    schema-correct DataFrame is returned then, never six fabricated
    zero-count rows implying real data exists when it does not."""
    if summary is None:
        return pd.DataFrame({"stage": [], "count": [], "series": []})
    counts = (
        summary.total_candidates,
        summary.evaluations_completed,
        summary.decision_events_recorded,
        summary.executed_count,
        summary.hold_count,
        summary.reject_count,
    )
    return pd.DataFrame(
        {
            "stage": list(_PIPELINE_STAGE_LABELS),
            "count": list(counts),
            "series": [_PIPELINE_SERIES_LABEL] * len(counts),
        }
    )


# ---------------------------------------------------------------------------
# Wave 3C: Decision Ledger Inspection rendering (ADR-064).
#
# Pure string builders over the frozen Wave 3B CandidateDecisionInspection.
# Every ledger-sourced string is HTML-escaped. No value is computed; no
# outcome / P&L / trade field is read (the contract has none). Native
# <details>/<summary> gives expand/collapse with no JS.
# ---------------------------------------------------------------------------

_E = html.escape


def _esc(value: Any) -> str:
    return _E("" if value is None else str(value))


def _bool_chip(label: str, value: bool) -> str:
    state = "true" if value else "false"
    return (
        f'<span class="pl-dli-flag pl-dli-flag--{state}">{_E(label)}='
        f'{"true" if value else "false"}</span>'
    )


def _mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _kv(label: str, value: Any) -> str:
    return (
        f'<div class="pl-dli-kv"><span class="pl-dli-k">{_E(label)}</span>'
        f'<span class="pl-dli-v">{_esc(value)}</span></div>'
    )


def _model_signals_html(model_outputs: Any) -> str:
    mo = _mapping(model_outputs)
    if not mo:
        return '<div class="pl-dli-kv"><span class="pl-dli-k">Model signals</span>' \
               '<span class="pl-dli-v pl-dli-muted">not recorded</span></div>'
    labels = (("xgboost", "XGBoost"), ("lstm", "LSTM"), ("finbert", "FinBERT"))
    rows = []
    for key, shown in labels:
        entry = _mapping(mo.get(key))
        if not entry:
            continue
        signal = entry.get("signal")
        confidence = entry.get("confidence")
        conf_txt = f"{confidence:.2f}" if isinstance(confidence, (int, float)) else _esc(confidence)
        rows.append(
            f'<div class="pl-dli-kv"><span class="pl-dli-k">{_E(shown)}</span>'
            f'<span class="pl-dli-v">{_esc(signal)} &middot; {conf_txt}</span></div>'
        )
    return "".join(rows) or (
        '<div class="pl-dli-kv"><span class="pl-dli-k">Model signals</span>'
        '<span class="pl-dli-v pl-dli-muted">not recorded</span></div>'
    )


def _intent_html(intent: Any) -> str:
    it = _mapping(intent)
    if not it:
        return _kv("Intent", None) if intent is None else ""
    parts = [_kv("Primary intent", it.get("primary_intent"))]
    if it.get("thesis"):
        parts.append(_kv("Thesis", it.get("thesis")))
    if it.get("invalidation_point"):
        parts.append(_kv("Invalidation point", it.get("invalidation_point")))
    return "".join(parts)


def _market_context_html(market_context: Any) -> str:
    mc = _mapping(market_context)
    parts = []
    for key, shown in (
        ("regime", "Regime"),
        ("decision_timestamp", "Decision timestamp"),
        ("price_data_timestamp", "Price data timestamp"),
        ("news_data_timestamp", "News data timestamp"),
    ):
        if key in mc:
            parts.append(_kv(shown, mc.get(key)))
    return "".join(parts)


def _data_completeness_html(data_completeness: Any) -> str:
    dc = _mapping(data_completeness)
    if not dc:
        return ""
    parts = [_kv("Data completeness", dc.get("status"))]
    missing = dc.get("missing_inputs")
    stale = dc.get("stale_inputs")
    if isinstance(missing, list) and missing:
        parts.append(_kv("Missing inputs", ", ".join(str(x) for x in missing)))
    if isinstance(stale, list) and stale:
        parts.append(_kv("Stale inputs", ", ".join(str(x) for x in stale)))
    return "".join(parts)


def _decision_action_fact_html(decision: DecisionInspectionResult) -> str:
    """The one recorded gate/exit fact for this decision -- verbatim,
    escaped. No synthetic passed-gate list, no 'why' beyond the record."""
    if decision.hold_message:
        return f'<div class="pl-dli-fact">{_E(decision.hold_message)}</div>'
    if decision.gate_finding is not None:
        gf = decision.gate_finding
        return (
            '<div class="pl-dli-fact pl-dli-fact--gate">'
            f'{_kv("Gate", gf.gate)}{_kv("Passed", gf.passed)}'
            f'{_kv("Detail", gf.detail)}'
            "</div>"
        )
    if decision.missing_gate_detail_message:
        return (
            f'<div class="pl-dli-fact pl-dli-muted">'
            f'{_E(decision.missing_gate_detail_message)}</div>'
        )
    if decision.entry_gates_passed:
        return '<div class="pl-dli-fact">Entry gates passed</div>'
    return ""


def _decision_details_html(decision: DecisionInspectionResult, *, is_latest: bool) -> str:
    conf = decision.final_confidence
    conf_txt = f"{conf:.2f}" if isinstance(conf, (int, float)) else "not recorded"
    action = decision.action
    badge_cls = {
        "BUY": "buy", "SELL": "sell", "HOLD": "hold", "REJECT": "reject",
    }.get(action, "neutral")
    summary = (
        '<summary class="pl-dli-decision-summary">'
        f'<span class="pl-dli-badge pl-dli-badge--{badge_cls}">{_E(action)}</span>'
        f'<span class="pl-dli-badge-sub">{_E(decision.event_type)}</span>'
        f'<span class="pl-dli-mono">{_E(decision.decision_id)}</span>'
        f'<span class="pl-dli-ts">{_E(decision.timestamp)}</span>'
        f'<span class="pl-dli-seq">seq {_esc(decision.sequence_number)}</span>'
        "</summary>"
    )
    body = (
        '<div class="pl-dli-decision-body">'
        f'{_decision_action_fact_html(decision)}'
        f'{_kv("Recorded confidence", conf_txt)}'
        f'{_kv("Candidate event ID", decision.candidate_event_id)}'
        f'{_kv("Asset", decision.asset)}'
        f'<div class="pl-dli-subgroup">{_model_signals_html(decision.model_outputs)}</div>'
        f'<div class="pl-dli-subgroup">{_intent_html(decision.intent)}</div>'
        f'<div class="pl-dli-subgroup">{_market_context_html(decision.market_context)}</div>'
        f'<div class="pl-dli-subgroup">{_data_completeness_html(decision.data_completeness)}</div>'
        "</div>"
    )
    open_attr = " open" if is_latest else ""
    return f'<details class="pl-dli-decision"{open_attr}>{summary}{body}</details>'


def _candidate_card_html(candidate: CandidateInspectionResult) -> str:
    sr = _mapping(candidate.screening_results)
    sr_bits = []
    for key, shown in (("rank", "rank"), ("composite_score", "score"),
                       ("sector", "sector")):
        if key in sr:
            sr_bits.append(f"{shown} {_esc(sr.get(key))}")  # value already escaped
    if "note" in sr:
        sr_bits.append(_esc(sr.get("note")))
    screening_line = (
        f'<div class="pl-dli-screening">{" &middot; ".join(sr_bits)}</div>'
        if sr_bits else ""
    )

    flags = "".join((
        _bool_chip("data_available", candidate.data_available),
        _bool_chip("required_models_available", candidate.required_models_available),
        _bool_chip("evaluation_requested", candidate.evaluation_requested),
        _bool_chip("evaluation_completed", candidate.evaluation_completed),
    ))

    n = len(candidate.decisions)
    latest = candidate.latest_decision
    decisions_html = "".join(
        _decision_details_html(d, is_latest=(latest is not None and d is latest))
        for d in candidate.decisions
    )
    terminal = (
        f'<div class="pl-dli-terminal">{_E(candidate.terminal_state_message)}</div>'
        if candidate.terminal_state_message else ""
    )

    state = candidate_filter_state(candidate)
    return (
        f'<div class="pl-dli-candidate pl-dli-candidate--{_E(state)}">'
        '<div class="pl-dli-candidate-head">'
        f'<span class="pl-dli-asset">{_E(candidate.asset)}</span>'
        f'<span class="pl-dli-mono">{_E(candidate.candidate_event_id)}</span>'
        f'<span class="pl-dli-ts">{_E(candidate.timestamp)}</span>'
        "</div>"
        '<div class="pl-dli-candidate-meta">'
        f'<span class="pl-dli-status">{_E(candidate.evaluation_status_label)}</span>'
        f'<span class="pl-dli-screener">screener {_E(candidate.screening_version)}</span>'
        f'<span class="pl-dli-count">{n} decision{"" if n == 1 else "s"} recorded</span>'
        "</div>"
        f'{screening_line}'
        f'<div class="pl-dli-flags">{flags}</div>'
        f'{terminal}'
        f'{decisions_html}'
        "</div>"
    )


def _ledger_freshness_html(inspection: Optional[CandidateDecisionInspection]) -> str:
    if inspection is None:
        return ""
    mtime = inspection.snapshot_mtime
    mtime_txt = (
        mtime.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
        if mtime is not None else "unknown"
    )
    through = inspection.data_through or "unknown"
    return (
        '<div class="pl-dli-freshness">'
        f'Ledger snapshot: {_E(mtime_txt)} &middot; data through {_E(through)}'
        "</div>"
    )


def _ledger_body_html(screen: PerformanceLearningScreen) -> str:
    if not screen.ledger_available:
        if screen.ledger_health is None:
            return (
                '<div class="pl-unavailable-message">'
                f'{_E(screen.ledger_unavailable_fallback)}</div>'
            )
        return render_unavailable(
            screen.ledger_health,
            fallback_message=screen.ledger_unavailable_fallback,
        )
    if screen.ledger_is_empty:
        return (
            f'<div class="pl-unavailable-message">'
            f'{_E(screen.ledger_empty_message)}</div>'
        )
    inspection = screen.ledger_inspection
    cards = "".join(
        _candidate_card_html(c)
        for c in prioritized_candidates(inspection.candidates)
    )
    boundary = (
        '<div class="pl-dli-boundary">'
        f'{_E(inspection.decision_time_boundary_notice)}'
        "</div>"
    )
    head = ""
    if screen.ledger_funnel_available:
        summary = screen.ledger_funnel_summary
        head = build_funnel_panel_html(summary) + build_filter_controls_html(summary)
    return f'{head}<div class="pl-dli-list">{cards}</div>{boundary}'


# P0-2 (Refresh): local primitive, not a cross-package import -- same
# "duplicate the primitive" convention ui/morning_brief/gradio_view.py's
# own _DISPLAY_TIMEZONE comment documents: America/Chicago, DST-aware via
# zoneinfo, "%Y-%m-%d %H:%M %Z" -- the same wall-clock convention every
# other Trading Intelligence timestamp uses.
_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")
_RENDERED_AT_PREFIX = "Rendered at "


def _format_rendered_at_html(moment: datetime) -> str:
    """Render-clock stamp for the whole screen -- when this render ran,
    not a claim about any underlying data's freshness. Reuses the
    existing .pl-dli-freshness class's small/muted-caption styling
    (theme.py -- not touched by this change) rather than adding a new CSS
    rule: a pure style-hook reuse (small font-size, secondary text color,
    caption-appropriate margin), not a claim that this line is part of
    Decision Ledger Inspection."""
    stamp = moment.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")
    return f'<div class="pl-dli-freshness">{html.escape(_RENDERED_AT_PREFIX + stamp)}</div>'


class PerformanceLearningUI:
    def __init__(
        self,
        screen: Optional[PerformanceLearningScreen] = None,
        *,
        screen_provider: Optional[Callable[[], PerformanceLearningScreen]] = None,
    ):
        """`screen_provider` (bootstrap.py's `_build_performance_learning_screen`)
        is invoked once here to obtain the screen this build renders. A
        fixed `screen` (tests) is wrapped in a constant provider. With
        neither supplied the provider is `build_mock_screen` -- the
        standalone honest-unavailable shell, never fabricated outcomes."""
        if screen_provider is not None:
            self._screen_provider = screen_provider
        elif screen is not None:
            self._screen_provider = lambda: screen
        else:
            self._screen_provider = build_mock_screen
        self._screen = self._screen_provider()

    def build(self) -> gr.Blocks:
        screen = self._screen
        with gr.Blocks(
            title="AARA Trading Intelligence — Performance & Learning",
            css=CSS + _INTEGRATION_HEALTH_CSS,
        ) as demo:
            gr.HTML(SHELL_IDENTITY_HTML, elem_classes=["aara-shell-header"])
            gr.HTML(build_shell_nav_html("Performance & Learning"), elem_classes=["aara-shell-nav"])

            gr.HTML(_PAGE_HEADER_HTML)
            # P0-2: same shared Refresh control every other screen already
            # uses -- disable -> _render -> enable, wired identically to
            # demo.load() below (see ui/portfolio_intelligence/gradio_view.py's
            # own Refresh chain, mirrored here byte-for-byte).
            refresh_button = gr.Button(
                "↻ Refresh", size="sm", scale=0, elem_classes=["aara-refresh-button"],
            )
            rendered_at_output = gr.HTML(_format_rendered_at_html(self._now()))

            # --- Prominent Sample-Size Banner ---
            # Near the top, before any individual section -- so a reader
            # sees the product's current evidence maturity once, up front,
            # rather than only inside the Model Confidence Calibration
            # section further down.
            evidence_maturity_output = gr.HTML(
                self._format_evidence_maturity_html(screen),
                elem_classes=["pl-evidence-maturity"],
            )

            # --- Outcome History (Wave 2B: real, or an honest state) ---
            gr.HTML(self._format_section_label_html(screen.outcome_history))

            populated = screen.outcome_history_available and not screen.outcome_history_is_empty

            outcome_summary_output = gr.HTML(
                self._format_summary_html(screen.summary),
                visible=populated and screen.summary is not None,
            )
            outcome_win_rate_output = gr.HTML(
                self._format_summary_html(screen.win_rate_summary),
                visible=populated and screen.win_rate_summary is not None,
            )
            outcome_loss_review_output = gr.HTML(
                self._format_loss_review_html(screen),
                visible=populated and screen.loss_review_summary is not None,
                elem_classes=["pl-loss-review"],
            )
            outcome_unavailable_output = gr.HTML(
                self._format_outcome_unavailable_html(screen),
                visible=not screen.outcome_history_available,
            )
            outcome_empty_output = gr.HTML(
                self._format_outcome_empty_html(screen),
                visible=screen.outcome_history_available and screen.outcome_history_is_empty,
            )
            outcome_table = gr.Dataframe(
                headers=_OUTCOME_HEADERS,
                value=[_outcome_row_cells(row) for row in screen.outcome_rows],
                datatype=_OUTCOME_DATATYPES,
                interactive=False,
                label="Outcome History",
                show_label=False,
                elem_classes=["pl-outcome-table"],
                visible=populated,
                **{_DATAFRAME_HEIGHT_KWARG: 360},
            )

            # --- Realized outcomes by entry market regime (Sprint 4 Item #4) ---
            # An additive slice of Outcome History: the SAME Wave 2A lineage
            # grouped by DecisionOutcome.entry_regime (verbatim -- no invented
            # regime vocabulary). Stable tree, visibility toggled -- same
            # pattern as Outcome History / calibration above.
            reg_unavailable = not screen.regime_outcomes_available
            reg_empty = (
                screen.regime_outcomes_available and screen.regime_outcomes_is_empty
            )
            reg_table = (
                screen.regime_outcomes_available and not screen.regime_outcomes_is_empty
            )
            gr.HTML(
                f'<div class="pl-section-label">{html.escape(REGIME_OUTCOMES_TITLE)}</div>'
            )
            # Sprint 1 (visualization convention): chart ABOVE the existing
            # table, visible under EXACTLY `reg_table` -- the SAME condition
            # the table below already uses. No new threshold: the regime
            # section has never had a 30-outcome floor and this chart does
            # not introduce one (see CRITICAL REGIME GATE in the sprint
            # spec / test_regime_chart_visible_when_populated_even_far_
            # below_30_outcomes).
            with gr.Column(
                elem_classes=["aara-card", "pl-regime-chart-card"], visible=reg_table,
            ) as regime_chart_card:
                gr.HTML(
                    chart_header_html(_REGIME_CHART_TITLE, _REGIME_CHART_DESCRIPTION),
                    visible=reg_table,
                )
                regime_chart = gr.BarPlot(
                    value=win_loss_long_dataframe(
                        (row.regime, row.wins, row.losses)
                        for row in screen.regime_outcome_rows
                    ),
                    x="category",
                    y="count",
                    color="outcome",
                    x_title="Entry regime",
                    y_title="Outcomes (n)",
                    color_map=WIN_LOSS_COLOR_MAP,
                    sort=[row.regime for row in screen.regime_outcome_rows],
                    height=_CHART_HEIGHT,
                    visible=reg_table,
                    elem_classes=["pl-regime-chart"],
                )
            regime_unavailable_output = gr.HTML(
                self._format_regime_outcomes_unavailable_html(screen),
                visible=reg_unavailable,
            )
            regime_empty_output = gr.HTML(
                self._format_regime_outcomes_empty_html(screen),
                visible=reg_empty,
            )
            regime_table_output = gr.HTML(
                self._format_regime_outcomes_table_html(screen),
                visible=reg_table,
                elem_classes=["pl-regime-outcomes"],
            )

            # --- Attribution Breakdown ---
            # unchanged: no wired source, fixed honest unavailable message
            gr.HTML(self._format_section_label_html(screen.attribution_breakdown))
            gr.HTML(self._format_unavailable_message_html(screen.attribution_breakdown))

            # --- Model Confidence Calibration (Sprint 4 #1) ---
            # Frozen IA label; the CONTENT is the neutral, disclaimed
            # "Historical outcome by ensemble score" tally. Stable tree,
            # visibility toggled -- same pattern as Outcome History above.
            cal_unavailable = not screen.calibration_available
            cal_empty = screen.calibration_available and screen.calibration_is_empty
            cal_small_n = (
                screen.calibration_available
                and not screen.calibration_is_empty
                and not screen.calibration_has_enough_data
            )
            cal_table = (
                screen.calibration_available and screen.calibration_has_enough_data
            )
            gr.HTML(self._format_section_label_html(screen.model_confidence_calibration))
            # Sprint 1 (visualization convention): chart ABOVE the existing
            # table, visible under EXACTLY `cal_table` -- the SAME condition
            # the table below already uses. CALIBRATION_MIN_OUTCOMES /
            # screen.calibration_has_enough_data stays the one authoritative
            # gate; no separate chart-only threshold is introduced.
            with gr.Column(
                elem_classes=["aara-card", "pl-calibration-chart-card"], visible=cal_table,
            ) as calibration_chart_card:
                gr.HTML(
                    chart_header_html(
                        CALIBRATION_CONTENT_HEADING, _CALIBRATION_CHART_DESCRIPTION
                    ),
                    visible=cal_table,
                )
                calibration_chart = gr.BarPlot(
                    value=win_loss_long_dataframe(
                        (band.label, band.wins, band.losses)
                        for band in screen.calibration_bands
                    ),
                    x="category",
                    y="count",
                    color="outcome",
                    x_title="Ensemble score band",
                    y_title="Outcomes (n)",
                    color_map=WIN_LOSS_COLOR_MAP,
                    sort=[band.label for band in screen.calibration_bands],
                    height=_CHART_HEIGHT,
                    visible=cal_table,
                    elem_classes=["pl-calibration-chart"],
                )
            calibration_unavailable_output = gr.HTML(
                self._format_calibration_unavailable_html(screen),
                visible=cal_unavailable,
            )
            calibration_empty_output = gr.HTML(
                self._format_calibration_empty_html(screen),
                visible=cal_empty,
            )
            calibration_small_n_output = gr.HTML(
                self._format_calibration_small_n_html(screen),
                visible=cal_small_n,
            )
            calibration_table_output = gr.HTML(
                self._format_calibration_table_html(screen),
                visible=cal_table,
                elem_classes=["pl-calibration"],
            )

            # --- Decision Ledger Inspection (Wave 3C, ADR-064) ---
            # Additive: rendered once, here at build() time, from the
            # already-materialized Wave 3B CandidateDecisionInspection on
            # `self._screen`. NARROW P0-2 CORRECTION: this section is
            # deliberately EXCLUDED from the Refresh/_render() dynamic-
            # output contract below -- ADR-064 §2.12 is explicit and
            # unqualified: "There is no Refresh button. The surface is
            # snapshot-bound and renders once per process from the fetched
            # snapshot... The snapshot's contents are never compared to
            # 'today' or presented as live." These four components
            # (freshness line, pipeline chart card/chart, ledger body) are
            # therefore plain, unassigned, build()-time-only components --
            # exactly as they rendered before P0-2 -- never captured into
            # `outputs`, never returned by _render(), never touched by the
            # Refresh button or demo.load() below. Its own freshness line
            # (_ledger_freshness_html) continues to show the SNAPSHOT's own
            # mtime/data-through bound, verbatim, unrelated to the page-
            # level render clock the refreshable sections now show.
            gr.HTML(
                f'<div class="pl-section-label">'
                f'{html.escape(DECISION_LEDGER_INSPECTION_TITLE)}</div>'
            )
            gr.HTML(
                _ledger_freshness_html(screen.ledger_inspection),
                visible=(
                    screen.ledger_available
                    and not screen.ledger_is_empty
                    and screen.ledger_inspection is not None
                ),
            )
            # Sprint 4: chart ABOVE the existing funnel text panel/candidate
            # cards, visible under EXACTLY `screen.ledger_funnel_available`
            # -- the SAME condition the funnel panel below already uses
            # (_ledger_body_html only builds `head` when this is True). No
            # new threshold, no second read.
            with gr.Column(
                elem_classes=["aara-card", "pl-pipeline-chart-card"],
                visible=screen.ledger_funnel_available,
            ):
                gr.HTML(
                    chart_header_html(_PIPELINE_CHART_TITLE, _PIPELINE_CHART_DESCRIPTION),
                    visible=screen.ledger_funnel_available,
                )
                gr.BarPlot(
                    value=_pipeline_chart_dataframe(
                        screen.ledger_funnel_summary
                        if screen.ledger_funnel_available else None
                    ),
                    x="stage",
                    y="count",
                    color="series",
                    x_title="Stage",
                    y_title="Candidates (n)",
                    color_map=_PIPELINE_COLOR_MAP,
                    sort=list(_PIPELINE_STAGE_LABELS),
                    height=_CHART_HEIGHT,
                    visible=screen.ledger_funnel_available,
                    elem_classes=["pl-pipeline-chart"],
                )
            gr.HTML(_ledger_body_html(screen), elem_classes=["pl-dli"])

            # P0-2 (narrowed): append-only outputs list covering only the
            # REFRESHABLE sections -- rendered_at, Evidence Maturity,
            # Outcome History, Regime, Calibration. The Decision Ledger
            # Inspection section (4 components, see above) is deliberately
            # absent from this list -- ADR-064 §2.12 compliance. 19 total.
            # rendered_at_output is first, matching every sibling screen's
            # own Refresh convention (ui/morning_brief/gradio_view.py,
            # ui/risk_intelligence/gradio_view.py, ui/portfolio_intelligence/
            # gradio_view.py).
            outputs = [
                rendered_at_output,
                evidence_maturity_output,
                outcome_summary_output, outcome_win_rate_output,
                outcome_loss_review_output,
                outcome_unavailable_output, outcome_empty_output, outcome_table,
                regime_chart_card, regime_chart,
                regime_unavailable_output, regime_empty_output, regime_table_output,
                calibration_chart_card, calibration_chart,
                calibration_unavailable_output, calibration_empty_output,
                calibration_small_n_output, calibration_table_output,
            ]

            # Same disable -> render -> enable double-submit guard chain as
            # every other screen's Refresh -- a second click while a render
            # is in flight cannot dispatch a second concurrent fetch.
            # _render is wired identically to demo.load() (same fn, same
            # outputs), only wrapped in the .then() chain here.
            refresh_button.click(
                fn=self._disable_refresh_button, inputs=None, outputs=[refresh_button],
            ).then(
                fn=self._render, inputs=None, outputs=outputs,
            ).then(
                fn=self._enable_refresh_button, inputs=None, outputs=[refresh_button],
            )
            demo.load(fn=self._render, inputs=None, outputs=outputs)

        return demo

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _disable_refresh_button() -> Dict[str, Any]:
        """First link in the Refresh double-submit guard chain (see
        build()) -- disables the button the instant it is clicked, before
        _render runs. Mirrors every other screen's own helper of the same
        name (e.g. ui/portfolio_intelligence/gradio_view.py)."""
        return gr.update(interactive=False)

    @staticmethod
    def _enable_refresh_button() -> Dict[str, Any]:
        """Last link in the Refresh double-submit guard chain (see
        build()) -- re-enables the button once _render has returned,
        success or not."""
        return gr.update(interactive=True)

    def _render(self) -> Tuple[Dict[str, Any], ...]:
        """Re-fetch through the provider and return one Gradio update per
        REFRESHABLE dynamic output, in build()'s `outputs` order. Called
        by demo.load() on page load and by the Refresh chain. Reuses every
        existing formatting helper verbatim over the freshly-fetched
        `screen` -- no new rendering logic, no fabricated fallback: a
        provider that now returns an all-unavailable screen collapses
        every section back to its own explicit unavailable state, exactly
        as a fresh build() would.

        NARROW P0-2 CORRECTION: the Decision Ledger Inspection section
        (freshness line, pipeline chart card/chart, ledger body) is
        deliberately NOT among the outputs this method returns -- ADR-064
        §2.12 requires that surface to render exactly once per process,
        snapshot-bound, never presented as live. Those four components
        stay build()-time-only, constructed from `self._screen` (the
        original single-invocation snapshot), untouched by every Refresh
        click and by demo.load() alike. This method therefore never
        re-reads the Trust Ledger snapshot and never regenerates the
        ledger's own filter/candidate HTML."""
        screen = self._screen_provider()

        populated = screen.outcome_history_available and not screen.outcome_history_is_empty
        reg_unavailable = not screen.regime_outcomes_available
        reg_empty = (
            screen.regime_outcomes_available and screen.regime_outcomes_is_empty
        )
        reg_table = (
            screen.regime_outcomes_available and not screen.regime_outcomes_is_empty
        )
        cal_unavailable = not screen.calibration_available
        cal_empty = screen.calibration_available and screen.calibration_is_empty
        cal_small_n = (
            screen.calibration_available
            and not screen.calibration_is_empty
            and not screen.calibration_has_enough_data
        )
        cal_table = (
            screen.calibration_available and screen.calibration_has_enough_data
        )

        return (
            gr.update(value=_format_rendered_at_html(self._now())),
            gr.update(value=self._format_evidence_maturity_html(screen)),
            gr.update(
                value=self._format_summary_html(screen.summary),
                visible=populated and screen.summary is not None,
            ),
            gr.update(
                value=self._format_summary_html(screen.win_rate_summary),
                visible=populated and screen.win_rate_summary is not None,
            ),
            gr.update(
                value=self._format_loss_review_html(screen),
                visible=populated and screen.loss_review_summary is not None,
            ),
            gr.update(
                value=self._format_outcome_unavailable_html(screen),
                visible=not screen.outcome_history_available,
            ),
            gr.update(
                value=self._format_outcome_empty_html(screen),
                visible=screen.outcome_history_available and screen.outcome_history_is_empty,
            ),
            gr.update(
                value=[_outcome_row_cells(row) for row in screen.outcome_rows],
                visible=populated,
            ),
            gr.update(visible=reg_table),
            gr.update(
                value=win_loss_long_dataframe(
                    (row.regime, row.wins, row.losses)
                    for row in screen.regime_outcome_rows
                ),
                sort=[row.regime for row in screen.regime_outcome_rows],
                visible=reg_table,
            ),
            gr.update(
                value=self._format_regime_outcomes_unavailable_html(screen),
                visible=reg_unavailable,
            ),
            gr.update(
                value=self._format_regime_outcomes_empty_html(screen),
                visible=reg_empty,
            ),
            gr.update(
                value=self._format_regime_outcomes_table_html(screen),
                visible=reg_table,
            ),
            gr.update(visible=cal_table),
            gr.update(
                value=win_loss_long_dataframe(
                    (band.label, band.wins, band.losses)
                    for band in screen.calibration_bands
                ),
                sort=[band.label for band in screen.calibration_bands],
                visible=cal_table,
            ),
            gr.update(
                value=self._format_calibration_unavailable_html(screen),
                visible=cal_unavailable,
            ),
            gr.update(
                value=self._format_calibration_empty_html(screen),
                visible=cal_empty,
            ),
            gr.update(
                value=self._format_calibration_small_n_html(screen),
                visible=cal_small_n,
            ),
            gr.update(
                value=self._format_calibration_table_html(screen),
                visible=cal_table,
            ),
        )

    @staticmethod
    def _format_section_label_html(section: PerformanceLearningSection) -> str:
        return f'<div class="pl-section-label">{html.escape(section.title)}</div>'

    @staticmethod
    def _format_unavailable_message_html(section: PerformanceLearningSection) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(section.unavailable_message)}'
            "</div>"
        )

    @staticmethod
    def _format_outcome_unavailable_html(screen: PerformanceLearningScreen) -> str:
        """`outcome_health is None` (standalone / no provider) -> this
        section's own fixed message, byte-identical to the pre-Wave-2B
        render. A real non-HEALTHY health -> the shared ADR-061
        "Data unavailable -- <reason>" phrase (reason from status only;
        never the provider name or detail)."""
        if screen.outcome_health is None:
            return PerformanceLearningUI._format_unavailable_message_html(
                screen.outcome_history
            )
        return render_unavailable(
            screen.outcome_health,
            fallback_message=screen.outcome_history.unavailable_message,
        )

    @staticmethod
    def _format_outcome_empty_html(screen: PerformanceLearningScreen) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(screen.outcome_history_empty_message)}'
            "</div>"
        )

    @staticmethod
    def _format_summary_html(summary: Optional[str]) -> str:
        if not summary:
            return ""
        return f'<div class="pl-summary">{html.escape(summary)}</div>'

    # --- Prominent Sample-Size Banner --------------------------------------

    @staticmethod
    def _format_evidence_maturity_html(screen: PerformanceLearningScreen) -> str:
        """`calibration_health is None` (standalone / no provider) -> a
        fixed fallback message; a real non-HEALTHY health -> the shared
        ADR-061 "Data unavailable -- <reason>" phrase -- same two-branch
        rule _format_calibration_unavailable_html already uses. Otherwise
        renders screen.evidence_maturity_heading (the SAME calibration_
        total_outcomes / CALIBRATION_MIN_OUTCOMES this screen's own
        Model Confidence Calibration section already gates on) alongside
        the fixed EVIDENCE_MATURITY_DISCLAIMER -- never a significance,
        predictive-validity, or readiness claim."""
        if screen.calibration_health is None:
            return (
                f'<div class="pl-unavailable-message">'
                f'{html.escape(_EVIDENCE_MATURITY_UNAVAILABLE_MESSAGE)}</div>'
            )
        heading = screen.evidence_maturity_heading
        if heading is None:
            return render_unavailable(
                screen.calibration_health,
                fallback_message=_EVIDENCE_MATURITY_UNAVAILABLE_MESSAGE,
            )
        return (
            f'<div class="pl-evidence-maturity-heading">{html.escape(heading)}</div>'
            f'<div class="pl-evidence-maturity-disclaimer">'
            f'{html.escape(EVIDENCE_MATURITY_DISCLAIMER)}</div>'
        )

    # --- Sprint 1 Phase 3: Loss/failure-analysis callout ------------------

    @staticmethod
    def _format_loss_review_html(screen: PerformanceLearningScreen) -> str:
        """Concise, purely descriptive callout -- see bootstrap.py's
        _loss_review_summary() for exactly what is and is not computed.
        Empty string when there is nothing to show yet (outcome read
        unavailable, or not populated) -- the caller's `visible=` already
        gates on the same condition; this stays defensive against a direct
        call with an unpopulated screen."""
        summary = screen.loss_review_summary
        if not summary:
            return ""
        return (
            f'<div class="pl-summary">{html.escape(summary)}</div>'
            f'<div class="pl-loss-review-disclaimer">'
            f'{html.escape(LOSS_REVIEW_DISCLAIMER)}</div>'
        )

    # --- Sprint 4 #1: Model Confidence Calibration -----------------------

    @staticmethod
    def _format_calibration_unavailable_html(screen: PerformanceLearningScreen) -> str:
        """`calibration_health is None` (standalone / no provider) -> this
        section's own fixed message, byte-identical to the pre-Sprint-4
        render. A real non-HEALTHY health -> the shared ADR-061
        "Data unavailable -- <reason>" phrase (reason from status only)."""
        if screen.calibration_health is None:
            return PerformanceLearningUI._format_unavailable_message_html(
                screen.model_confidence_calibration
            )
        return render_unavailable(
            screen.calibration_health,
            fallback_message=screen.model_confidence_calibration.unavailable_message,
        )

    @staticmethod
    def _format_calibration_empty_html(screen: PerformanceLearningScreen) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(screen.calibration_empty_message)}'
            "</div>"
        )

    @staticmethod
    def _format_calibration_small_n_html(screen: PerformanceLearningScreen) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(screen.calibration_small_n_message)}'
            "</div>"
        )

    @staticmethod
    def _format_calibration_table_html(screen: PerformanceLearningScreen) -> str:
        """Heading (neutral wording) + disclaimer + one row per band.
        Every interpolated value is HTML-escaped. Win rate is blank -- never
        a fabricated 0% -- for a band that counted no outcomes."""
        rows = []
        for band in screen.calibration_bands:
            rate = "" if band.win_rate is None else f"{band.win_rate:.0%}"
            rows.append(
                "<tr>"
                f'<td class="pl-cal-band">{html.escape(band.label)}</td>'
                f'<td class="pl-cal-num">{html.escape(str(band.n))}</td>'
                f'<td class="pl-cal-num">{html.escape(str(band.wins))}</td>'
                f'<td class="pl-cal-num">{html.escape(str(band.losses))}</td>'
                f'<td class="pl-cal-num">{html.escape(rate)}</td>'
                "</tr>"
            )
        return (
            f'<div class="pl-cal-heading">{html.escape(CALIBRATION_CONTENT_HEADING)}</div>'
            f'<div class="pl-cal-disclaimer">{html.escape(CALIBRATION_DISCLAIMER)}</div>'
            '<table class="pl-cal-table">'
            "<thead><tr>"
            "<th>Ensemble score band</th><th>Outcomes (n)</th>"
            "<th>Wins</th><th>Losses</th><th>Win rate</th>"
            "</tr></thead>"
            f'<tbody>{"".join(rows)}</tbody>'
            "</table>"
        )

    # --- Sprint 4 Item #4: Realized outcomes by entry market regime -----

    @staticmethod
    def _format_regime_outcomes_unavailable_html(
        screen: PerformanceLearningScreen,
    ) -> str:
        """`regime_outcome_health is None` (standalone / no provider) -> this
        slice's own fixed message. A real non-HEALTHY health -> the shared
        ADR-061 "Data unavailable -- <reason>" phrase (reason from status
        only)."""
        if screen.regime_outcome_health is None:
            return (
                '<div class="pl-unavailable-message">'
                f'{html.escape(screen.regime_outcomes_unavailable_message)}'
                "</div>"
            )
        return render_unavailable(
            screen.regime_outcome_health,
            fallback_message=screen.regime_outcomes_unavailable_message,
        )

    @staticmethod
    def _format_regime_outcomes_empty_html(screen: PerformanceLearningScreen) -> str:
        return (
            '<div class="pl-unavailable-message">'
            f'{html.escape(screen.regime_outcomes_empty_message)}'
            "</div>"
        )

    @staticmethod
    def _format_regime_outcomes_table_html(screen: PerformanceLearningScreen) -> str:
        """Disclaimer + one row per entry regime, in the order the fold
        already fixed (real regimes alphabetical, "Not recorded" last).
        Every interpolated value is HTML-escaped. Win rate is blank -- never
        a fabricated 0% -- for a row that counted no outcomes."""
        rows = []
        for row in screen.regime_outcome_rows:
            rate = "" if row.win_rate is None else f"{row.win_rate:.0%}"
            rows.append(
                "<tr>"
                f'<td class="pl-regime-label">{html.escape(row.regime)}</td>'
                f'<td class="pl-regime-num">{html.escape(str(row.n))}</td>'
                f'<td class="pl-regime-num">{html.escape(str(row.wins))}</td>'
                f'<td class="pl-regime-num">{html.escape(str(row.losses))}</td>'
                f'<td class="pl-regime-num">{html.escape(rate)}</td>'
                "</tr>"
            )
        return (
            f'<div class="pl-regime-disclaimer">{html.escape(REGIME_OUTCOMES_DISCLAIMER)}</div>'
            '<table class="pl-regime-table">'
            "<thead><tr>"
            "<th>Entry regime</th><th>Outcomes (n)</th>"
            "<th>Wins</th><th>Losses</th><th>Win rate</th>"
            "</tr></thead>"
            f'<tbody>{"".join(rows)}</tbody>'
            "</table>"
        )
