"""Shared rendering helpers for the Trust Ledger analytics panels
(trust_scorecard.py, phase2_preview.py) -- connect-and-refresh plumbing and
win-rate/return color thresholds used identically by both."""
from __future__ import annotations

import sqlite3

from loguru import logger

from dashboard.design_system import GAIN, LOSS, NEURAL

_logger = logger


def connect_ledger_or_none() -> sqlite3.Connection | None:
    """Shared connect-and-refresh for Trust Ledger-backed panels. Returns
    None on failure -- callers render an empty/awaiting state, same
    best-effort philosophy as decision_quality.py."""
    import ledger.db as ledger_db
    from bot.monitor.dashboard_data import refresh_db_from_hf
    from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH
    refresh_db_from_hf()
    try:
        return ledger_db.get_conn(DEFAULT_LEDGER_DB_PATH)
    except Exception as exc:
        _logger.warning(f"ledger_analytics connect: {exc}")
        return None


def rate_color(rate: float) -> str:
    return GAIN if rate >= 0.6 else (LOSS if rate < 0.45 else NEURAL)


def ret_color(ret: float) -> str:
    return GAIN if ret >= 0 else LOSS
