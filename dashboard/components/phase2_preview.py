"""Phase 2 dashboard wiring for analytics/regime_views.py and
improvement_proposals.py -- explicitly unfrozen ahead of Phase 1B/1A
acceptance (user decision, 2026-07-30; see CURRENT_ARCHITECTURE.md's Phase 2
section). analytics/experiments.py is deliberately NOT wired here: its
run_experiment() is blocked on Phase 1B's reweighting-recommendation format,
which doesn't exist yet -- a missing spec, not a missing-data problem, so
there is nothing honest to preview.

Regime performance follows the same real-or-illustrative pattern as
dashboard/components/trust_scorecard.py's calibration buckets: the
analytics query stays real always, the illustrative fallback lives only
here. Improvement proposals need no fallback -- it's a real, always-honest
empty list until someone actually creates one.
"""
from __future__ import annotations

from loguru import logger

from analytics.regime_views import regime_performance, RegimePerformance
from analytics.improvement_proposals import list_proposals
from dashboard.design_system import (
    GAIN, NEURAL,
    _section, _card, _wrap, _empty_state, _illustrative_banner,
    th_style, td_style,
)
from dashboard.components._ledger_analytics import connect_ledger_or_none, rate_color, ret_color
from bot.core.error_logger import safe_render, timed

_logger = logger
_connect = connect_ledger_or_none
_rate_color = rate_color
_ret_color = ret_color


def _regime_row(r) -> str:
    return (f'<tr><td {td_style()}>{r.regime}</td>'
            f'<td {td_style("text-align:right;")}>{r.decisions}</td>'
            f'<td {td_style(f"text-align:right;color:{_rate_color(r.win_rate)};")}>{r.win_rate:.0%}</td>'
            f'<td {td_style(f"text-align:right;color:{_ret_color(r.avg_net_return)};")}>{r.avg_net_return:+.1%}</td></tr>')


_ILLUSTRATIVE_REGIMES = [
    RegimePerformance("TRENDING", 12, 0.67, 0.022),
    RegimePerformance("RANGING", 9, 0.56, 0.008),
    RegimePerformance("VOLATILE", 3, 0.33, -0.019),
]


@timed(_logger)
@safe_render("Regime Performance")
def render_regime_performance() -> str:
    conn = _connect()
    if conn is None:
        return (f'<div class="nt nt-wrap">'
                f'{_section("🌡️", "Regime Performance", "Phase 2 preview")}'
                f'{_card("Trust Ledger unavailable.")}</div>')
    try:
        regimes = regime_performance(conn)
    finally:
        conn.close()

    is_real = bool(regimes)
    rows_html = "".join(_regime_row(r) for r in (regimes if is_real else _ILLUSTRATIVE_REGIMES))
    banner = "" if is_real else _illustrative_banner(
        "no closed decisions yet -- this is what the real breakdown will look like."
    )
    th_cells = "".join(f'<th {th_style()}>{h}</th>' for h in ["Regime", "Decisions", "Win Rate", "Avg Return"])
    table = (
        f'<table style="width:100%;border-collapse:collapse;font-family:Inter,system-ui,sans-serif;">'
        f'<thead><tr>{th_cells}</tr></thead><tbody>{rows_html}</tbody></table>'
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("🌡️", "Regime Performance", "Win rate by market regime -- Phase 2 preview")}'
        f'{banner}{_wrap(table)}'
        f'</div>'
    )


@timed(_logger)
@safe_render("Improvement Proposals")
def render_improvement_proposals() -> str:
    proposals = list_proposals()
    if not proposals:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("📋", "Improvement Proposals", "Phase 2 preview")}'
            f'{_card(_empty_state("📋", "No proposals yet", "Created once Phase 1B evidence identifies a candidate model change."))}'
            f'</div>'
        )

    rows_html = ""
    for p in proposals:
        status = "Approved" if p.approved_at else "Pending"
        status_color = GAIN if p.approved_at else NEURAL
        rows_html += (
            f'<tr><td {td_style()}>{p.proposal_id}</td>'
            f'<td {td_style(nowrap=False)}>{p.what_changes}</td>'
            f'<td {td_style(f"color:{status_color};")}>{status}</td>'
            f'<td {td_style()}>{p.created_at[:10]}</td></tr>'
        )
    th_cells = "".join(f'<th {th_style()}>{h}</th>' for h in ["ID", "What Changes", "Status", "Created"])
    table = (
        f'<table style="width:100%;border-collapse:collapse;font-family:Inter,system-ui,sans-serif;">'
        f'<thead><tr>{th_cells}</tr></thead><tbody>{rows_html}</tbody></table>'
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("📋", "Improvement Proposals", f"{len(proposals)} recorded -- Phase 2 preview")}'
        f'{_wrap(table)}'
        f'</div>'
    )


from dashboard.registry import ComponentSpec, RefreshGroup, register
register(ComponentSpec("regime_performance_out", RefreshGroup.SLOW, render_regime_performance, priority=44))
register(ComponentSpec("improvement_proposals_out", RefreshGroup.FAST, render_improvement_proposals, priority=45))
