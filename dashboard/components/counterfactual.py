"""Counterfactual Analysis — Phase 5 Step 12 of the Decision Intelligence roadmap.

Answers "what happened to the ones we passed on?" for every gate-blocked
decision. Reads the Trust Ledger, not the retired decision_log (phase0_
decisions.md #17/#18). Evidence-gated like Decision Quality / Loss
Explanation / Investor Profile — reports "not enough data" rather than a
verdict below the threshold, and never judges a rejection before its
outcome window has actually closed (_evaluate_rejection() enforces that
itself).
"""
from __future__ import annotations

import datetime
import json

from loguru import logger

from bot.core.error_logger import safe_render, timed
from dashboard.design_system import (
    GAIN, LOSS, TEXT2, TEXT3,
    FONT_LABEL, WEIGHT_BOLD,
    _section, _empty_state, _card, _stat_card,
)
from database.services.decision_service import _forward_return

_logger = logger

_MIN_EVALUATED_FOR_INSIGHTS = 15  # matches the ~15-20 evidence-gate threshold used elsewhere in Phase 3/5
_MIN_PER_GATE_REASON        = 3   # a gate needs at least this many evaluated misses to call out its hit rate
_MAX_CANDIDATES_PER_RENDER  = 30  # bounds yfinance calls per refresh (RefreshGroup.SLOW, every 5 min)
_DEFAULT_WINDOW_DAYS        = 10  # the ledger doesn't carry an expected_holding_period like decision_log did


def _rejected_decisions(limit: int) -> list[dict]:
    """Gate-blocked entries (action=REJECT, event_type=QUALIFIED_REJECTION),
    most recent first. Reads the Trust Ledger — decision_log is retired per
    phase0_decisions.md #17/#18. gate_reason is the last failing gate in the
    decision's risk_checks.gate_trace (EntryDecisionRecorder.reject() writes
    exactly one)."""
    import ledger.db as ledger_db
    from bot.monitor.dashboard_data import refresh_db_from_hf
    from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH
    # Unlike trades.db (pulled by every _con() call), nothing else guarantees
    # trust_ledger.db exists locally before this runs -- on the Space it's
    # only pulled here, on demand (Space-only no-op locally/in CI, see
    # refresh_db_from_hf's SPACE_ID gate).
    refresh_db_from_hf()
    try:
        conn = ledger_db.get_conn(DEFAULT_LEDGER_DB_PATH)
    except Exception as exc:
        _logger.warning(f"counterfactual ledger connect: {exc}")
        return []
    try:
        rows = conn.execute(
            "SELECT decision_id, asset, timestamp, risk_checks FROM decision_events "
            "WHERE action='REJECT' AND event_type='QUALIFIED_REJECTION' "
            "ORDER BY sequence_number DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except Exception as exc:
        _logger.warning(f"counterfactual read: {exc}")
        return []
    finally:
        conn.close()

    results = []
    for decision_id, symbol, timestamp, risk_checks_json in rows:
        gate_reason = None
        try:
            trace = json.loads(risk_checks_json).get("gate_trace") or []
            failing = [t for t in trace if not t.get("passed", True)]
            if failing:
                gate_reason = failing[-1].get("gate")
        except (TypeError, json.JSONDecodeError) as exc:
            _logger.debug(f"counterfactual gate_trace parse ({decision_id}): {exc}")
        results.append({"decision_id": decision_id, "symbol": symbol,
                         "decision_date": timestamp, "gate_reason": gate_reason})
    return results


def _evaluate_rejection(symbol: str, decision_date: str) -> dict:
    """What actually happened to the symbol afterward — read-only, fixed
    default window (see _DEFAULT_WINDOW_DAYS). None if the window hasn't
    closed yet or price history isn't available — never a partial/
    in-progress return, matching the project's standing rule that outcomes
    aren't judged before their window closes."""
    try:
        start_date = datetime.datetime.fromisoformat(str(decision_date)[:10]).date()
    except (TypeError, ValueError):
        return {"forward_return": None}
    target_end = start_date + datetime.timedelta(days=_DEFAULT_WINDOW_DAYS)
    if target_end > datetime.datetime.now(datetime.timezone.utc).date():
        return {"forward_return": None}
    return {"forward_return": _forward_return(symbol, start_date, target_end)}


def _evaluated_rejections() -> list[dict]:
    """Rejected/blocked decisions whose outcome window has closed, with a
    known forward_return. Still-pending-window and data-unavailable rows are
    silently excluded here (not an error — just not evaluable yet)."""
    candidates = _rejected_decisions(limit=_MAX_CANDIDATES_PER_RENDER)
    results = []
    for c in candidates:
        r = _evaluate_rejection(c["symbol"], c["decision_date"])
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
