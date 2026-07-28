"""Phase 1A Sprint 5 -- decision_outcome_events writer.

Closes the loop Sprint 3 deliberately left open: writing this table is
what transitions a decision from OPEN to CLOSED in the decision_state
view, and what makes check_fingerprint's dedup guard meaningful (a closed
BUY no longer blocks a legitimate same-day re-entry).

decision_outcome_events.decision_id references the ORIGINAL BUY's Trust
Ledger decision_id, not the SELL's -- the SELL is its own independent
decision_events row (per Sprint 3's design decision (d)); this table
answers "what happened to the position that BUY opened," mirroring
decision_log's own find_open_decision_id/complete_decision pattern
against the Trust Ledger's separate, UUID-based decision_id space.
"""
from __future__ import annotations

import sqlite3

import ledger.ledger as ledger_svc
from bot.trust_ledger.ids import new_outcome_id


def find_open_buy_decision_id(conn: sqlite3.Connection, asset: str) -> str | None:
    """The most recent EXECUTED BUY decision_events row for this asset that
    is still OPEN (decision_state, derived from row existence in this very
    table) -- the entry decision whose outcome an exit should close."""
    row = conn.execute(
        "SELECT decision_id FROM decision_events "
        "WHERE asset=? AND action='BUY' AND event_type='EXECUTED' "
        "ORDER BY sequence_number DESC LIMIT 1",
        (asset,),
    ).fetchone()
    if not row:
        return None
    state = conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (row[0],)
    ).fetchone()
    return row[0] if state and state[0] == "OPEN" else None


def _latest_cost_model_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT cost_model_id FROM cost_models ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def estimate_net_return(gross_return: float, spread_assumption: float, slippage_assumption: float) -> tuple[float, dict]:
    """The codebase doesn't track actual per-trade round-trip transaction
    costs separately today -- this applies the bootstrapped cost-model
    assumptions as an estimate, documented as such via cost_breakdown,
    rather than presenting net_return as a precise reconstruction.
    Commission is 0.0 (Alpaca is zero-commission for US equities)."""
    commission = 0.0
    net_return = gross_return - spread_assumption - slippage_assumption - commission
    return net_return, {
        "spread": spread_assumption, "slippage": slippage_assumption, "commission": commission,
        "note": "estimated from bootstrapped cost_model assumptions, not a precise per-trade reconstruction",
    }


def write_decision_outcome_event(
    conn: sqlite3.Connection,
    asset: str,
    decision_id: str,
    exit_timestamp: str,
    gross_return: float,
    holding_period_days: int,
    spread_assumption: float = 0.001,
    slippage_assumption: float = 0.001,
) -> dict:
    net_return, cost_breakdown = estimate_net_return(gross_return, spread_assumption, slippage_assumption)
    cost_model_id = _latest_cost_model_id(conn)
    return ledger_svc.append_ledger_row(conn, "decision_outcome_events", {
        "outcome_id": new_outcome_id(asset),
        "decision_id": decision_id,
        "exit_timestamp": exit_timestamp,
        "gross_return": gross_return,
        "net_return": net_return,
        "holding_period_days": holding_period_days,
        "cost_breakdown": cost_breakdown,
        "cost_model_id": cost_model_id,
    })
