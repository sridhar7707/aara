"""Counterfactual Analysis — Phase 5 Step 12 of the Decision Intelligence roadmap.

Answers "what happened to the ones we passed on?" for every decision that
never became a trade (blocked by a gate, rejected by a human, or expired
waiting on one). Evidence-gated like Decision Quality / Loss Explanation /
Investor Profile — reports "not enough data" rather than a verdict below
the threshold, and never judges a rejection before its outcome window has
actually closed (evaluate_rejected_decision() enforces that itself).
"""
from __future__ import annotations

from loguru import logger

from bot.core.error_logger import safe_render, timed
from dashboard.data import get_db_conn
from dashboard.design_system import (
    GAIN, LOSS, TEXT2, TEXT3,
    FONT_LABEL, WEIGHT_BOLD,
    _section, _empty_state, _card, _stat_card,
)
from database.services.decision_service import list_rejected_decisions, evaluate_rejected_decision

_logger = logger

_MIN_EVALUATED_FOR_INSIGHTS = 15  # matches the ~15-20 evidence-gate threshold used elsewhere in Phase 3/5
_MIN_PER_GATE_REASON        = 3   # a gate needs at least this many evaluated misses to call out its hit rate
_MAX_CANDIDATES_PER_RENDER  = 30  # bounds yfinance calls per refresh (RefreshGroup.SLOW, every 5 min)


def _evaluated_rejections() -> list[dict]:
    """Rejected/blocked decisions whose outcome window has closed, with a
    known forward_return. Still-pending-window and data-unavailable rows are
    silently excluded here (not an error — just not evaluable yet)."""
    with get_db_conn() as con:
        candidates = list_rejected_decisions(con, limit=_MAX_CANDIDATES_PER_RENDER)
        results = []
        for c in candidates:
            r = evaluate_rejected_decision(con, c["decision_id"])
            if r.get("forward_return") is not None:
                results.append({**c, "forward_return": r["forward_return"]})
        return results


def _gate_reason_breakdown(rows: list[dict]) -> tuple[str | None, str | None]:
    """(most-often-wrong gate, most-often-right gate) by how often the symbol
    it blocked would have gone on to gain. None if no gate_reason group has
    enough evaluated misses to say anything meaningful."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        reason = r.get("gate_reason") or "unspecified"
        groups.setdefault(reason, []).append(r)
    qualified = {k: v for k, v in groups.items() if len(v) >= _MIN_PER_GATE_REASON}
    if not qualified:
        return None, None
    would_have_won_rate = {k: sum(1 for r in v if r["forward_return"] > 0) / len(v) for k, v in qualified.items()}
    worst = max(would_have_won_rate, key=lambda k: would_have_won_rate[k])  # blocks winners most often
    best  = min(would_have_won_rate, key=lambda k: would_have_won_rate[k])  # correctly avoids losers most often
    if worst == best:
        return None, None
    return worst, best


@timed(_logger)
@safe_render("Counterfactual Analysis")
def render_counterfactual_analysis() -> str:
    rows = _evaluated_rejections()
    n = len(rows)
    if n < _MIN_EVALUATED_FOR_INSIGHTS:
        plural = "s" if n != 1 else ""
        title = f"{n} evaluated rejection{plural} so far"
        subtitle = f"Need {_MIN_EVALUATED_FOR_INSIGHTS - n} more before patterns are meaningful."
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("🔍", "Counterfactual Analysis", "")}'
            f'{_card(_empty_state("🔍", title, subtitle))}'
            f'</div>'
        )

    would_have_won = sum(1 for r in rows if r["forward_return"] > 0)
    would_have_win_rate = would_have_won / n
    avg_return = sum(r["forward_return"] for r in rows) / n

    worst_gate, best_gate = _gate_reason_breakdown(rows)

    wr_color = LOSS if would_have_win_rate >= 0.60 else GAIN  # high "would-have-won" rate is a bad sign here
    ret_color = LOSS if avg_return > 0 else GAIN               # positive missed return means we missed gains

    cards = (
        f'<div class="nt-cards">'
        + _stat_card("Evaluated Rejections", str(n), TEXT2, TEXT2, "gates blocked or a human passed", 0.0)
        + _stat_card("Would-Have Won", f"{would_have_win_rate:.0%}", TEXT2, wr_color,
                     "of rejected symbols gained afterward", 0.06)
        + _stat_card("Avg Forward Return", f"{avg_return:+.1%}", TEXT2, ret_color,
                     "average move after we passed", 0.12)
        + f'</div>'
    )
    findings = (
        f'<div style="padding:10px 14px;font-size:{FONT_LABEL};color:{TEXT2};">'
        + (f'<span style="color:{LOSS};font-weight:{WEIGHT_BOLD};">Most often blocks winners:</span> '
           f'{worst_gate}<br>' if worst_gate else "")
        + (f'<span style="color:{GAIN};font-weight:{WEIGHT_BOLD};">Most often avoids losers:</span> '
           f'{best_gate}<br>' if best_gate else "")
        + ('No single gate reason stands out yet — need more evaluated misses per reason.'
           if not worst_gate and not best_gate else "")
        + f'</div>'
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("🔍", "Counterfactual Analysis", f"Based on {n} evaluated rejections")}'
        f'{cards}{findings}'
        f'</div>'
    )


from dashboard.registry import ComponentSpec, RefreshGroup, register
register(ComponentSpec("counterfactual_out", RefreshGroup.SLOW, render_counterfactual_analysis, priority=86))
