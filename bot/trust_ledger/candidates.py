"""Phase 1A Sprint 2 -- candidate_evaluation_events writer.

Written exactly once per (symbol, trading day), per phase1a_requirements.md
Section 4.1: "written exactly once, after the evaluation pipeline concludes
-- never at request time with an intent to update later." Whichever
evaluation concludes first for a symbol that day (success or the
5th-consecutive-failure threshold) is final for the day; a later cycle's
result is not written on top of it.

The write-once check is DB-backed, not purely in-memory: bot/main.py's own
docstring says it "runs every 5 minutes via GitHub Actions" -- i.e. each
cycle may be a fresh process, so a module-level in-memory cache alone
(matching the existing _sym_errors pattern) cannot be trusted to survive a
restart. The in-memory cache here is a same-process fast path only.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import ledger.ledger as ledger_svc
from bot.trust_ledger.ids import new_candidate_event_id

SCREENING_VERSION = "screen_universe_v1"

_recorded_today: dict[tuple[str, str], str] = {}
_recorded_date: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reset_if_new_day(trading_day: str) -> None:
    global _recorded_date
    if _recorded_date != trading_day:
        _recorded_today.clear()
        _recorded_date = trading_day


def _build_screening_results(symbol: str, universe_payload: dict) -> dict:
    """universe_payload is data/universe_today.json's parsed content (see
    bot/_main_market.py::_load_today_universe) -- picks already carry
    rank/composite_score/sector/etc, no new plumbing needed."""
    for pick in universe_payload.get("picks") or []:
        if pick.get("symbol") == symbol:
            return {
                "rank": pick.get("rank"),
                "composite_score": pick.get("composite_score"),
                "analyst_signal": pick.get("analyst_signal"),
                "etf_momentum": pick.get("etf_momentum"),
                "regime": pick.get("regime"),
                "sector": pick.get("sector"),
            }
    # Symbol not found in today's screener picks (e.g. universe file missing/
    # stale, falling back to config.SYMBOLS per _load_today_universe) --
    # still a legitimate candidate, just without screener factor scores.
    return {"note": "no screener pick data available for this symbol today"}


def record_candidate_evaluation_if_concluded(
    conn: sqlite3.Connection,
    symbol: str,
    trading_day: str,
    universe_payload: dict,
    data_available: bool,
    required_models_available: bool,
    evaluation_completed: bool,
) -> dict | None:
    """Write a candidate_evaluation_events row for (symbol, trading_day) if
    one doesn't already exist. Returns the appended row, or None if this
    (symbol, trading_day) already has a concluded evaluation on record."""
    _reset_if_new_day(trading_day)
    key = (symbol, trading_day)
    if key in _recorded_today:
        return None

    existing = conn.execute(
        "SELECT candidate_event_id FROM candidate_evaluation_events "
        "WHERE asset=? AND timestamp LIKE ? ORDER BY sequence_number DESC LIMIT 1",
        (symbol, f"{trading_day}%"),
    ).fetchone()
    if existing:
        _recorded_today[key] = existing[0]
        return None

    row = ledger_svc.append_ledger_row(conn, "candidate_evaluation_events", {
        "candidate_event_id": new_candidate_event_id(symbol),
        "timestamp": _utc_now(),
        "asset": symbol,
        "screening_version": SCREENING_VERSION,
        "screening_results": _build_screening_results(symbol, universe_payload),
        "data_available": data_available,
        "required_models_available": required_models_available,
        "evaluation_requested": True,
        "evaluation_completed": evaluation_completed,
    })
    _recorded_today[key] = row["candidate_event_id"]
    return row


def get_todays_candidate_event_id(conn: sqlite3.Connection, symbol: str, trading_day: str) -> str | None:
    """Look up the (symbol, trading_day) candidate_event_id regardless of
    whether this process wrote it or a fresh process wrote it earlier today
    -- decision-writing code (Sprint 3) needs this every time it creates a
    decision_events row, decoupled from whether record_candidate_evaluation_
    if_concluded happened to be called in the same function call."""
    _reset_if_new_day(trading_day)
    key = (symbol, trading_day)
    if key in _recorded_today:
        return _recorded_today[key]
    row = conn.execute(
        "SELECT candidate_event_id FROM candidate_evaluation_events "
        "WHERE asset=? AND timestamp LIKE ? ORDER BY sequence_number DESC LIMIT 1",
        (symbol, f"{trading_day}%"),
    ).fetchone()
    if row:
        _recorded_today[key] = row[0]
        return row[0]
    return None
