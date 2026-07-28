"""Decision Intelligence Phase 1 glue for the per-symbol cycle — extracted from
bot/_main_cycle.py to keep that file under the project's 500-line limit."""
from __future__ import annotations

import sqlite3

from loguru import logger

import bot.monitor.telegram_bot as tg
from bot.execution.alpaca_client import AlpacaClient
from bot.strategy.ensemble import ensemble_confidence
from bot._main_positions import _TP_FLOOR, _upsert_position_state
from bot.capital.pool import CapitalPool, update_on_buy as _pool_buy
from bot._main_db import log_trade
from config import CASH_USE_FRACTION, STOP_LOSS_PCT
from database.trade_journal import open_entry as _journal_open
from database.services.decision_service import (
    create_decision, mark_executed, list_approved_unexecuted, expire_stale_decisions,
)

_logger = logger


def create_buy_decision(
    con: sqlite3.Connection, symbol: str, current_price: float, portfolio_value: float,
    signal_log_id: int | None, xgb_prob: float, lstm_prob: float,
    sentiment: float, macro_score: float, regime_name: str,
) -> int:
    """Record a decision the moment a symbol's ensemble signal says BUY, before
    any entry gate runs, so rejected/blocked candidates are captured too."""
    ens_conf = ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)
    return create_decision(
        con, symbol,
        price_at_decision=current_price,
        portfolio_value_at_time=portfolio_value,
        signal_log_id=signal_log_id,
        decision_reason=f"XGB {xgb_prob:.0%}, LSTM {lstm_prob:.0%}, regime={regime_name}",
        ai_confidence=int(round(ens_conf * 100)),
    )


def backfill_decisions_from_trades(con: sqlite3.Connection) -> int:
    """Commit 5 — one-time-per-trade backfill: create a fully-populated
    decision_log row for every historical BUY trade that predates this
    wiring (Commit 4) and doesn't already have one linked via trade_id.
    Idempotent (checked via trade_id) — safe to call on every bot startup,
    and self-healing if decision_log ever gets reset/recreated.

    Matches each BUY to its real closing SELL, if any, so Confidence
    Calibration has outcome history to work with immediately rather than
    waiting for 38 fresh trades. SELL_RECONCILE rows are treated as if they
    never happened when matching — per the 2026-07-07 corruption incident
    (see project_sell_reconcile_pollution memory), they recorded a
    transient bad broker read, not a real close, and trusting them here
    would mark still-open positions as closed with a fabricated outcome.

    Returns the number of decision_log rows created.
    """
    # A now-retired dashboard mechanism (dashboard/components/timeline.py's
    # _sync_from_trades(), removed) used to lazily backfill decision_log with
    # a narrower, unlinked format (no trade_id, decision_status always NULL)
    # whenever the Symbol Detail timeline was viewed — before this function
    # existed. Those rows are pure duplicates of what this function creates
    # properly linked; decision_status is NULL only ever for that legacy
    # format (every row this module writes always sets it), so it's a safe,
    # precise way to find and remove them before backfilling cleanly.
    _stale = con.execute(
        "DELETE FROM decision_log WHERE decision_status IS NULL"
    ).rowcount
    if _stale:
        _logger.info(f"Decision backfill: removed {_stale} stale rows from the retired timeline sync")

    already_linked = {
        r[0] for r in con.execute(
            "SELECT trade_id FROM decision_log WHERE trade_id IS NOT NULL"
        ).fetchall()
    }
    trades = con.execute(
        "SELECT id, symbol, timestamp, action, price, portfolio_value, "
        "ensemble_score, ai_reasoning, pnl_pct FROM trades ORDER BY symbol, timestamp"
    ).fetchall()

    open_buy: dict[str, tuple] = {}
    created = 0
    for tid, symbol, ts, action, price, pv, ens_score, reasoning, pnl_pct in trades:
        if action == "BUY":
            open_buy[symbol] = (tid, ts, price, pv, ens_score, reasoning)
        elif action == "SELL_RECONCILE":
            continue
        elif action.startswith("SELL"):
            buy = open_buy.pop(symbol, None)
            if buy is None or buy[0] in already_linked:
                continue
            _insert_backfilled_decision(con, symbol, buy, outcome_pct=pnl_pct, outcome_known_at=ts)
            created += 1

    for symbol, buy in open_buy.items():
        if buy[0] in already_linked:
            continue
        _insert_backfilled_decision(con, symbol, buy)
        created += 1

    if created:
        con.commit()
        _logger.info(f"Decision backfill: created {created} decision_log rows from historical trades")
    return created


def _insert_backfilled_decision(
    con: sqlite3.Connection, symbol: str, buy: tuple,
    outcome_pct: float | None = None, outcome_known_at: str | None = None,
) -> None:
    trade_id, ts, price, portfolio_value, ens_score, reasoning = buy
    outcome_status = "UNKNOWN"
    if outcome_pct is not None:
        outcome_status = "WIN" if outcome_pct > 0 else ("LOSS" if outcome_pct < 0 else "NEUTRAL")
    con.execute(
        """INSERT INTO decision_log
           (symbol, decision_date, decision_type, price_at_decision, reasoning,
            ai_confidence, portfolio_value_at_time, triggered_by, created_at,
            trade_id, decision_source, decision_reason,
            decision_status, execution_status, outcome_status,
            executed_at, outcome_known_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (symbol, str(ts)[:10] if ts else None, "BUY", price, reasoning,
         int(round(float(ens_score or 0) * 100)), portfolio_value, "ai", ts,
         trade_id, "AI_SIGNAL", reasoning,
         "APPROVED", "EXECUTED", outcome_status, ts, outcome_known_at),
    )


def execute_approved_decisions(
    con: sqlite3.Connection, client: AlpacaClient, positions: dict,
    available_cash: float, portfolio_value: float,
    buy_order_syms: set, pool: CapitalPool | None = None,
) -> float:
    """Supervised-mode resumption: place the real order for any BUY a human
    has approved since the entry-gate pipeline last saw that symbol.

    Deliberately decoupled from _handle_entry() and called once per cycle
    (not per-symbol) — a symbol's live signal can weaken or disappear
    entirely between when a human clicks approve and the bot's next cycle,
    so gating this on that cycle's action==1 (as _handle_entry() is) would
    silently never resume it. Replays the notional/stop/TP/RR values
    _handle_entry() already computed and stored via mark_waiting_approval()
    rather than recomputing Kelly sizing or ATR stops against a possibly
    very different market by the time a human acts — only the cash-reserve
    check and current price are re-verified, at execution time.
    """
    expired = expire_stale_decisions(con)
    if expired:
        _logger.info(f"Supervised resumption: expired {expired} stale decision(s) from a prior day")

    for row in list_approved_unexecuted(con):
        symbol = row["symbol"]
        if symbol in positions or symbol in buy_order_syms:
            _logger.info(f"Supervised resumption: {symbol} already held/pending — skipping approved decision")
            continue
        notional = row["suggested_notional"]
        if not notional or notional <= 0:
            _logger.warning(f"Supervised resumption: {symbol} has no valid suggested_notional — skipping")
            continue
        if notional > available_cash * CASH_USE_FRACTION:
            _logger.info(f"Supervised resumption: {symbol} skipped — cash reserve would be breached "
                        f"(need ${notional:.2f}, cash ${available_cash:.2f})")
            continue
        try:
            current_price = client.get_latest_price(symbol)
        except Exception as exc:
            _logger.warning(f"Supervised resumption: {symbol} price fetch failed: {exc}")
            continue
        if not current_price or current_price <= 0:
            continue

        result = client.buy(symbol, notional, limit_price=current_price)
        if not result:
            _logger.warning(f"Supervised resumption: {symbol} buy order not placed")
            continue
        filled_qty = client.wait_for_fill(result["order_id"], timeout_secs=15)
        if filled_qty <= 0:
            _logger.warning(f"Supervised resumption: {symbol} order did not fill")
            continue

        fill_price = client.get_fill_price(result["order_id"]) or current_price
        fill_shares = notional / fill_price
        stop_pct = row["suggested_stop_loss"] or STOP_LOSS_PCT
        tp_pct   = row["suggested_take_profit"] or _TP_FLOOR
        rr_ratio = row["suggested_rr_ratio"] or (tp_pct / stop_pct if stop_pct else 0.0)
        _ai_rsn = f"Bought {symbol} at ${fill_price:.2f} (human-approved, supervised mode)."

        trade_id = log_trade(con, symbol, "BUY", fill_shares, fill_price, notional,
                             "SUPERVISED", portfolio_value, 0,
                             order_id=result.get("order_id"), ai_reasoning=_ai_rsn,
                             stop_loss=round(fill_price * (1 - stop_pct), 4),
                             take_profit=round(fill_price * (1 + tp_pct), 4),
                             risk_reward_ratio=round(rr_ratio, 4))
        mark_executed(con, row["decision_id"], trade_id=trade_id, quantity_changed=fill_shares)
        try:
            _journal_open(con, symbol, trade_id, entry_reason=_ai_rsn,
                          entry_signals={"mode": "SUPERVISED", "stop_pct": round(stop_pct, 4),
                                        "tp_pct": round(tp_pct, 4), "rr_ratio": round(rr_ratio, 3)},
                          entry_confidence=0.0, pattern_tags=["SUPERVISED"])
        except Exception as exc:
            _logger.warning(f"Journal open failed for {symbol} (non-fatal): {exc}")
        if pool:
            _pool_buy(con, pool.id, notional, symbol=symbol)
        tg.alert_buy(symbol, fill_shares, fill_price, "SUPERVISED", portfolio_value, 0.0,
                    notional=notional)
        _upsert_position_state(con, symbol, fill_price, fill_price, 0.0, fill_shares)
        available_cash -= notional
        _logger.info(f"Supervised resumption: {symbol} EXECUTED — decision [{row['decision_id']}] -> trade [{trade_id}]")

    return available_cash
