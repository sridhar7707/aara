"""DB initialization and backwards-compatible re-exports.

Heavy helpers live in focused sub-modules:
  bot/db/risk_state.py  — RiskSnapshot, load_risk_state, save_risk_state
  bot/db/trade_log.py   — log_trade, log_signal, log_recommendation, record_snapshot
  bot/db/macro_cache.py — get_macro
"""
from __future__ import annotations

import contextlib
import sqlite3
from datetime import date, timedelta

from loguru import logger

from bot.core.error_logger import log_exception
from config import TRADE_DB_PATH
from database.query_metrics import _init_schema as _init_qm_schema

# ── Re-exports (callers import from here; actual code in sub-modules) ─────────
from bot.db.risk_state import (          # noqa: F401
    RiskSnapshot,
    _week_key,
    load_risk_state as _load_risk_state,
    save_risk_state as _save_risk_state,
)
from bot.db.trade_log import (           # noqa: F401
    log_trade,
    log_signal as _log_signal,
    log_recommendation as _log_recommendation,
    record_snapshot as _record_snapshot,
)
from bot.db.macro_cache import (         # noqa: F401
    get_macro as _get_macro_from_db,
)


# ── WAL / initialization ──────────────────────────────────────────────────────

def _enable_wal_mode(db_path: str) -> None:
    """Enable WAL journal mode so dashboard readers don't block the bot writer."""
    try:
        with contextlib.closing(sqlite3.connect(db_path)) as con:
            row = con.execute("PRAGMA journal_mode=WAL").fetchone()
            actual = row[0] if row else "unknown"
            if actual != "wal":
                logger.warning(
                    f"WAL mode not confirmed on {db_path}: got {actual!r} "
                    "— concurrent reads may block writer"
                )
            else:
                logger.info(f"WAL mode verified: {db_path}")
            con.execute("PRAGMA synchronous=NORMAL")
    except Exception as exc:
        log_exception(logger, "_enable_wal_mode", exc, {"db_path": db_path})


def init_db(db_path: str = TRADE_DB_PATH) -> sqlite3.Connection:
    _enable_wal_mode(db_path)
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, symbol TEXT, action TEXT,
            shares REAL, price REAL, notional REAL,
            regime TEXT, portfolio_value REAL, pnl_pct REAL,
            xgb_prob REAL DEFAULT 0.0, lstm_prob REAL DEFAULT 0.0,
            sentiment_score REAL DEFAULT 0.0, macro_score REAL DEFAULT 0.0,
            ensemble_score REAL DEFAULT 0.0, realized_pnl REAL DEFAULT 0.0,
            order_id TEXT DEFAULT NULL, holding_days INTEGER DEFAULT 0,
            feature_drivers TEXT DEFAULT NULL
        )
    """)
    for _col in (
        "xgb_prob REAL DEFAULT 0.0", "lstm_prob REAL DEFAULT 0.0",
        "sentiment_score REAL DEFAULT 0.0", "macro_score REAL DEFAULT 0.0",
        "ensemble_score REAL DEFAULT 0.0", "realized_pnl REAL DEFAULT 0.0",
        "order_id TEXT DEFAULT NULL", "holding_days INTEGER DEFAULT 0",
        "feature_drivers TEXT DEFAULT NULL", "ai_reasoning TEXT DEFAULT NULL",
        "stop_loss REAL DEFAULT NULL", "take_profit REAL DEFAULT NULL",
        "risk_reward_ratio REAL DEFAULT NULL",
    ):
        try:
            con.execute(f"ALTER TABLE trades ADD COLUMN {_col}")
        except sqlite3.OperationalError:
            pass
    con.execute("""CREATE TABLE IF NOT EXISTS position_state (
        symbol TEXT PRIMARY KEY, entry_price REAL,
        high_water_mark REAL, atr_at_entry REAL, opened_at TEXT)""")
    try:
        con.execute("ALTER TABLE position_state ADD COLUMN shares REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass  # column already exists
    con.execute("""CREATE TABLE IF NOT EXISTS risk_state (
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS earnings_cache (
        symbol TEXT PRIMARY KEY, near_earnings INTEGER, cached_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS macro_cache (
        key TEXT PRIMARY KEY, value REAL, cached_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        timestamp TEXT PRIMARY KEY, portfolio_value REAL,
        available_cash REAL, open_positions INTEGER)""")
    con.execute("""CREATE TABLE IF NOT EXISTS signal_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL, xgb_prob REAL, lstm_prob REAL,
        sentiment_score REAL, macro_score REAL, ensemble_score REAL,
        ensemble_action TEXT, regime TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS screener_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, screened_at TEXT NOT NULL,
        symbol TEXT NOT NULL, rank INTEGER, composite_score REAL,
        analyst_signal REAL, etf_momentum REAL, regime TEXT, sector TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS signal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL, entry_price REAL, stop_price REAL,
        target_price REAL, rr_ratio REAL, setup_type TEXT,
        xgb_prob REAL, lstm_prob REAL, ensemble_score REAL, macro_score REAL,
        outcome TEXT DEFAULT 'pending', outcome_price REAL,
        outcome_pct REAL, outcome_ts TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
        prediction_date TEXT NOT NULL, recommendation TEXT, confidence REAL,
        prev_recommendation TEXT, price_at_recommendation REAL, created_at TEXT,
        UNIQUE(symbol, prediction_date))""")
    con.execute("""CREATE TABLE IF NOT EXISTS news_cache (
        symbol TEXT, fetch_date TEXT, headlines_json TEXT, cached_at TEXT,
        PRIMARY KEY (symbol, fetch_date))""")
    con.execute("""CREATE TABLE IF NOT EXISTS user_settings (
        key TEXT PRIMARY KEY, value TEXT NOT NULL,
        updated_at TEXT DEFAULT (datetime('now')))""")
    _init_v2_tables(con)
    _init_qm_schema(con)
    con.commit()
    from bot._main_decisions import backfill_decisions_from_trades
    backfill_decisions_from_trades(con)
    return con


def _init_v2_tables(con: sqlite3.Connection) -> None:
    """Create v2 advanced-feature tables (safe no-ops if already present)."""
    con.execute("CREATE TABLE IF NOT EXISTS capital_accounts ("
                "id INTEGER PRIMARY KEY, initial_deposit REAL NOT NULL DEFAULT 1000.0,"
                "ai_generated_profit REAL NOT NULL DEFAULT 0.0,"
                "reinvest_profits_only INTEGER NOT NULL DEFAULT 0,"
                "updated_at TEXT DEFAULT (datetime('now')))")
    con.execute("CREATE TABLE IF NOT EXISTS investment_theses ("
                "thesis_id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,"
                "thesis_text TEXT, price_target REAL, invalidation_criteria TEXT,"
                "review_trigger TEXT DEFAULT 'quarterly', next_review_date TEXT,"
                "confidence_at_entry INTEGER DEFAULT 75, current_validity TEXT DEFAULT 'valid',"
                "last_evaluated_date TEXT, ai_evaluation_notes TEXT,"
                "created_at TEXT DEFAULT (datetime('now')))")
    con.execute("CREATE TABLE IF NOT EXISTS decision_log ("
                "decision_id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,"
                "decision_date TEXT NOT NULL, decision_type TEXT NOT NULL,"
                "price_at_decision REAL, quantity_changed REAL, reasoning TEXT,"
                "ai_confidence INTEGER, portfolio_value_at_time REAL,"
                "triggered_by TEXT DEFAULT 'ai', created_at TEXT DEFAULT (datetime('now')))")
    # Decision Intelligence Phase 1 — BUY-candidate lifecycle capture, added on top
    # of the original trades-mirror schema above. See docs/PHASE_PLAN_decision_intelligence.md
    # (local, not in git) for the full rationale; kept brief here since that's not
    # source-controlled and this comment is what survives in the repo.
    for _dl_col in (
        "signal_log_id INTEGER DEFAULT NULL",         # FK -> signal_log.id (model evidence by reference)
        "trade_id INTEGER DEFAULT NULL",               # FK -> trades.id (NULL until/unless executed)
        "gate_reason TEXT DEFAULT NULL",               # which entry gate blocked it, if any
        "decision_source TEXT DEFAULT NULL",           # AI_SIGNAL / HUMAN_INITIATED / SYSTEM_REBALANCE
        "decision_reason TEXT DEFAULT NULL",           # short structured reason
        "risk_factors TEXT DEFAULT NULL",
        "expected_holding_period INTEGER DEFAULT NULL",
        "thesis TEXT DEFAULT NULL",                    # optional longer-form narrative
        "lesson_learned TEXT DEFAULT NULL",            # nullable — filled only once outcome analysis exists
        "decision_status TEXT DEFAULT NULL",           # CREATED/WAITING_APPROVAL/APPROVED/USER_REJECTED/SYSTEM_BLOCKED/EXPIRED
        "execution_status TEXT DEFAULT NULL",          # NOT_EXECUTED/EXECUTED
        "outcome_status TEXT DEFAULT 'UNKNOWN'",       # WIN/LOSS/NEUTRAL/UNKNOWN — never set at creation time
        "executed_at TEXT DEFAULT NULL",
        "outcome_known_at TEXT DEFAULT NULL",
        # Phase 4 — Supervised Autonomy: gates already passed once at decision
        # time, so a later human-approved resumption replays these instead of
        # recomputing Kelly sizing / ATR stops against whatever the market
        # looks like by then.
        "suggested_notional REAL DEFAULT NULL",
        "suggested_stop_loss REAL DEFAULT NULL",
        "suggested_take_profit REAL DEFAULT NULL",
        "suggested_rr_ratio REAL DEFAULT NULL",
    ):
        try:
            con.execute(f"ALTER TABLE decision_log ADD COLUMN {_dl_col}")
        except sqlite3.OperationalError:
            pass
    con.execute("CREATE TABLE IF NOT EXISTS daily_changes ("
                "change_id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,"
                "change_date TEXT NOT NULL, confidence_yesterday INTEGER,"
                "confidence_today INTEGER, action_yesterday TEXT, action_today TEXT,"
                "action_changed INTEGER DEFAULT 0, change_reason TEXT,"
                "significance TEXT DEFAULT 'minor', UNIQUE(symbol, change_date))")


def _anchor_daily_start(con: sqlite3.Connection) -> tuple[float | None, str]:
    """Pick the start-of-day equity baseline for Day P&L from the prior business day."""
    today = date.today()
    prior = today - timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= timedelta(days=1)
    prior_start = prior.isoformat()
    prior_end   = today.isoformat()

    row = con.execute(
        "SELECT timestamp, portfolio_value FROM portfolio_snapshots "
        "WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC LIMIT 1",
        (prior_start, prior_end),
    ).fetchone()
    if row and row[1] is not None:
        return float(row[1]), f"snapshot from {row[0][:10]}"

    row = con.execute(
        "SELECT timestamp, portfolio_value FROM trades "
        "WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC LIMIT 1",
        (prior_start, prior_end),
    ).fetchone()
    if row and row[1] is not None:
        return float(row[1]), f"trade from {row[0][:10]}"

    return None, f"no data for {prior_start} — starting fresh"
