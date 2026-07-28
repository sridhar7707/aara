"""Phase 1A Sprint 4 -- risk_evaluation_events writer.

NORMAL/WARNING/DEFENSIVE classification is derived entirely from existing
RiskManager methods -- zero changes to bot/risk/risk_manager.py. Written
once per cycle (portfolio-level; risk_evaluation_events has no symbol
column), not once per symbol.

OBSERVATION is the literal cold-start value: it appears exactly once, as
from_state of the very first row this system ever writes, and never again
as a to_state once the classifier has run once.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import ledger.ledger as ledger_svc
from bot.risk.risk_manager import RiskManager
from bot.trust_ledger.ids import new_event_id
from config import MAX_POSITION_PCT

_STATE_KEY = "risk_governor_state"  # new key in the existing risk_state table (Group C, mutable)
_SIZE_MULTIPLIER = {"NORMAL": 1.0, "WARNING": 0.5, "DEFENSIVE": 0.0}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify(risk: RiskManager, current_value: float) -> tuple[str, str]:
    """Returns (state, reason) -- the reason is written to
    risk_evaluation_events.trigger_reason, so an auditor can see *why* a
    cycle was WARNING/DEFENSIVE, not just that it was. DEFENSIVE (hard
    circuit breakers) > WARNING (soft breach / approaching limit) > NORMAL.
    Calls the existing check_* methods directly -- some have side effects
    (e.g. check_daily_loss sets risk.halted), which is fine here since
    approve_buy() already exercises the same methods with the same effects
    earlier in the cycle; calling them again is idempotent."""
    if risk.halted:
        return "DEFENSIVE", "risk.halted is set"
    if not risk.check_daily_loss(current_value):
        return "DEFENSIVE", "daily loss limit breached"
    if not risk.check_portfolio_drawdown(current_value):
        return "DEFENSIVE", "portfolio drawdown limit breached"
    if risk.check_daily_loss_warning(current_value):
        return "WARNING", "approaching daily loss limit"
    if not risk.check_weekly_loss(current_value):
        return "WARNING", "weekly loss limit breached"
    return "NORMAL", "no risk limits breached"


def recommend_position_size(sizing_base: float, classification: str) -> float:
    """Advisory only -- Observation Mode has zero enforcement authority
    (FR-1.10a). What the governor would apply if it could, not what's
    actually applied; compared against actual_position_size later to
    answer "would the governor's calls have helped" (the 90-day graduation
    question)."""
    return sizing_base * MAX_POSITION_PCT * _SIZE_MULTIPLIER.get(classification, 0.0)


def _get_last_state(trades_conn: sqlite3.Connection) -> str | None:
    row = trades_conn.execute("SELECT value FROM risk_state WHERE key=?", (_STATE_KEY,)).fetchone()
    return row[0] if row and row[0] else None


def _set_last_state(trades_conn: sqlite3.Connection, state: str) -> None:
    trades_conn.execute(
        "INSERT OR REPLACE INTO risk_state (key, value, updated_at) VALUES (?,?,?)",
        (_STATE_KEY, state, _utc_now()),
    )
    trades_conn.commit()


def record_risk_evaluation(
    trades_conn: sqlite3.Connection,
    trust_conn: sqlite3.Connection,
    risk: RiskManager,
    current_value: float,
    sizing_base: float,
    cycle_deployed_notional: float,
) -> dict:
    """trades_conn: the operational DB (bot/trades.db) -- risk_state is a
    Group C operational table, not part of the ledger, so last-classification
    persistence lives there, matching bot/db/risk_state.py's existing
    read/write pattern. trust_conn: the Trust Ledger DB, for the actual
    risk_evaluation_events write."""
    to_state, reason = classify(risk, current_value)
    from_state = _get_last_state(trades_conn) or "OBSERVATION"
    _set_last_state(trades_conn, to_state)

    recommended = recommend_position_size(sizing_base, to_state)
    return ledger_svc.append_ledger_row(trust_conn, "risk_evaluation_events", {
        "event_id": new_event_id(),
        "timestamp": _utc_now(),
        "from_state": from_state,
        "to_state": to_state,
        "trigger_reason": reason,
        "validation_mode": "NATURAL",
        "replay_scenario_id": None,
        "recommended_position_size": recommended,
        "actual_position_size": cycle_deployed_notional,
    })
