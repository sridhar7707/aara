"""Decision Intelligence service — lifecycle layer for BUY-candidate decisions.

Decision lifecycle:

    CREATED
       |
       +--> SYSTEM_BLOCKED
       |
       +--> WAITING_APPROVAL
       |          |
       |          +--> USER_REJECTED
       |          |
       |          +--> APPROVED
       |
       +--> EXECUTED
                  |
                  v
            OUTCOME_KNOWN

Rules:
- Decisions are created before trades. A decision can exist without ever
  becoming a trade (rejected by a human, blocked by a risk gate, or expired).
- Trades are one possible outcome of a decision, not the decision itself.
- SELL actions remain risk-engine controlled and outside this lifecycle —
  stop-loss, trailing-stop, and drift-trim exits are risk controls, not
  investment choices, and continue writing directly to trades/trade_journal.
- outcome_status is never computed at creation time. It stays UNKNOWN until
  complete_decision() runs at exit, and evaluate_decision() may refine it
  later once vs-SPY data is available. Judging a decision before its outcome
  window closes defeats the entire point of this model.
"""
from __future__ import annotations

import datetime
import sqlite3

from loguru import logger

_logger = logger


def create_decision(
    con: sqlite3.Connection,
    symbol: str,
    price_at_decision: float,
    portfolio_value_at_time: float,
    decision_type: str = "BUY",
    signal_log_id: int | None = None,
    decision_source: str = "AI_SIGNAL",
    decision_reason: str | None = None,
    risk_factors: str | None = None,
    expected_holding_period: int | None = None,
    thesis: str | None = None,
    ai_confidence: int | None = None,
) -> int:
    """Record a decision at the moment a BUY candidate is born — before any
    entry gate runs. Returns the new decision_id. quantity_changed is left
    NULL here; it isn't known until position sizing runs inside the gates."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = con.execute(
        """INSERT INTO decision_log
           (symbol, decision_date, decision_type, price_at_decision, reasoning,
            ai_confidence, portfolio_value_at_time, triggered_by, created_at,
            signal_log_id, decision_source, decision_reason, risk_factors,
            expected_holding_period, thesis, decision_status, execution_status,
            outcome_status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (symbol, now[:10], decision_type, price_at_decision, decision_reason,
         ai_confidence, portfolio_value_at_time, "ai", now,
         signal_log_id, decision_source, decision_reason, risk_factors,
         expected_holding_period, thesis, "CREATED", "NOT_EXECUTED", "UNKNOWN"),
    )
    con.commit()
    decision_id = cur.lastrowid
    _logger.debug(f"Decision created [{decision_id}] {symbol} {decision_type} @ ${price_at_decision:.2f}")
    return decision_id


def reject_decision(con: sqlite3.Connection, decision_id: int, rejected_by: str, reason: str) -> None:
    """Mark a decision as not proceeding — never executes.
    rejected_by: 'user' (supervised-mode human rejection) or 'system' (an entry
    gate blocked it). Reuses gate_reason as the free-text reason for either case."""
    status = "USER_REJECTED" if rejected_by == "user" else "SYSTEM_BLOCKED"
    con.execute(
        "UPDATE decision_log SET decision_status=?, gate_reason=? WHERE decision_id=?",
        (status, reason, decision_id),
    )
    con.commit()
    _logger.info(f"Decision [{decision_id}] {status}: {reason}")


def approve_decision(con: sqlite3.Connection, decision_id: int, approved_by: str) -> None:
    """Mark a decision approved. approved_by: 'system' (autonomous mode, all
    gates passed) or 'user' (supervised mode, human clicked approve). Does not
    execute the trade — call mark_executed() separately once an order fills."""
    con.execute(
        "UPDATE decision_log SET decision_status='APPROVED' WHERE decision_id=?",
        (decision_id,),
    )
    con.commit()
    _logger.debug(f"Decision [{decision_id}] APPROVED by {approved_by}")


def mark_waiting_approval(con: sqlite3.Connection, decision_id: int) -> None:
    """Supervised-mode only: all gates passed, decision now waits on a human.
    Not one of the five originally-scoped functions — added because gates
    passing under SUPERVISED mode is a distinct transition from both
    'system-approved' (autonomous) and the terminal 'user-approved' action."""
    con.execute(
        "UPDATE decision_log SET decision_status='WAITING_APPROVAL' WHERE decision_id=?",
        (decision_id,),
    )
    con.commit()
    _logger.info(f"Decision [{decision_id}] WAITING_APPROVAL")


def mark_executed(con: sqlite3.Connection, decision_id: int, trade_id: int,
                   quantity_changed: float | None = None) -> None:
    """Link a decision to the trade that executed it. Also not one of the five
    originally-scoped functions — added because none of create/approve/reject/
    complete/evaluate cleanly represents 'the order filled, link trade_id'."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    con.execute(
        "UPDATE decision_log SET execution_status='EXECUTED', trade_id=?, "
        "executed_at=?, quantity_changed=COALESCE(?, quantity_changed) WHERE decision_id=?",
        (trade_id, now, quantity_changed, decision_id),
    )
    con.commit()
    _logger.debug(f"Decision [{decision_id}] EXECUTED -> trade_id={trade_id}")


def complete_decision(con: sqlite3.Connection, decision_id: int, realized_pnl_pct: float) -> None:
    """Called when the linked trade's position closes (a SELL fires). Records
    only factual, immediately-known outcome data — no lessons, no vs-SPY yet.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    outcome = "WIN" if realized_pnl_pct > 0 else ("LOSS" if realized_pnl_pct < 0 else "NEUTRAL")
    con.execute(
        "UPDATE decision_log SET outcome_status=?, outcome_known_at=? WHERE decision_id=?",
        (outcome, now, decision_id),
    )
    con.commit()
    _logger.debug(f"Decision [{decision_id}] outcome={outcome} ({realized_pnl_pct:+.2%})")


def evaluate_decision(con: sqlite3.Connection, decision_id: int) -> dict:
    """Compute vs-SPY performance for a completed decision. Read-only — writes
    nothing back to decision_log (no spy_return/alpha columns exist; these are
    meant to be computed on demand, same pattern dashboard/components/
    attribution.py already uses for trades). Not wired into any caller yet —
    built for Phase 2 analytics (Confidence Calibration, SPY attribution)."""
    row = con.execute(
        "SELECT symbol, trade_id, outcome_known_at FROM decision_log WHERE decision_id=?",
        (decision_id,),
    ).fetchone()
    if not row or not row[1] or not row[2]:
        return {"decision_id": decision_id, "error": "no completed trade linked yet"}
    _symbol, trade_id, outcome_known_at = row
    trade = con.execute("SELECT pnl_pct, holding_days FROM trades WHERE id=?", (trade_id,)).fetchone()
    if not trade:
        return {"decision_id": decision_id, "error": "linked trade not found"}
    pnl_pct, holding_days = float(trade[0] or 0.0), int(trade[1] or 0)
    spy_return = _spy_return_over_window(outcome_known_at, holding_days)
    if spy_return is None:
        return {"decision_id": decision_id, "return_pct": pnl_pct, "spy_return": None, "alpha": None}
    return {"decision_id": decision_id, "return_pct": pnl_pct,
            "spy_return": spy_return, "alpha": pnl_pct - spy_return}


def _spy_return_over_window(exit_iso: str, holding_days: int) -> float | None:
    """SPY's return over the same holding window as a closed trade. Self-
    contained (doesn't import dashboard/) to avoid a database -> dashboard
    layering dependency — database/services should not depend on dashboard/."""
    try:
        import yfinance as yf
        exit_date  = datetime.datetime.fromisoformat(str(exit_iso).replace("Z", "+00:00")).date()
        entry_date = exit_date - datetime.timedelta(days=max(holding_days, 1))
        hist = yf.Ticker("SPY").history(
            start=(entry_date - datetime.timedelta(days=5)).isoformat(),
            end=(exit_date + datetime.timedelta(days=1)).isoformat(),
        )
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        dates  = [d.date() if hasattr(d, "date") else d for d in hist.index]
        closes = list(hist["Close"])
        entry_px = next((closes[i] for i in range(len(dates) - 1, -1, -1) if dates[i] <= entry_date), None)
        exit_px  = next((closes[i] for i in range(len(dates) - 1, -1, -1) if dates[i] <= exit_date), None)
        if not entry_px or not exit_px or entry_px <= 0:
            return None
        return float((exit_px - entry_px) / entry_px)
    except Exception as exc:
        _logger.debug(f"_spy_return_over_window: {exc}")
        return None
