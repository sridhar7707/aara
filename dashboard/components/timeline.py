"""Decision Timeline — chronological log of every decision per position (req 11.6)."""
from __future__ import annotations
import datetime
import json
from loguru import logger
from dashboard.design_system import (
    SURFACE, SURFACE2, BORDER, TEXT1, TEXT2, TEXT3,
    ACTION_BUY, ACTION_SELL, ACTION_TRIM, ACTION_HOLD, ACTION_WATCH,
    GAIN, LOSS, NEURAL, PRIMARY,
    FONT_SECTION, FONT_VALUE, FONT_LABEL, WEIGHT_BOLD,
    _section, _wrap, _card, _empty_state,
    _sym,
)
from bot.core.error_logger import safe_render, timed

_logger = logger

_TYPE_COLORS = {
    "buy":    GAIN,
    "add":    GAIN,
    "trim":   "#f59e0b",
    "sell":   LOSS,
    "review": NEURAL,
    "hold":   TEXT2,
}

_TYPE_ICONS = {
    "buy": "●", "add": "●", "trim": "◑",
    "sell": "○", "review": "◇", "hold": "·",
}


def _load_timeline(symbol: str) -> list[dict]:
    """Reads the Trust Ledger (decision_events) -- decision_log is retired
    per phase0_decisions.md #17/#18, same migration already applied to
    decision_quality.py/counterfactual.py. Only EXECUTED BUY/SELL rows are
    shown: QUALIFIED_REJECTION doesn't change the position, and would flood
    a single symbol's timeline every cycle it's evaluated but not acted on."""
    import ledger.db as ledger_db
    from bot.monitor.dashboard_data import refresh_db_from_hf
    from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH
    refresh_db_from_hf()
    try:
        conn = ledger_db.get_conn(DEFAULT_LEDGER_DB_PATH)
    except Exception as exc:
        _logger.warning(f"timeline ledger connect: {exc}")
        return []
    try:
        rows = conn.execute(
            "SELECT timestamp, action, portfolio_snapshot, risk_checks, "
            "final_confidence, intent FROM decision_events "
            "WHERE asset=? AND event_type='EXECUTED' AND action IN ('BUY','SELL') "
            "ORDER BY timestamp ASC",
            (symbol,)
        ).fetchall()
    except Exception as exc:
        _logger.warning(f"timeline read: {exc}")
        return []
    finally:
        conn.close()

    entries = []
    for timestamp, action, portfolio_snapshot, risk_checks, final_confidence, intent in rows:
        ps = json.loads(portfolio_snapshot)
        rc = json.loads(risk_checks)
        it = json.loads(intent)
        if action == "BUY":
            price, qty = rc.get("fill_price"), rc.get("fill_shares")
            reasoning = it.get("thesis") or "—"
        else:  # SELL -- share count isn't recorded on the exit event today
            price, qty = ps.get("current_price"), None
            reasoning = rc.get("exit_reason") or "—"
        entries.append({
            "decision_date": str(timestamp)[:10],
            "decision_type": action.lower(),
            "price_at_decision": price,
            "quantity_changed": qty,
            "reasoning": reasoning,
            "ai_confidence": round(final_confidence * 100) if final_confidence is not None else None,
            "portfolio_value_at_time": ps.get("portfolio_value"),
            "triggered_by": "ai",
        })
    return entries


def render_decision_timeline(symbol: str | None = None) -> str:
    """Render decision timeline for a single symbol."""
    if not symbol:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("⏱", "Decision Timeline", "Full history per position")}'
            f'{_card(_empty_state("⏱", "Select a symbol", "Choose a symbol to view its decision timeline."))}'
            f'</div>'
        )
    entries = _load_timeline(symbol)

    if not entries:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("⏱", "Decision Timeline", symbol)}'
            f'{_card(_empty_state("⏱", f"No history for {symbol}", "History will appear after trades are logged."))}'
            f'</div>'
        )

    # Calculate total return for closed positions
    buy_prices: list[float]  = [e["price_at_decision"] or 0.0 for e in entries if e["decision_type"] == "buy"]
    sell_prices: list[float] = [e["price_at_decision"] or 0.0 for e in entries if e["decision_type"] == "sell"]
    total_return_str = ""
    first_entry_date = entries[0]["decision_date"]
    last_exit_date   = None
    if buy_prices and sell_prices:
        avg_buy  = sum(buy_prices)  / len(buy_prices)
        avg_sell = sum(sell_prices) / len(sell_prices)
        ret = (avg_sell - avg_buy) / avg_buy * 100 if avg_buy > 0 else 0.0
        ret_c = GAIN if ret >= 0 else LOSS
        last_exit_date = max(e["decision_date"] for e in entries if e["decision_type"] == "sell")
        try:
            d0 = datetime.date.fromisoformat(first_entry_date)
            d1 = datetime.date.fromisoformat(last_exit_date)
            hold_days = (d1 - d0).days
        except Exception:
            hold_days = 0
        total_return_str = (
            f'<div style="background:{ret_c}11;border:1px solid {ret_c}44;border-radius:6px;'
            f'padding:10px 14px;margin-top:12px;display:flex;gap:20px;flex-wrap:wrap;">'
            f'<span style="font-size:{FONT_LABEL};color:{TEXT2};">Total Return</span>'
            f'<span style="font-weight:{WEIGHT_BOLD};color:{ret_c};font-size:{FONT_VALUE};">'
            f'{ret:+.1f}%</span>'
            f'<span style="font-size:{FONT_LABEL};color:{TEXT2};">Holding Period</span>'
            f'<span style="font-weight:{WEIGHT_BOLD};color:{TEXT1};">{hold_days} days</span>'
            f'</div>'
        )

    # Timeline entries
    items_html = ""
    for entry in entries:
        dtype   = entry["decision_type"] or "review"
        color   = _TYPE_COLORS.get(dtype, TEXT2)
        icon    = _TYPE_ICONS.get(dtype, "·")
        date_s  = entry["decision_date"] or "—"
        price   = entry["price_at_decision"]
        qty     = entry["quantity_changed"]
        reason  = entry["reasoning"] or "—"
        conf    = entry["ai_confidence"]
        by_who  = entry["triggered_by"] or "ai"

        price_str = f"@ ${price:.2f}" if price else ""
        qty_str   = f"  {qty:+.2f} shares" if qty else ""
        conf_str  = f"  · {conf}% confidence" if conf else ""
        by_str    = f"  · {by_who}" if by_who not in ("ai", "") else ""

        items_html += (
            f'<div style="display:flex;gap:14px;padding:10px 0;'
            f'border-bottom:1px solid {BORDER};">'
            f'<div style="flex:0 0 90px;font-size:{FONT_LABEL};color:{TEXT2};">{date_s}</div>'
            f'<div style="flex:0 0 12px;color:{color};font-size:18px;line-height:1;'
            f'margin-top:1px;">{icon}</div>'
            f'<div style="flex:1;">'
            f'<div style="font-weight:{WEIGHT_BOLD};color:{color};'
            f'text-transform:capitalize;font-size:{FONT_LABEL};">'
            f'{dtype.title()} {price_str}{qty_str}</div>'
            f'<div style="font-size:{FONT_LABEL};color:{TEXT2};margin-top:2px;line-height:1.5;">'
            f'&#8220;{reason}&#8221;'
            f'<span style="color:{TEXT3};">{conf_str}{by_str}</span></div>'
            f'</div>'
            f'</div>'
        )

    body = items_html + total_return_str
    inner = _wrap(f'<div style="max-height:480px;overflow-y:auto;">{body}</div>')
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("⏱", "Decision Timeline", symbol)}'
        f'{inner}'
        f'</div>'
    )


@timed(_logger)
@safe_render("Decision Timeline")
def render_all_timelines() -> str:
    """Overview: all symbols with decision history, most recent first.

    Reads the Trust Ledger (decision_events) -- see _load_timeline's
    docstring for why decision_log is retired and EXECUTED-only is correct."""
    import ledger.db as ledger_db
    from bot.monitor.dashboard_data import refresh_db_from_hf
    from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH
    refresh_db_from_hf()
    try:
        conn = ledger_db.get_conn(DEFAULT_LEDGER_DB_PATH)
    except Exception as exc:
        _logger.warning(f"timeline ledger connect: {exc}")
        conn = None
    rows = []
    if conn is not None:
        try:
            rows = conn.execute(
                "SELECT asset, MAX(timestamp) AS last_ts, COUNT(*) AS n_decisions "
                "FROM decision_events WHERE event_type='EXECUTED' AND action IN ('BUY','SELL') "
                "GROUP BY asset ORDER BY last_ts DESC LIMIT 20"
            ).fetchall()
        except Exception as exc:
            _logger.warning(f"timeline read: {exc}")
        finally:
            conn.close()
    rows = [(sym, str(last_ts)[:10], n) for sym, last_ts, n in rows]

    if not rows:
        return (f'<div class="nt nt-wrap">'
                f'{_section("⏱", "Decision Timeline", "All positions")}'
                f'{_card(_empty_state("⏱", "No decisions logged yet", ""))}'
                f'</div>')

    items_html = ""
    for sym, last_date, n in rows:
        items_html += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:8px 14px;border-bottom:1px solid {BORDER};">'
            f'<span style="font-family:Courier New,monospace;font-weight:700;color:{TEXT1};">'
            f'{sym}</span>'
            f'<span style="font-size:{FONT_LABEL};color:{TEXT2};">'
            f'{n} decision{"s" if n != 1 else ""}</span>'
            f'<span style="font-size:{FONT_LABEL};color:{TEXT3};">Last: {last_date}</span>'
            f'</div>'
        )
    note = f"{len(rows)} symbol{'s' if len(rows) != 1 else ''} with decision history"
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("⏱", "Decision Timeline", note)}'
        f'{_wrap(items_html)}'
        f'</div>'
    )


from dashboard.registry import ComponentSpec, RefreshGroup, register
register(ComponentSpec("timeline_brief_out",  RefreshGroup.FAST, render_all_timelines, priority=60))
