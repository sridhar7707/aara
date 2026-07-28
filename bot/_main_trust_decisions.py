"""Trust Ledger decision-writing helpers for the live trading pipeline
(entry gates in bot/_main_cycle.py, exit management in bot/_main_positions.py)
-- extracted to its own module since both of those files are already near
the project's 500-line limit.

Best-effort throughout: the Trust Ledger is an audit system, not a trading
gate. A write failure here must never block or alter the outcome of the
primary pipeline (decision_log, order placement, position tracking).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

import bot.trust_ledger.decisions as decisions
from bot.strategy.ensemble import ensemble_confidence
from bot.strategy.model_output_adapter import build_model_outputs


@dataclass
class ExitLedgerContext:
    """Bundles the Trust Ledger fields _handle_exits() needs into one param
    instead of growing its already-long signature by 7 -- optional (None
    means "skip ledger writes for this call"), so existing callers/tests
    that construct _handle_exits() directly don't need updating."""
    trust_conn: Any
    candidate_event_id: str | None
    deployment_manifest_id: str | None
    xgb_prob: float = 0.0
    lstm_prob: float = 0.0
    sentiment: float = 0.0
    macro_score: float = 0.5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_decision_safe(
    trust_conn: sqlite3.Connection, candidate_event_id: str | None,
    deployment_manifest_id: str | None,
    asset: str, action: str, event_type: str,
    portfolio_snapshot: dict, market_context: dict, model_outputs: dict,
    risk_checks: dict, final_confidence: float, intent: dict, data_completeness: dict,
) -> None:
    if candidate_event_id is None or deployment_manifest_id is None:
        logger.warning(
            f"trust ledger decision write skipped for {asset}: "
            "missing candidate_event_id or deployment_manifest_id"
        )
        return
    try:
        # check_fingerprint is NOT called here yet, deliberately: it treats any
        # EXECUTED decision as a blocking duplicate while decision_state still
        # reports it OPEN, and nothing writes decision_outcome_events until
        # Sprint 5 -- calling it now would silently block every symbol's
        # second-ever EXECUTED BUY/SELL, forever, not just genuine rapid-fire
        # duplicates. The existing pipeline already prevents the real-world
        # duplicate case structurally: _handle_exits() returns True (and its
        # caller `continue`s) for any symbol still in `positions`, so a second
        # BUY can't fire while the first is still held, and a second SELL
        # can't fire once nothing is held. Re-enable this call once Sprint 5
        # wires decision_outcome_events, so decision_state reflects real closes.
        decisions.write_decision_event(
            trust_conn, candidate_event_id, asset, action, event_type,
            portfolio_snapshot, market_context, model_outputs, risk_checks,
            final_confidence, deployment_manifest_id, intent, data_completeness,
        )
    except decisions.DuplicateDecisionError as e:
        logger.warning(f"trust ledger duplicate decision blocked for {asset}: {e}")
    except Exception as e:
        logger.warning(f"trust ledger decision write failed for {asset}: {e}")


class EntryDecisionRecorder:
    """One instance per _handle_entry() call. Computes the pieces of a
    decision_events row that stay constant across all of that call's entry
    gates just once (not once per gate), accumulates a gate-by-gate trace
    as .reject() is called at each early-return point, and writes the
    final row (REJECT/QUALIFIED_REJECTION or BUY/EXECUTED) exactly once."""

    def __init__(
        self, trust_conn, candidate_event_id, deployment_manifest_id, symbol: str,
        xgb_prob: float, lstm_prob: float, sentiment: float, macro_score: float,
        regime_name: str, portfolio_value: float, available_cash: float,
        price_data_timestamp: str | None,
        lstm_is_degraded: bool = False, lstm_val_loss: float | None = None,
    ):
        self.trust_conn = trust_conn
        self.candidate_event_id = candidate_event_id
        self.deployment_manifest_id = deployment_manifest_id
        self.symbol = symbol
        self.trace: list[dict] = []
        self.final_confidence = ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)
        self.model_outputs = build_model_outputs(
            xgb_prob, lstm_prob, sentiment,
            lstm_is_degraded=lstm_is_degraded, lstm_val_loss=lstm_val_loss,
        )
        self.market_context = {
            "regime": regime_name,
            "macro_score": macro_score,
            "decision_timestamp": _utc_now(),
            "price_data_timestamp": price_data_timestamp,
        }
        self.portfolio_snapshot = {"portfolio_value": portfolio_value, "available_cash": available_cash}
        self.data_completeness = decisions.build_data_completeness(lstm_is_degraded=lstm_is_degraded)

    def reject(self, gate_name: str, detail: str) -> None:
        """Called at every gate's early-return point -- including gates the
        symbol passed on the way to a later failure, via the trace already
        accumulated. Writes immediately since _handle_entry returns right
        after calling this."""
        self.trace.append({"gate": gate_name, "passed": False, "detail": detail})
        record_decision_safe(
            self.trust_conn, self.candidate_event_id, self.deployment_manifest_id,
            self.symbol, "REJECT", "QUALIFIED_REJECTION",
            self.portfolio_snapshot, self.market_context, self.model_outputs,
            {"gate_trace": self.trace}, self.final_confidence,
            decisions.build_intent("REJECT"), self.data_completeness,
        )

    def record_executed(
        self, notional: float, fill_price: float, fill_shares: float, xgb_drivers: list | None = None,
    ) -> None:
        """xgb_drivers: XGBPredictor.explain()'s SHAP output, if the caller
        has it available -- rebuilds model_outputs with it rather than
        reusing the __init__-time version (which never has drivers, since
        computing them for every rejected gate would be wasted SHAP calls)."""
        self.trace.append({"gate": "all_entry_gates", "passed": True, "detail": "all gates passed"})
        model_outputs = self.model_outputs
        if xgb_drivers:
            model_outputs = dict(self.model_outputs)
            model_outputs["xgboost"] = dict(model_outputs["xgboost"])
            model_outputs["xgboost"]["metadata"] = {
                "shap_drivers": [{"feature": str(f), "shap_value": float(v)} for f, v in xgb_drivers]
            }
        record_decision_safe(
            self.trust_conn, self.candidate_event_id, self.deployment_manifest_id,
            self.symbol, "BUY", "EXECUTED",
            self.portfolio_snapshot, self.market_context, model_outputs,
            {"gate_trace": self.trace, "notional": notional, "fill_price": fill_price,
             "fill_shares": fill_shares},
            self.final_confidence,
            decisions.build_intent("BUY", contributing_modules=["xgboost", "lstm", "finbert", "ensemble"]),
            self.data_completeness,
        )

    def record_order_not_filled(self, reason: str) -> None:
        """Gates all passed but the broker order never filled -- no
        portfolio-affecting action occurred, so this is QUALIFIED_REJECTION
        (per phase1a_requirements.md Section 12c), not EXECUTED."""
        self.trace.append({"gate": "order_fill", "passed": False, "detail": reason})
        record_decision_safe(
            self.trust_conn, self.candidate_event_id, self.deployment_manifest_id,
            self.symbol, "REJECT", "QUALIFIED_REJECTION",
            self.portfolio_snapshot, self.market_context, self.model_outputs,
            {"gate_trace": self.trace}, self.final_confidence,
            decisions.build_intent("REJECT"), self.data_completeness,
        )


def record_exit_decision_safe(
    ledger_ctx: ExitLedgerContext | None, symbol: str, action: str, event_type: str,
    reason: str, portfolio_value: float, current_price: float, regime_name: str = "",
) -> None:
    """SELL/HOLD decision write for bot/_main_positions.py's exit paths.
    Simpler than EntryDecisionRecorder -- exit checks are a flat ordered
    chain (first-match-wins), not a gate trace worth accumulating the same
    way. ledger_ctx=None (e.g. a caller/test not wired to the ledger) is a
    silent no-op, same best-effort philosophy as everywhere else here."""
    if ledger_ctx is None:
        return
    final_confidence = ensemble_confidence(
        ledger_ctx.xgb_prob, ledger_ctx.lstm_prob, ledger_ctx.sentiment, ledger_ctx.macro_score,
    )
    model_outputs = build_model_outputs(ledger_ctx.xgb_prob, ledger_ctx.lstm_prob, ledger_ctx.sentiment)
    market_context = {
        "regime": regime_name, "macro_score": ledger_ctx.macro_score,
        "decision_timestamp": _utc_now(),
    }
    record_decision_safe(
        ledger_ctx.trust_conn, ledger_ctx.candidate_event_id, ledger_ctx.deployment_manifest_id,
        symbol, action, event_type,
        {"portfolio_value": portfolio_value, "current_price": current_price},
        market_context, model_outputs, {"exit_reason": reason}, final_confidence,
        decisions.build_intent(action), decisions.build_data_completeness(),
    )


class ExitDecisionRecorder:
    """Binds the per-call-fixed args (ledger_ctx, symbol, portfolio_value,
    current_price, regime_name) once so bot/_main_positions.py's 7 exit
    call sites -- a file already near the 500-line limit -- can each stay
    one line: _rec.sell(success, reason) / _rec.reject(reason) / _rec.hold()."""

    def __init__(self, ledger_ctx: ExitLedgerContext | None, symbol: str,
                 portfolio_value: float, current_price: float, regime_name: str = ""):
        self._args = (ledger_ctx, symbol)
        self._kwargs = dict(portfolio_value=portfolio_value, current_price=current_price,
                            regime_name=regime_name)

    def sell(self, success: bool, reason: str) -> None:
        if success:
            record_exit_decision_safe(*self._args, "SELL", "EXECUTED", reason, **self._kwargs)
        else:
            record_exit_decision_safe(*self._args, "REJECT", "QUALIFIED_REJECTION",
                                      f"{reason} sell order failed to fill", **self._kwargs)

    def reject(self, reason: str) -> None:
        record_exit_decision_safe(*self._args, "REJECT", "QUALIFIED_REJECTION", reason, **self._kwargs)

    def hold(self, reason: str = "no exit condition met") -> None:
        record_exit_decision_safe(*self._args, "HOLD", "QUALIFIED_REJECTION", reason, **self._kwargs)
