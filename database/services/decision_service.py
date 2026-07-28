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


def mark_waiting_approval(
    con: sqlite3.Connection, decision_id: int,
    suggested_notional: float | None = None,
    suggested_stop_loss: float | None = None,
    suggested_take_profit: float | None = None,
    suggested_rr_ratio: float | None = None,
) -> None:
    """Supervised-mode only: all gates passed, decision now waits on a human.
    Not one of the five originally-scoped functions — added because gates
    passing under SUPERVISED mode is a distinct transition from both
    'system-approved' (autonomous) and the terminal 'user-approved' action.

    The four suggested_* values capture the sizing/risk parameters already
    computed by the entry-gate pipeline at this exact moment — so a later
    human-approved resumption (see list_approved_unexecuted()) replays what
    already passed the gates instead of recomputing Kelly sizing or ATR
    stops against whatever the market looks like by the time a human acts."""
    con.execute(
        "UPDATE decision_log SET decision_status='WAITING_APPROVAL', "
        "suggested_notional=?, suggested_stop_loss=?, suggested_take_profit=?, "
        "suggested_rr_ratio=? WHERE decision_id=?",
        (suggested_notional, suggested_stop_loss, suggested_take_profit,
         suggested_rr_ratio, decision_id),
    )
    con.commit()
    _logger.info(f"Decision [{decision_id}] WAITING_APPROVAL")


def has_pending_decision(con: sqlite3.Connection, symbol: str) -> bool:
    """True if `symbol` already has a decision waiting on a human, or one a
    human has approved but the bot hasn't executed yet. Used to stop the
    entry-gate pipeline from spamming a fresh WAITING_APPROVAL row for the
    same symbol every cycle its signal keeps firing while the first one is
    still unresolved."""
    row = con.execute(
        "SELECT 1 FROM decision_log WHERE symbol=? AND ("
        "decision_status='WAITING_APPROVAL' OR "
        "(decision_status='APPROVED' AND execution_status='NOT_EXECUTED')"
        ") LIMIT 1",
        (symbol,),
    ).fetchone()
    return row is not None


def list_pending_approvals(con: sqlite3.Connection) -> list[dict]:
    """All decisions currently waiting on a human, oldest first — the
    dashboard's approval queue."""
    rows = con.execute(
        "SELECT decision_id, symbol, ai_confidence, decision_reason, "
        "suggested_notional, created_at FROM decision_log "
        "WHERE decision_status='WAITING_APPROVAL' ORDER BY decision_id ASC"
    ).fetchall()
    keys = ["decision_id", "symbol", "ai_confidence", "decision_reason",
            "suggested_notional", "created_at"]
    return [dict(zip(keys, r)) for r in rows]


def list_approved_unexecuted(con: sqlite3.Connection) -> list[dict]:
    """Today's BUY decisions a human has approved but the bot hasn't placed
    yet — what bot/_main_cycle.py's resumption step executes each cycle.
    Scoped to today only; anything older is handled by
    expire_stale_decisions() instead of executed on a stale price. Safe by
    construction: an AUTONOMOUS approval executes in the same function call
    as approve_decision(), so a row can only land here via a human clicking
    approve under SUPERVISED mode."""
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    rows = con.execute(
        "SELECT decision_id, symbol, suggested_notional, suggested_stop_loss, "
        "suggested_take_profit, suggested_rr_ratio FROM decision_log "
        "WHERE decision_status='APPROVED' AND execution_status='NOT_EXECUTED' "
        "AND decision_type='BUY' AND decision_date=? ORDER BY decision_id ASC",
        (today,),
    ).fetchall()
    keys = ["decision_id", "symbol", "suggested_notional", "suggested_stop_loss",
            "suggested_take_profit", "suggested_rr_ratio"]
    return [dict(zip(keys, r)) for r in rows]


def expire_stale_decisions(con: sqlite3.Connection) -> int:
    """Any decision still WAITING_APPROVAL, or APPROVED but not yet executed,
    from a prior trading day is stale — the price/sizing it was built on no
    longer reflects reality. Expire rather than silently execute on a
    days-old quote. Returns the number of rows expired."""
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    cur = con.execute(
        "UPDATE decision_log SET decision_status='EXPIRED' WHERE decision_date<? AND ("
        "decision_status='WAITING_APPROVAL' OR "
        "(decision_status='APPROVED' AND execution_status='NOT_EXECUTED'))",
        (today,),
    )
    con.commit()
    if cur.rowcount:
        _logger.info(f"Decision backfill: expired {cur.rowcount} stale pending/approved decision(s)")
    return cur.rowcount


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


def find_open_decision_id(con: sqlite3.Connection, symbol: str) -> int | None:
    """Find the decision behind a position that's about to close, at exit time.
    A symbol can only have one open, uncompleted decision at once (the entry
    gates already block re-buying a symbol that's already held), so the most
    recent EXECUTED-but-not-yet-completed row is unambiguous. Returns None for
    positions opened before this wiring existed — callers must skip gracefully,
    not error, since most currently-open positions predate Commit 4."""
    row = con.execute(
        "SELECT decision_id FROM decision_log WHERE symbol=? AND execution_status='EXECUTED' "
        "AND outcome_known_at IS NULL ORDER BY decision_id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    return row[0] if row else None


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


_DEFAULT_COUNTERFACTUAL_WINDOW_DAYS = 10


def list_rejected_decisions(con: sqlite3.Connection, limit: int = 200) -> list[dict]:
    """Decisions that never became a trade -- blocked by a gate, rejected by a
    human, or expired waiting on one. The raw material for counterfactual
    analysis ("what happened to the ones we passed on?"). Most recent first."""
    rows = con.execute(
        "SELECT decision_id, symbol, decision_date, price_at_decision, gate_reason, "
        "decision_status, ai_confidence, expected_holding_period "
        "FROM decision_log WHERE decision_status IN ('SYSTEM_BLOCKED', 'USER_REJECTED', 'EXPIRED') "
        "ORDER BY decision_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    keys = ["decision_id", "symbol", "decision_date", "price_at_decision", "gate_reason",
            "decision_status", "ai_confidence", "expected_holding_period"]
    return [dict(zip(keys, r)) for r in rows]


def evaluate_rejected_decision(con: sqlite3.Connection, decision_id: int) -> dict:
    """What actually happened to a rejected/blocked decision's symbol afterward --
    read-only, writes nothing back to decision_log (same pattern as
    evaluate_decision()). Uses expected_holding_period as the window if the
    decision recorded one, else a fixed default. Returns forward_return=None
    with an explanatory 'error' if the window hasn't closed yet or price
    history isn't available -- never a partial/in-progress return, matching
    the project's standing rule that outcomes aren't judged before their
    window closes."""
    row = con.execute(
        "SELECT symbol, price_at_decision, decision_date, expected_holding_period, decision_status "
        "FROM decision_log WHERE decision_id=?", (decision_id,),
    ).fetchone()
    if not row:
        return {"decision_id": decision_id, "forward_return": None, "error": "no such decision"}
    symbol, price_at_decision, decision_date, holding_period, status = row
    if status not in ("SYSTEM_BLOCKED", "USER_REJECTED", "EXPIRED"):
        return {"decision_id": decision_id, "forward_return": None,
                "error": "decision was not rejected/blocked"}
    if not price_at_decision or not decision_date:
        return {"decision_id": decision_id, "forward_return": None,
                "error": "no price recorded at decision time"}

    window = holding_period or _DEFAULT_COUNTERFACTUAL_WINDOW_DAYS
    start_date = datetime.datetime.fromisoformat(decision_date[:10]).date()
    target_end = start_date + datetime.timedelta(days=window)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    if target_end > today:
        return {"decision_id": decision_id, "symbol": symbol, "forward_return": None,
                "error": "window not yet complete"}

    forward_return = _forward_return(symbol, start_date, target_end)
    if forward_return is None:
        return {"decision_id": decision_id, "symbol": symbol, "forward_return": None,
                "error": "price history unavailable"}
    return {"decision_id": decision_id, "symbol": symbol, "forward_return": forward_return,
            "window_days": window, "error": None}


def _forward_return(symbol: str, start_date: datetime.date, end_date: datetime.date) -> float | None:
    """Symbol's price return from start_date to end_date. Self-contained
    (doesn't import dashboard/), matching _spy_return_over_window()."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(
            start=start_date.isoformat(),
            end=(end_date + datetime.timedelta(days=1)).isoformat(),
        )
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        dates  = [d.date() if hasattr(d, "date") else d for d in hist.index]
        closes = list(hist["Close"])
        entry_px = next((closes[i] for i in range(len(dates)) if dates[i] >= start_date), None)
        exit_px  = next((closes[i] for i in range(len(dates) - 1, -1, -1) if dates[i] <= end_date), None)
        if not entry_px or not exit_px or entry_px <= 0:
            return None
        return float((exit_px - entry_px) / entry_px)
    except Exception as exc:
        _logger.debug(f"_forward_return({symbol}): {exc}")
        return None
