"""Wave 3D: pure string builders for the Decision Ledger Inspection
funnel-summary panel and the pure-CSS decision-state filter (ADR-064, no
scope expansion).

Self-contained: stdlib ``html`` plus the Wave 3B contract types only. No
Gradio, no service, no adapter, no I/O. Every figure rendered here is a
literal count from :class:`LedgerFunnelSummary`; every ledger-sourced
free-text value (gate names) is HTML-escaped. The filter is a hidden
native radio group -- ``theme.py``'s ``#pl-dli-filter-<key>:checked ~
.pl-dli-list`` rules do all show/hide with zero JavaScript and no Gradio
event handler.
"""
import html
from typing import List, Tuple

from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    FILTER_STATE_EXECUTED,
    CandidateInspectionResult,
    LedgerFunnelSummary,
    candidate_filter_state,
)

_E = html.escape

# The six filter buckets offered in the UI, in display order. "other" is a
# residual class (a recorded decision whose action is none of
# BUY/SELL/HOLD/REJECT) with no chip -- such a candidate shows only under
# "All".
_FILTER_CHIPS: Tuple[Tuple[str, str], ...] = (
    ("all", "All"),
    ("executed", "Executed"),
    ("hold", "Hold"),
    ("rejected", "Rejected"),
    ("no-decision", "No Decision"),
    ("incomplete", "Incomplete"),
)


def prioritized_candidates(
    candidates: Tuple[CandidateInspectionResult, ...],
) -> List[CandidateInspectionResult]:
    """Default ordering for the card list: candidates that ultimately
    executed float to the top so they are reachable without scrolling past
    every rejection.

    A stable partition only -- the Wave 3B
    ``(sequence_number, candidate_event_id)`` order is preserved inside
    each group, ``sequence_number`` semantics are untouched, "latest" is
    not redefined, and no candidate is dropped or hidden.
    """
    executed: List[CandidateInspectionResult] = []
    rest: List[CandidateInspectionResult] = []
    for c in candidates:
        target = executed if candidate_filter_state(c) == FILTER_STATE_EXECUTED else rest
        target.append(c)
    return executed + rest


def _filter_chip_count(summary: LedgerFunnelSummary, key: str) -> int:
    return {
        "all": summary.total_candidates,
        "executed": summary.candidates_executed,
        "hold": summary.candidates_hold,
        "rejected": summary.candidates_rejected,
        "no-decision": summary.candidates_no_decision,
        "incomplete": summary.candidates_incomplete,
    }[key]


def build_filter_controls_html(summary: LedgerFunnelSummary) -> str:
    """Hidden native radio group + a row of labels. "All" is pre-checked,
    so the filter is always explicit and fully reversible."""
    radios = "".join(
        f'<input type="radio" name="pl-dli-filter" '
        f'id="pl-dli-filter-{key}" class="pl-dli-filter-radio" '
        f'data-filter="{key}"{" checked" if key == "all" else ""}>'
        for key, _ in _FILTER_CHIPS
    )
    labels = "".join(
        f'<label for="pl-dli-filter-{key}" class="pl-dli-filter-label">'
        f'{_E(text)} <span class="pl-dli-filter-n">{_filter_chip_count(summary, key)}</span>'
        "</label>"
        for key, text in _FILTER_CHIPS
    )
    return f'{radios}<div class="pl-dli-filter">{labels}</div>'


def build_funnel_panel_html(summary: LedgerFunnelSummary) -> str:
    """Count-only aggregation panel. No percentage, ratio, rate, or causal
    claim -- three populations (candidates, decision events, and the
    executed subset) are stated as distinct literal counts."""
    lines = [
        '<div class="pl-dli-funnel-title">Decision Ledger</div>',
        '<div class="pl-dli-funnel-line">'
        f'{summary.total_candidates} candidates screened &middot; '
        f'{summary.evaluations_completed} evaluations completed &middot; '
        f'{summary.evaluations_incomplete} not completed</div>',
        '<div class="pl-dli-funnel-line">'
        f'{summary.decision_events_recorded} decisions recorded from '
        f'{summary.candidates_with_decision} of {summary.total_candidates} candidates</div>',
        '<div class="pl-dli-funnel-line pl-dli-funnel-headline">'
        f'{summary.executed_count} executed &middot; '
        f'{summary.hold_count} held &middot; '
        f'{summary.reject_count} rejected</div>',
        '<div class="pl-dli-funnel-line pl-dli-funnel-sub">'
        f'BUY {summary.buy_count} &middot; SELL {summary.sell_count} &middot; '
        f'HOLD {summary.hold_count} &middot; REJECT {summary.reject_count}</div>',
    ]
    if summary.reject_count and summary.rejection_reasons:
        gates = "".join(
            '<span class="pl-dli-funnel-gate">'
            f'{_E(reason.gate)} '
            f'<span class="pl-dli-funnel-gate-n">{reason.count}</span></span>'
            for reason in summary.rejection_reasons
        )
        lines.append(
            '<div class="pl-dli-funnel-why">'
            '<div class="pl-dli-funnel-why-title">Why AARA did not trade more</div>'
            '<div class="pl-dli-funnel-why-line">'
            f'{summary.reject_count} rejected decisions &middot; '
            "recorded blocking gates:</div>"
            f'<div class="pl-dli-funnel-gates">{gates}</div>'
            "</div>"
        )
    return f'<div class="pl-dli-funnel">{"".join(lines)}</div>'
