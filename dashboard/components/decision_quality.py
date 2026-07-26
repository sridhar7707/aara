"""Decision Quality Summary — the Decision Intelligence "home card."

Answers "why should I trust this?" across every completed decision, not
just executed trades — every number here traces back to a decision_id.
Deliberately not a single 0-100 score (a lone number invites false
precision); it's a small set of evidence-gated facts instead.
"""
from __future__ import annotations

import datetime

from loguru import logger

from bot.core.error_logger import safe_render, timed
from config import SECTOR_MAP
from dashboard.charts import _get_sym_hist
from dashboard.data import safe_query
from dashboard.design_system import (
    GAIN, LOSS, NEURAL, TEXT1, TEXT2, TEXT3,
    FONT_LABEL, WEIGHT_BOLD,
    _section, _empty_state, _card, _stat_card,
)

_logger = logger

_MIN_FOR_TREND     = 6   # need at least 3 decisions per half to compare
_MIN_FOR_DIMENSION = 3   # need at least this many decisions in a sector/reason to call it a strength or weakness


def _completed_decisions() -> list[tuple]:
    """(decision_id, symbol, outcome_status, outcome_known_at, created_at) for
    every decision with a known outcome, oldest first. Deliberately reads
    only decision_log, not trades — decision_log.trade_id links to the
    executing BUY (pnl_pct always 0 there), not the eventual closing SELL,
    so outcome_status (already correctly classified by complete_decision())
    is the only reliable per-decision win/loss signal without a fragile
    second join to guess which trades row actually closed it."""
    return safe_query(
        "SELECT decision_id, symbol, outcome_status, outcome_known_at, created_at "
        "FROM decision_log WHERE execution_status='EXECUTED' AND outcome_status != 'UNKNOWN' "
        "ORDER BY outcome_known_at ASC",
        default=[],
    ) or []


def _nearest_snapshot_value(cutoff: str, before: bool) -> float | None:
    """Portfolio value at-or-before (before=True) / at-or-after (before=False)
    a timestamp, excluding SELL_RECONCILE-tainted snapshot rows."""
    op = "<=" if before else ">="
    order = "DESC" if before else "ASC"
    rows = safe_query(
        f"SELECT portfolio_value FROM portfolio_snapshots ps "
        f"WHERE timestamp {op} ? AND portfolio_value > 0 "
        f"AND NOT EXISTS (SELECT 1 FROM trades t WHERE t.action='SELL_RECONCILE' "
        f"AND t.portfolio_value = ps.portfolio_value) "
        f"ORDER BY timestamp {order} LIMIT 1",
        (cutoff,), default=[],
    )
    return float(rows[0][0]) if rows else None


def _spy_close_near(spy_hist, cutoff_iso: str) -> float | None:
    if spy_hist is None or spy_hist.empty or "Close" not in spy_hist.columns:
        return None
    try:
        cutoff_date = datetime.datetime.fromisoformat(str(cutoff_iso).replace("Z", "+00:00")).date()
    except Exception as exc:
        _logger.debug(f"_spy_close_near: cutoff parse: {exc}")
        return None
    dates  = [d.date() if hasattr(d, "date") else d for d in spy_hist.index]
    closes = list(spy_hist["Close"])
    for i in range(len(dates) - 1, -1, -1):
        if dates[i] <= cutoff_date:
            return float(closes[i])
    return None


def _win_rate(rows: list[tuple]) -> float:
    return sum(1 for r in rows if r[2] == "WIN") / len(rows) if rows else 0.0


def _decision_quality_trend(rows: list[tuple]) -> tuple[str, str] | None:
    """(label, color) comparing win rate in the first half vs second half of
    completed decisions, chronologically. None if there isn't enough data."""
    if len(rows) < _MIN_FOR_TREND:
        return None
    mid = len(rows) // 2
    delta = _win_rate(rows[mid:]) - _win_rate(rows[:mid])
    if delta > 0.10:
        return "Improving", GAIN
    if delta < -0.10:
        return "Declining", LOSS
    return "Stable", NEURAL


def _best_worst_dimension(rows: list[tuple], key_fn) -> tuple[str | None, str | None]:
    """Group rows by key_fn(row) and return (best_key, worst_key) by win rate.
    A group only qualifies as "best" with a genuinely good win rate (>=60%,
    matching the GAIN threshold used elsewhere in this codebase) or "worst"
    with a genuinely poor one (<45%) — being the only group with enough
    decisions doesn't make it a strength if its win rate is actually
    mediocre. (None, None) if no group clears either bar."""
    groups: dict[str, list[tuple]] = {}
    for r in rows:
        groups.setdefault(key_fn(r), []).append(r)
    qualified = {k: v for k, v in groups.items() if len(v) >= _MIN_FOR_DIMENSION}
    if not qualified:
        return None, None
    wr = {k: _win_rate(v) for k, v in qualified.items()}
    strong = {k: v for k, v in wr.items() if v >= 0.60}
    weak   = {k: v for k, v in wr.items() if v < 0.45}
    best  = max(strong, key=lambda k: strong[k]) if strong else None
    worst = min(weak, key=lambda k: weak[k]) if weak else None
    return best, worst


@timed(_logger)
@safe_render("Decision Quality Summary")
def render_decision_quality_summary() -> str:
    rows = _completed_decisions()
    if not rows:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("🧭", "Investment Intelligence Summary", "")}'
            f'{_card(_empty_state("🧭", "No completed decisions yet", "This builds as decisions are made and their outcomes become known."))}'
            f'</div>'
        )

    n = len(rows)
    window_start, window_end = rows[0][4], rows[-1][3]

    pv_start = _nearest_snapshot_value(window_start, before=True)
    pv_end   = _nearest_snapshot_value(window_end, before=False) or _nearest_snapshot_value(window_end, before=True)
    port_ret = (pv_end / pv_start - 1) if pv_start and pv_end and pv_start > 0 else None

    spy_hist = _get_sym_hist("SPY")
    spy_start = _spy_close_near(spy_hist, window_start)
    spy_end   = _spy_close_near(spy_hist, window_end)
    spy_ret = (spy_end / spy_start - 1) if spy_start and spy_end and spy_start > 0 else None

    trend = _decision_quality_trend(rows)
    trend_label, trend_color = trend if trend else ("Early evidence", TEXT3)

    best_sector, worst_sector = _best_worst_dimension(rows, lambda r: SECTOR_MAP.get(r[1], "Other").replace("_", " "))
    strength = f"{best_sector} selection" if best_sector else None
    weakness = f"{worst_sector} selection" if worst_sector and worst_sector != best_sector else None

    port_html = f"{port_ret:+.1%}" if port_ret is not None else "&mdash;"
    spy_html  = f"{spy_ret:+.1%}" if spy_ret is not None else "&mdash;"
    port_c = GAIN if (port_ret or 0) >= 0 else LOSS
    spy_c  = GAIN if (spy_ret or 0) >= 0 else LOSS

    cards = (
        f'<div class="nt-cards">'
        + _stat_card("Portfolio", port_html, TEXT2, port_c, f"{n} completed decisions", 0.0)
        + _stat_card("SPY (same period)", spy_html, TEXT2, spy_c, "benchmark over the same window", 0.06)
        + _stat_card("Decision Quality", trend_label, TEXT2, trend_color,
                     "1st half vs 2nd half win rate" if trend else f"Need {_MIN_FOR_TREND}+ decisions", 0.12)
        + f'</div>'
    )
    findings = (
        f'<div style="padding:10px 14px;font-size:{FONT_LABEL};color:{TEXT2};">'
        + (f'<span style="color:{GAIN};font-weight:{WEIGHT_BOLD};">Strength:</span> {strength}<br>' if strength else "")
        + (f'<span style="color:{LOSS};font-weight:{WEIGHT_BOLD};">Weakness:</span> {weakness}<br>' if weakness else "")
        + (f'No sector stands out as a clear strength or weakness yet.'
           if not strength and not weakness else "")
        + f'</div>'
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("🧭", "Investment Intelligence Summary", f"Based on {n} completed decisions")}'
        f'{cards}{findings}'
        f'</div>'
    )


from dashboard.registry import ComponentSpec, RefreshGroup, register
register(ComponentSpec("decision_quality_out", RefreshGroup.SLOW, render_decision_quality_summary, priority=39))
