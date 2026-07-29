"""Phase 1A -- constitution_enforcement_events writer.

Implements the six rules of docs/architecture/TRADING_CONSTITUTION.md as
advisory checks logged against every decision_events row. Per
phase0_decisions.md #17 (no per-trade human approval in Phase 1A) and the
constitution's own "Day 1-30: every rule is advisory" framing (Part 3),
ESCALATED/FAIL results are logged but never block execution -- same
best-effort philosophy as every other Trust Ledger write (see
bot/_main_trust_decisions.py's module docstring).

Rule 3 (trade structure) requires thesis/invalidation_point/
expected_return_basis_points on BUY only -- EntryDecisionRecorder.
record_executed() (bot/_main_trust_decisions.py) populates these from the
same stop/target sizing gates _handle_entry already computes before
placing the order. SELL is a RISK_MANAGEMENT_EXIT, not a fresh position --
it's the original BUY's invalidation point firing (or target hit), so
only the confidence floor applies there, not a restated thesis.

Rule 6 (override prevention) is a static ledger-level invariant already
enforced by schema.sql's append-only triggers, not something that varies
per decision -- logged once per decision as PASS stating that fact, so a
full six-row set exists for every decision (phase1a_requirements.md
Section 13a's enforcement workflow).

Deliberately does NOT call RiskManager.check_daily_loss() or reuse
bot.trust_ledger.risk.classify() -- check_daily_loss() sets risk.halted as
a side effect, which is safe when classify() is the only other caller
(once per cycle, at cycle end in record_risk_evaluation_safe). This module
runs once per decision, potentially several times per cycle; reusing a
mutating call here could set risk.halted mid-cycle earlier than
approve_buy() would have, changing which later symbols get blocked --
exactly the "alter the outcome of the primary pipeline" this module must
never do. _read_only_governor_state() mirrors classify()'s logic using
only non-mutating reads.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import ledger.ledger as ledger_svc
from bot.risk.risk_manager import RiskManager
from bot.trust_ledger.ids import new_constitution_event_id
from config import DAILY_LOSS_LIMIT_PCT

DRAWDOWN_WARNING_PCT = 0.15
DRAWDOWN_CRITICAL_PCT = 0.25
AUTONOMY_TRADE_COUNT = 20
LOW_CONFIDENCE_REVIEW_TRADE_COUNT = 50
LOW_CONFIDENCE_THRESHOLD = 0.65

_TRADE_ACTIONS = ("BUY", "SELL")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_only_governor_state(risk: RiskManager, portfolio_value: float) -> tuple[str, str]:
    if risk.halted:
        return "DEFENSIVE", "risk.halted is set"
    if risk.daily_start_value and risk.daily_start_value != 0.0:
        daily_pnl_pct = (portfolio_value - risk.daily_start_value) / risk.daily_start_value
        if daily_pnl_pct <= -DAILY_LOSS_LIMIT_PCT:
            return "DEFENSIVE", "daily loss limit breached"
    if not risk.check_portfolio_drawdown(portfolio_value):
        return "DEFENSIVE", "portfolio drawdown limit breached"
    if risk.check_daily_loss_warning(portfolio_value):
        return "WARNING", "approaching daily loss limit"
    if not risk.check_weekly_loss(portfolio_value):
        return "WARNING", "weekly loss limit breached"
    return "NORMAL", "no risk limits breached"


def _executed_trade_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM decision_events WHERE event_type='EXECUTED'"
    ).fetchone()
    return row[0] if row else 0


def _last_closed_net_return(conn: sqlite3.Connection, asset: str) -> float | None:
    row = conn.execute(
        "SELECT o.net_return FROM decision_outcome_events o "
        "JOIN decision_events d ON d.decision_id = o.decision_id "
        "WHERE d.asset=? ORDER BY o.sequence_number DESC LIMIT 1",
        (asset,),
    ).fetchone()
    return row[0] if row else None


def _rule_risk_governor_authority(decision_row: dict, governor_state: str) -> tuple[str, str, str]:
    if governor_state in ("WARNING", "DEFENSIVE") and decision_row["action"] == "BUY":
        return "ESCALATED", "advisory_only", (
            f"Risk Governor is {governor_state}; a new BUY would normally require "
            "human approval, but Phase 1A has no per-trade approval workflow "
            "(phase0_decisions.md #17) -- logged for Phase 1B compliance review."
        )
    return "PASS", "execution_proceeded", f"Risk Governor state {governor_state}, no restriction applies"


def _rule_position_sizing_discipline(conn: sqlite3.Connection, decision_row: dict) -> tuple[str, str, str]:
    if decision_row["action"] != "BUY":
        return "PASS", "execution_proceeded", "not a position-opening decision"
    prior_return = _last_closed_net_return(conn, decision_row["asset"])
    if prior_return is None or prior_return >= 0:
        return "PASS", "execution_proceeded", "no prior loss on this asset to compare against"
    return "PASS", "execution_proceeded", (
        f"prior {decision_row['asset']} trade closed at a loss (net_return={prior_return:.4f}); "
        "Risk Governor position sizing already scales down in WARNING/DEFENSIVE "
        "(bot/trust_ledger/risk.py recommend_position_size)"
    )


def _rule_trade_structure(decision_row: dict) -> tuple[str, str, str]:
    """BUY (OPPORTUNITY_ENTRY) must state thesis/invalidation_point/
    expected_return_basis_points -- TRADING_CONSTITUTION.md Rule 3's own
    English: "why, when it's wrong, and what you expect." SELL
    (RISK_MANAGEMENT_EXIT) doesn't get a fresh thesis: it IS the original
    BUY's invalidation point firing (or its target being hit), not a new
    position -- so only the confidence floor applies there."""
    action = decision_row["action"]
    if action not in _TRADE_ACTIONS:
        return "PASS", "execution_proceeded", "not a trade-committing decision"
    if decision_row.get("final_confidence", 0.0) < 0.5:
        return "ESCALATED", "advisory_only", "missing required fields: final_confidence>=0.5"
    if action != "BUY":
        return "PASS", "execution_proceeded", "exit decision: confidence floor met, no fresh thesis required"
    intent = decision_row.get("intent") or {}
    missing = []
    if not intent.get("thesis"):
        missing.append("intent.thesis")
    if not intent.get("invalidation_point"):
        missing.append("intent.invalidation_point")
    if intent.get("expected_return_basis_points") is None:
        missing.append("intent.expected_return_basis_points")
    if missing:
        return "ESCALATED", "advisory_only", "missing required fields: " + ", ".join(missing)
    return "PASS", "execution_proceeded", "thesis, invalidation point, expected return, and confidence all present"


def _rule_drawdown_circuit_breaker(risk: RiskManager, portfolio_value: float) -> tuple[str, str, str]:
    if not risk.portfolio_high:
        return "PASS", "execution_proceeded", "no recorded portfolio high yet"
    drawdown = (risk.portfolio_high - portfolio_value) / risk.portfolio_high
    if drawdown >= DRAWDOWN_CRITICAL_PCT:
        return "ESCALATED", "advisory_only", (
            f"critical drawdown {drawdown:.1%} >= {DRAWDOWN_CRITICAL_PCT:.0%}; constitution "
            "requires human approval for ALL trades -- Phase 1A has no such workflow, logged only"
        )
    if drawdown >= DRAWDOWN_WARNING_PCT:
        return "ESCALATED", "advisory_only", (
            f"drawdown {drawdown:.1%} >= {DRAWDOWN_WARNING_PCT:.0%}; constitution requires human "
            "approval for new BUYs -- Phase 1A has no such workflow, logged only"
        )
    return "PASS", "execution_proceeded", f"drawdown {drawdown:.1%} within limits"


def _rule_approval_escalation(conn: sqlite3.Connection, decision_row: dict) -> tuple[str, str, str]:
    if decision_row["action"] not in _TRADE_ACTIONS:
        return "PASS", "execution_proceeded", "not a trade-committing decision"
    count = _executed_trade_count(conn)
    if count < AUTONOMY_TRADE_COUNT:
        return "ESCALATED", "advisory_only", (
            f"trade #{count + 1}: below the {AUTONOMY_TRADE_COUNT}-trade evidence threshold for "
            "autonomous execution -- Phase 1A has no per-trade approval workflow, logged only"
        )
    confidence = decision_row.get("final_confidence", 1.0)
    if count < LOW_CONFIDENCE_REVIEW_TRADE_COUNT and confidence < LOW_CONFIDENCE_THRESHOLD:
        return "ESCALATED", "advisory_only", (
            f"trade #{count + 1}: confidence {confidence:.2f} < {LOW_CONFIDENCE_THRESHOLD} "
            f"while still below the {LOW_CONFIDENCE_REVIEW_TRADE_COUNT}-trade mark"
        )
    return "PASS", "execution_proceeded", f"trade #{count + 1}: evidence threshold met"


def _rule_override_prevention() -> tuple[str, str, str]:
    return "PASS", "execution_proceeded", (
        "append-only/no-update/no-delete enforced at the DB level by "
        "ledger/schema.sql triggers, independent of this check"
    )


def check_and_log(
    conn: sqlite3.Connection, decision_row: dict, risk: RiskManager | None,
) -> list[dict]:
    """Runs all six Trading Constitution rules against a just-written
    decision_events row (the dict returned by decisions.write_decision_event)
    and logs one constitution_enforcement_events row per rule. risk=None
    (e.g. a caller/test not wired to a live RiskManager) still logs Rules
    2/3/5/6, with Rules 1/4 reporting the OBSERVATION/no-data case rather
    than being skipped -- every decision gets a full six-row set."""
    portfolio_value = (decision_row.get("portfolio_snapshot") or {}).get("portfolio_value", 0.0)
    if risk is not None:
        governor_state, _ = _read_only_governor_state(risk, portfolio_value)
        drawdown_check = _rule_drawdown_circuit_breaker(risk, portfolio_value)
    else:
        governor_state = "OBSERVATION"
        drawdown_check = ("PASS", "execution_proceeded", "no RiskManager available for this check")

    checks = (
        ("rule_1", "Risk Governor Authority",
         _rule_risk_governor_authority(decision_row, governor_state)),
        ("rule_2", "Position Sizing Discipline",
         _rule_position_sizing_discipline(conn, decision_row)),
        ("rule_3", "Trade Structure Requirement",
         _rule_trade_structure(decision_row)),
        ("rule_4", "Portfolio Drawdown Circuit Breaker", drawdown_check),
        ("rule_5", "Approval Escalation for First N Trades",
         _rule_approval_escalation(conn, decision_row)),
        ("rule_6", "Override Prevention",
         _rule_override_prevention()),
    )

    rows = []
    for rule_id, rule_name, (result, action_taken, reason) in checks:
        rows.append(ledger_svc.append_ledger_row(conn, "constitution_enforcement_events", {
            "event_id": new_constitution_event_id(),
            "decision_id": decision_row["decision_id"],
            "rule_id": rule_id,
            "rule_name": rule_name,
            "check_timestamp": _utc_now(),
            "check_result": result,
            "action_taken": action_taken,
            "reason": reason,
        }))
    return rows
