"""Trade journal: records entry context at BUY time and closes with outcome at SELL time."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from loguru import logger


def _ensure_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS trade_journal (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol           TEXT NOT NULL,
            buy_trade_id     INTEGER,
            sell_trade_id    INTEGER,
            entry_reason     TEXT,
            entry_signals    TEXT,
            entry_confidence REAL,
            exit_reason      TEXT,
            outcome_pct      REAL,
            holding_days     INTEGER,
            lesson           TEXT,
            pattern_tags     TEXT,
            created_at       TEXT DEFAULT (datetime('now')),
            closed_at        TEXT
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_tj_symbol ON trade_journal(symbol)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tj_closed ON trade_journal(closed_at)")
    con.commit()


def open_entry(
    con: sqlite3.Connection,
    symbol: str,
    buy_trade_id: int | None,
    entry_reason: str,
    entry_signals: dict,
    entry_confidence: float,
    pattern_tags: list[str],
) -> int:
    """Record a new open journal entry at BUY time. Returns the journal row id."""
    _ensure_table(con)
    cur = con.execute(
        """INSERT INTO trade_journal
           (symbol, buy_trade_id, entry_reason, entry_signals, entry_confidence, pattern_tags)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (symbol, buy_trade_id, entry_reason,
         json.dumps(entry_signals, default=float),
         entry_confidence,
         json.dumps(pattern_tags)),
    )
    con.commit()
    jid = cur.lastrowid
    logger.debug(f"Journal open [{jid}] {symbol}: confidence={entry_confidence:.0%}")
    return jid


def close_entry(
    con: sqlite3.Connection,
    symbol: str,
    sell_trade_id: int | None,
    exit_reason: str,
    outcome_pct: float,
    holding_days: int,
) -> None:
    """Close the most-recent open journal entry for symbol at SELL time."""
    _ensure_table(con)
    lesson = _auto_lesson(exit_reason, outcome_pct, holding_days)
    closed_at = datetime.now(timezone.utc).isoformat()
    row = con.execute(
        "SELECT id FROM trade_journal WHERE symbol=? AND closed_at IS NULL ORDER BY id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    if row:
        con.execute(
            """UPDATE trade_journal
               SET sell_trade_id=?, exit_reason=?, outcome_pct=?, holding_days=?,
                   lesson=?, closed_at=?
               WHERE id=?""",
            (sell_trade_id, exit_reason, outcome_pct, holding_days, lesson, closed_at, row[0]),
        )
        logger.debug(f"Journal close [{row[0]}] {symbol}: {exit_reason} {outcome_pct:+.1%}")
    elif sell_trade_id is not None and con.execute(
        "SELECT 1 FROM trade_journal WHERE sell_trade_id=? LIMIT 1", (sell_trade_id,)
    ).fetchone():
        # Idempotency: same sell already journaled (retry scenario)
        logger.debug(f"Journal close {symbol}: sell_trade_id={sell_trade_id} already recorded, skipping")
        return
    else:
        con.execute(
            """INSERT INTO trade_journal
               (symbol, sell_trade_id, exit_reason, outcome_pct, holding_days, lesson, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (symbol, sell_trade_id, exit_reason, outcome_pct, holding_days, lesson, closed_at),
        )
        logger.debug(f"Journal orphan-close {symbol}: no open entry found, created closed record")
    con.commit()


def _auto_lesson(exit_reason: str, outcome_pct: float, holding_days: int) -> str:
    if exit_reason == "take-profit":
        return "Take-profit reached — entry setup worked as planned."
    if exit_reason == "gap-down":
        return "Gap-down hard floor hit — position market-sold immediately to prevent deeper loss."
    if exit_reason == "reconcile":
        return "Position closed externally (manually or by broker) — not an automated exit."
    if exit_reason in ("stop-loss", "STOP"):
        if holding_days <= 2:
            return "Stopped out quickly — entry timing may have been premature."
        if holding_days >= 14:
            return "Long hold then stopped out — thesis did not materialize in time."
        return "Stop-loss triggered — position moved against the signal."
    if exit_reason == "trailing-stop":
        if outcome_pct > 0:
            return "Trailing stop captured a gain — position peaked and reversed."
        return "Trailing stop with a loss — exit was timely given the reversal."
    if exit_reason == "time-exit":
        if outcome_pct > 0:
            return "Time exit with a gain — could have held longer with more conviction."
        return "Time exit flat/negative — thesis did not develop within the hold window."
    if exit_reason == "signal":
        if outcome_pct > 0:
            return "Signal-driven exit with gain — model correctly called the reversal."
        return "Signal sell at a loss — entry signal may have been a false positive."
    return f"Trade closed via {exit_reason} at {outcome_pct:+.1%} after {holding_days}d."


def query_pattern_stats(con: sqlite3.Connection) -> list[dict]:
    """Win rate and average return grouped by exit reason."""
    _ensure_table(con)
    rows = con.execute(
        """SELECT exit_reason,
                  COUNT(*) AS n,
                  SUM(CASE WHEN outcome_pct > 0 THEN 1 ELSE 0 END) AS wins,
                  AVG(outcome_pct) AS avg_pct
           FROM trade_journal
           WHERE closed_at IS NOT NULL AND exit_reason IS NOT NULL
           GROUP BY exit_reason ORDER BY n DESC"""
    ).fetchall()
    return [
        {
            "exit_reason": r[0], "n": r[1], "wins": r[2],
            "avg_pct": round(float(r[3] or 0) * 100, 2),
            "win_rate": round(r[2] / r[1] * 100, 1) if r[1] else 0.0,
        }
        for r in rows
    ]


def recent_entries(con: sqlite3.Connection, limit: int = 25) -> list[dict]:
    """Return the most-recent journal entries (open and closed), newest first."""
    _ensure_table(con)
    rows = con.execute(
        """SELECT symbol, entry_reason, entry_confidence, exit_reason,
                  outcome_pct, holding_days, lesson, created_at, closed_at
           FROM trade_journal ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    keys = ["symbol", "entry_reason", "entry_confidence", "exit_reason",
            "outcome_pct", "holding_days", "lesson", "created_at", "closed_at"]
    return [dict(zip(keys, r)) for r in rows]
