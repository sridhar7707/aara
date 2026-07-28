"""Trust Ledger candidate-evaluation write helper, extracted from bot/main.py
to keep it under the project's 500-line limit (matches the existing
bot/_main_*.py extraction pattern used throughout this file).

Best-effort by design: the Trust Ledger is an audit system, not a trading
gate -- a write failure here must never propagate and block the primary
pipeline (signal logging, entry gates) that runs after it in bot/main.py.
"""
from __future__ import annotations

import sqlite3

from loguru import logger

from bot.trust_ledger.candidates import record_candidate_evaluation_if_concluded


def record_candidate_safe(
    trust_conn: sqlite3.Connection, symbol: str, today_str: str, universe_payload: dict,
    data_available: bool, required_models_available: bool, evaluation_completed: bool,
) -> None:
    try:
        record_candidate_evaluation_if_concluded(
            trust_conn, symbol, today_str, universe_payload,
            data_available=data_available,
            required_models_available=required_models_available,
            evaluation_completed=evaluation_completed,
        )
    except Exception as e:
        logger.warning(f"trust ledger candidate write failed for {symbol}: {e}")
