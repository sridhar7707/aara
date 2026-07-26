"""Decision Intelligence Phase 1 glue for the per-symbol cycle — extracted from
bot/_main_cycle.py to keep that file under the project's 500-line limit."""
from __future__ import annotations

import sqlite3

from loguru import logger

from bot.strategy.ensemble import WEIGHTS
from database.services.decision_service import create_decision

_logger = logger


def create_buy_decision(
    con: sqlite3.Connection, symbol: str, current_price: float, portfolio_value: float,
    signal_log_id: int | None, xgb_prob: float, lstm_prob: float,
    sentiment: float, macro_score: float, regime_name: str,
) -> int:
    """Record a decision the moment a symbol's ensemble signal says BUY, before
    any entry gate runs, so rejected/blocked candidates are captured too."""
    ens_conf = (
        WEIGHTS["xgb"]       * xgb_prob +
        WEIGHTS["lstm"]      * lstm_prob +
        WEIGHTS["sentiment"] * ((sentiment + 1.0) / 2.0) +
        WEIGHTS["macro"]     * macro_score
    )
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
