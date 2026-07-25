"""Trade and signal logging helpers."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from loguru import logger

from bot.strategy.ensemble import WEIGHTS


def log_trade(
    con: sqlite3.Connection,
    symbol: str,
    action: str,
    shares: float,
    price: float,
    notional: float,
    regime: str,
    portfolio_value: float,
    pnl_pct: float,
    xgb_prob: float = 0.0,
    lstm_prob: float = 0.0,
    sentiment_score: float = 0.0,
    macro_score: float = 0.0,
    entry_price: float = 0.0,
    order_id: str | None = None,
    holding_days: int = 0,
    feature_drivers: str | None = None,
    ai_reasoning: str | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    risk_reward_ratio: float | None = None,
) -> int | None:
    sentiment_norm = (sentiment_score + 1.0) / 2.0
    ensemble_score = (WEIGHTS["xgb"]  * xgb_prob + WEIGHTS["lstm"] * lstm_prob
                      + WEIGHTS["sentiment"] * sentiment_norm + WEIGHTS["macro"] * macro_score)
    realized_pnl = shares * (price - entry_price) if "SELL" in action and entry_price > 0 else 0.0
    cur = con.execute(
        """INSERT INTO trades
           (timestamp, symbol, action, shares, price, notional, regime, portfolio_value, pnl_pct,
            xgb_prob, lstm_prob, sentiment_score, macro_score, ensemble_score, realized_pnl,
            order_id, holding_days, feature_drivers, ai_reasoning, stop_loss, take_profit, risk_reward_ratio)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now(timezone.utc).isoformat(),
         symbol, action, shares, price, notional, regime, portfolio_value, pnl_pct,
         xgb_prob, lstm_prob, sentiment_score, macro_score, ensemble_score, realized_pnl,
         order_id, holding_days, feature_drivers, ai_reasoning, stop_loss, take_profit, risk_reward_ratio),
    )
    con.commit()
    return cur.lastrowid


def log_signal(
    con: sqlite3.Connection, symbol: str,
    xgb_prob: float, lstm_prob: float, sentiment_score: float,
    macro_score: float, regime: str, ensemble_action: str,
) -> None:
    """Record model output for every symbol evaluated each cycle (caller commits)."""
    sent_norm      = (sentiment_score + 1.0) / 2.0
    ensemble_score = (
        WEIGHTS["xgb"]       * xgb_prob +
        WEIGHTS["lstm"]      * lstm_prob +
        WEIGHTS["sentiment"] * sent_norm +
        WEIGHTS["macro"]     * macro_score
    )
    con.execute(
        "INSERT INTO signal_log "
        "(timestamp, symbol, xgb_prob, lstm_prob, sentiment_score, macro_score, "
        "ensemble_score, ensemble_action, regime) VALUES (?,?,?,?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), symbol,
         round(xgb_prob, 4), round(lstm_prob, 4), round(sentiment_score, 4),
         round(macro_score, 4), round(ensemble_score, 4), ensemble_action, regime),
    )


def log_recommendation(
    con: sqlite3.Connection,
    symbol: str,
    recommendation: str,
    confidence: float,
    price: float | None = None,
) -> None:
    """Upsert today's recommendation into trades.db (caller commits after batching)."""
    today = date.today().isoformat()
    now   = datetime.now(timezone.utc).isoformat()
    prev_row = con.execute(
        "SELECT recommendation FROM recommendations "
        "WHERE symbol = ? ORDER BY prediction_date DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    prev = prev_row[0] if prev_row else None
    con.execute(
        """INSERT INTO recommendations
               (symbol, prediction_date, recommendation, confidence,
                prev_recommendation, price_at_recommendation, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(symbol, prediction_date) DO UPDATE SET
               recommendation          = excluded.recommendation,
               confidence              = excluded.confidence,
               prev_recommendation     = excluded.prev_recommendation,
               price_at_recommendation = excluded.price_at_recommendation,
               created_at              = excluded.created_at""",
        (symbol, today, recommendation, round(confidence, 4), prev, price, now),
    )


def record_snapshot(
    con: sqlite3.Connection,
    portfolio_value: float,
    available_cash: float,
    open_positions: int,
) -> None:
    """Write a heartbeat portfolio snapshot for the dashboard (every cycle)."""
    con.execute(
        "INSERT OR REPLACE INTO portfolio_snapshots "
        "(timestamp, portfolio_value, available_cash, open_positions) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), portfolio_value, available_cash, open_positions),
    )
    con.commit()
    logger.info(
        f"Snapshot recorded — portfolio=${portfolio_value:,.2f}, cash=${available_cash:,.2f}, "
        f"open_positions={open_positions}"
    )
