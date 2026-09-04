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
from typing import Any, Callable, List, Mapping, Optional

import gradio as gr

from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    CandidateDecisionInspection,
    CandidateInspectionResult,
    DecisionInspectionResult,
    candidate_filter_state,
)
from applications.trading_intelligence.ui.performance_learning.decision_ledger_funnel_view import (
    build_filter_controls_html,
    build_funnel_panel_html,
    prioritized_candidates,
)
from applications.trading_intelligence.ui.integration_health_view import (
    CSS as _INTEGRATION_HEALTH_CSS,
    render_unavailable,
)
from applications.trading_intelligence.ui.performance_learning.mock_data import build_mock_screen
from applications.trading_intelligence.ui.performance_learning.screen import (
    DECISION_LEDGER_INSPECTION_TITLE,
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

_OUTCOME_HEADERS = [
    "Decision", "Entry date", "Status", "Exit date", "Holding days",
    "Realized P&L $", "Realized P&L %", "Exit basis", "Pairing method",
    "Pairing confidence", "Direction",
]

_PAGE_HEADER_HTML = (
    '<div class="pl-page-header">'
    "<h2>Performance & Learning</h2>"
    '<div class="pl-subtitle">Outcome history, attribution, and model confidence calibration</div>'
    "</div>"
)


def _outcome_row_cells(row: OutcomeHistoryRow) -> List[str]:
    return [
        row.decision, row.entry_date, row.status, row.exit_date, row.holding_days,
        row.realized_pnl_usd, row.realized_pnl_pct, row.exit_basis,
        row.pairing_method, row.pairing_confidence, row.direction,
    ]


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

            # --- Outcome History (Wave 2B: real, or an honest state) ---
            gr.HTML(self._format_section_label_html(screen.outcome_history))

            populated = screen.outcome_history_available and not screen.outcome_history_is_empty

            gr.HTML(
                self._format_summary_html(screen.summary),
                visible=populated and screen.summary is not None,
            )
            gr.HTML(
                self._format_outcome_unavailable_html(screen),
                visible=not screen.outcome_history_available,
            )
            gr.HTML(
                self._format_outcome_empty_html(screen),
                visible=screen.outcome_history_available and screen.outcome_history_is_empty,
            )
            gr.Dataframe(
                headers=_OUTCOME_HEADERS,
                value=[_outcome_row_cells(row) for row in screen.outcome_rows],
                datatype=["str"] * len(_OUTCOME_HEADERS),
                interactive=False,
                label="Outcome History",
                show_label=False,
                elem_classes=["pl-outcome-table"],
                visible=populated,
                **{_DATAFRAME_HEIGHT_KWARG: 360},
            )

            # --- Attribution Breakdown / Model Confidence Calibration ---
            # unchanged: no wired source, fixed honest unavailable message
            for section in (
                screen.attribution_breakdown,
                screen.model_confidence_calibration,
            ):
                gr.HTML(self._format_section_label_html(section))
                gr.HTML(self._format_unavailable_message_html(section))

            # --- Decision Ledger Inspection (Wave 3C, ADR-064) ---
            # Additive: rendered once from the already-materialized Wave 3B
            # CandidateDecisionInspection on the screen. No provider call
            # here, no demo.load, no Refresh. Decision-time only.
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
            gr.HTML(_ledger_body_html(screen), elem_classes=["pl-dli"])

        return demo

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
