"""Decision Intelligence Phase 1 glue for the per-symbol cycle — extracted from
bot/_main_cycle.py to keep that file under the project's 500-line limit."""
from __future__ import annotations

import sqlite3

from bot.strategy.ensemble import WEIGHTS
from database.services.decision_service import create_decision


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
