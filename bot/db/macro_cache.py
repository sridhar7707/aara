"""Macro-score DB cache: fetch from FRED/yfinance, persist to macro_cache table."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

from loguru import logger

import bot.monitor.telegram_bot as tg
from bot.strategy.macro import _get_cached as _get_macro_cached

_TTL = 4 * 3600  # 4-hour cache for macro data

# Observational halt-reason metadata (Amendment 1 to ADR-010). A separate row
# in the same macro_cache key/value table, distinct from score/cap/halt, so
# downstream presentation/notification consumers (bot/_main_prep.py,
# bot/monitor/_dashboard_overview.py) can tell a genuine VIX threshold halt
# apart from a FRED/macro data-unavailable halt. This row is written on every
# evaluation attempt below but is never read by this function's own
# freshness/refresh-due check (which keys off "score"'s cached_at only), so
# it has zero influence on TTL/refresh behavior and cannot reproduce the
# "stale value looks fresh" defect ADR-010 closed.
HALT_REASON_KEY = "halt_reason"
REASON_NONE = 0             # halt=False; no BUY-blocking macro condition
REASON_VIX_THRESHOLD = 1    # halt=True; genuine VIX >= MACRO_HALT_VIX
REASON_DATA_UNAVAILABLE = 2 # halt=True; FRED/macro data unavailable (fail-closed)


def _write_halt_reason(con: sqlite3.Connection, reason: int) -> None:
    """Record observational halt-reason metadata only — does not commit and
    does not touch score/cap/halt. Caller commits alongside its own writes.
    """
    con.execute(
        "INSERT OR REPLACE INTO macro_cache (key, value, cached_at) VALUES (?,?,?)",
        (HALT_REASON_KEY, float(reason), datetime.now(timezone.utc).isoformat()),
    )


def get_macro_halt_reason(con: sqlite3.Connection) -> int | None:
    """Observational metadata only (Amendment 1 to ADR-010): the halt reason
    from the most recent evaluation attempt (REASON_NONE/VIX_THRESHOLD/
    DATA_UNAVAILABLE), or None if no evaluation has ever been recorded (true
    cold start). Never influences get_macro()'s TTL/refresh-due decision.
    """
    row = con.execute(
        "SELECT value FROM macro_cache WHERE key = ?", (HALT_REASON_KEY,)
    ).fetchone()
    return int(row[0]) if row else None


def get_macro(con: sqlite3.Connection) -> tuple[float, float, bool]:
    """Return (score, cap, halt). halt=True means VIX >= MACRO_HALT_VIX,
    OR macro data is unavailable (no valid within-TTL cache and the due
    refresh attempt failed) — both cases must block BUY eligibility, so
    both surface as halt=True to the existing, unmodified Gate 0 check.

    Use get_macro_halt_reason() to distinguish the two halt=True causes;
    this function's return signature is unchanged by that addition.
    """
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
        # force_refresh=True: this branch only runs once our own SQLite TTL
        # has decided a refresh is due — that decision is authoritative, so
        # _get_cached() must not silently satisfy it from a still-valid
        # in-process value without actually consulting FRED.
        result = _get_macro_cached(force_refresh=True)
    except Exception as e:
        logger.warning(f"FRED macro data unavailable — blocking BUY eligibility: {e}")
        tg.send(
            f"⚠️ <b>FRED macro data unavailable</b> — {e}\n"
            "No valid macro data — BUY eligibility blocked until FRED recovers."
        )
        # Do not persist the score/cap/halt failure state: writing those with
        # a fresh cached_at would make the next read treat them as a valid
        # within-TTL cache, masking the outage for up to 4 more hours. The
        # halt-reason row below is a separate, non-TTL-checked key — see the
        # module docstring above — and does not carry this risk.
        _write_halt_reason(con, REASON_DATA_UNAVAILABLE)
        con.commit()
        return 0.5, 1.0, True
    ts = datetime.now(timezone.utc).isoformat()
    for key in ("score", "cap", "halt"):
        con.execute(
            "INSERT OR REPLACE INTO macro_cache (key, value, cached_at) VALUES (?,?,?)",
            (key, float(result[key]), ts),
        )
    _write_halt_reason(con, REASON_VIX_THRESHOLD if result["halt"] else REASON_NONE)
    con.commit()
    return result["score"], result["cap"], bool(result["halt"])
