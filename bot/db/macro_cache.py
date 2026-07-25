"""Macro-score DB cache: fetch from FRED/yfinance, persist to macro_cache table."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

from loguru import logger

import bot.monitor.telegram_bot as tg
from bot.strategy.macro import _get_cached as _get_macro_cached

_TTL = 4 * 3600  # 4-hour cache for macro data


def get_macro(con: sqlite3.Connection) -> tuple[float, float, bool]:
    """Return (score, cap, halt). halt=True means VIX >= MACRO_HALT_VIX."""
    now  = time.time()
    rows = {r[0]: (float(r[1]), r[2])
            for r in con.execute("SELECT key, value, cached_at FROM macro_cache")}
    if "score" in rows and "cap" in rows:
        try:
            cached_ts = datetime.fromisoformat(rows["score"][1]).timestamp()
            if now - cached_ts < _TTL:
                halt = bool(rows["halt"][0]) if "halt" in rows else False
                return rows["score"][0], rows["cap"][0], halt
        except (ValueError, TypeError):
            pass
    try:
        result = _get_macro_cached()
    except Exception as e:
        logger.warning(f"Macro fetch failed — using neutral defaults: {e}")
        result = {"score": 0.5, "cap": 1.0, "halt": False}
        tg.send(
            f"⚠️ <b>FRED macro data unavailable</b> — {e}\n"
            "VIX/yield-curve circuit breaker is disabled. Market halt protection off."
        )
    ts = datetime.now(timezone.utc).isoformat()
    for key in ("score", "cap", "halt"):
        con.execute(
            "INSERT OR REPLACE INTO macro_cache (key, value, cached_at) VALUES (?,?,?)",
            (key, float(result[key]), ts),
        )
    con.commit()
    return result["score"], result["cap"], bool(result["halt"])
