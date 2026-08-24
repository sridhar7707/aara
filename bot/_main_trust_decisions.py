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

import bot.trust_ledger.constitution as constitution
import bot.trust_ledger.data_quality as data_quality
import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
import bot.trust_ledger.risk as risk_ledger
from bot.risk.risk_manager import RiskManager
from bot.strategy.ensemble import ensemble_confidence
from bot.strategy.model_output_adapter import build_model_outputs
from bot.strategy.sentiment import get_cached_headlines
from sentinel_engine.adapters.evidence_adapter import to_evidence_records
from sentinel_engine.adapters.governance_adapter import to_policy_id
from sentinel_engine.composition.evidence import get_evidence_service
from sentinel_engine.composition.governance import get_governance_service


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
    risk: RiskManager | None = None
    news_data_timestamp: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_decision_safe(
    trust_conn: sqlite3.Connection, candidate_event_id: str | None,
    deployment_manifest_id: str | None,
    asset: str, action: str, event_type: str,
    portfolio_snapshot: dict, market_context: dict, model_outputs: dict,
    risk_checks: dict, final_confidence: float, intent: dict, data_completeness: dict,
    risk: RiskManager | None = None,
) -> None:
    if candidate_event_id is None or deployment_manifest_id is None:
        logger.warning(
            f"trust ledger decision write skipped for {asset}: "
            "missing candidate_event_id or deployment_manifest_id"
        )
        return
    try:
        # Re-enabled in Sprint 5: ExitDecisionRecorder._record_outcome() now
        # writes decision_outcome_events right after every successful SELL,
        # so decision_state actually reflects real closes -- this no longer
        # blocks every symbol's second-ever EXECUTED BUY/SELL forever, the
        # way it would have if enabled back in Sprint 3 (see that commit).
        if event_type == "EXECUTED":
            decisions.check_fingerprint(
                trust_conn, asset, action, override_reason=intent.get("override_reason"),
            )
        decision_row = decisions.write_decision_event(
            trust_conn, candidate_event_id, asset, action, event_type,
            portfolio_snapshot, market_context, model_outputs, risk_checks,
            final_confidence, deployment_manifest_id, intent, data_completeness,
        )
        try:
            constitution.check_and_log(trust_conn, decision_row, risk)
        except Exception as e:
            logger.warning(f"trust ledger constitution check failed for {asset}: {e}")
        try:
            for evidence in to_evidence_records(decision_row["model_outputs"]):
                get_evidence_service().associate_evidence(decision_row["decision_id"], evidence)
        except Exception as e:
            logger.warning(f"trust ledger evidence integration failed for {asset}: {e}")
        try:
            policy_id = to_policy_id(decision_row)
            get_governance_service().evaluate_policy(decision_row["decision_id"], policy_id)
        except Exception as e:
            logger.warning(f"trust ledger governance evaluation failed for {asset}: {e}")
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
        risk: RiskManager | None = None, news_data_timestamp: str | None = None,
    ):
        self.trust_conn = trust_conn
        self.candidate_event_id = candidate_event_id
        self.deployment_manifest_id = deployment_manifest_id
        self.symbol = symbol
        self.risk = risk
        self.trace: list[dict] = []
        self.final_confidence = ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)
        self.model_outputs = build_model_outputs(
            xgb_prob, lstm_prob, sentiment,
            lstm_is_degraded=lstm_is_degraded, lstm_val_loss=lstm_val_loss,
            sentiment_headlines=get_cached_headlines(self.symbol),
        )
        self.market_context = {
            "regime": regime_name,
            "macro_score": macro_score,
            "decision_timestamp": _utc_now(),
            "price_data_timestamp": price_data_timestamp,
            "news_data_timestamp": news_data_timestamp,
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
            decisions.build_intent("REJECT"), self.data_completeness, risk=self.risk,
        )

    def record_executed(
        self, notional: float, fill_price: float, fill_shares: float,
        stop_pct: float, tp_target_pct: float, rr_ratio: float,
        xgb_drivers: list | None = None,
    ) -> None:
        """xgb_drivers: XGBPredictor.explain()'s SHAP output, if the caller
        has it available -- rebuilds model_outputs with it rather than
        reusing the __init__-time version (which never has drivers, since
        computing them for every rejected gate would be wasted SHAP calls).

        stop_pct/tp_target_pct/rr_ratio: the same sizing gates _handle_entry
        already computed and passed before ever placing the order (Gates
        8a/8b in bot/_main_cycle.py) -- reused here to populate
        intent.thesis/invalidation_point/expected_return_basis_points, per
        TRADING_CONSTITUTION.md Rule 3 (Trade Structure Requirement)."""
        self.trace.append({"gate": "all_entry_gates", "passed": True, "detail": "all gates passed"})
        model_outputs = self.model_outputs
        if xgb_drivers:
            model_outputs = dict(self.model_outputs)
            model_outputs["xgboost"] = dict(model_outputs["xgboost"])
            model_outputs["xgboost"]["metadata"] = {
                "shap_drivers": [{"feature": str(f), "shap_value": float(v)} for f, v in xgb_drivers]
            }
        thesis = (
            f"{self.symbol}: XGB {self.model_outputs['xgboost']['confidence']:.0%}, "
            f"LSTM {self.model_outputs['lstm']['confidence']:.0%}, "
            f"regime {self.market_context.get('regime', 'unknown')}; "
            f"stop {stop_pct:.1%}, target {tp_target_pct:.1%}, R:R {rr_ratio:.2f}x"
        )
        intent = decisions.build_intent(
            "BUY", contributing_modules=["xgboost", "lstm", "finbert", "ensemble"],
            thesis=thesis,
            invalidation_point=f"price closes below ${fill_price * (1 - stop_pct):.2f} (stop-loss)",
            expected_return_basis_points=round(tp_target_pct * 10_000),
        )
        record_decision_safe(
            self.trust_conn, self.candidate_event_id, self.deployment_manifest_id,
            self.symbol, "BUY", "EXECUTED",
            self.portfolio_snapshot, self.market_context, model_outputs,
            {"gate_trace": self.trace, "notional": notional, "fill_price": fill_price,
             "fill_shares": fill_shares},
            self.final_confidence, intent,
            self.data_completeness, risk=self.risk,
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
            decisions.build_intent("REJECT"), self.data_completeness, risk=self.risk,
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
    model_outputs = build_model_outputs(
        ledger_ctx.xgb_prob, ledger_ctx.lstm_prob, ledger_ctx.sentiment,
        sentiment_headlines=get_cached_headlines(symbol),
    )
    market_context = {
        "regime": regime_name, "macro_score": ledger_ctx.macro_score,
        "decision_timestamp": _utc_now(),
        "news_data_timestamp": ledger_ctx.news_data_timestamp,
    }
    record_decision_safe(
        ledger_ctx.trust_conn, ledger_ctx.candidate_event_id, ledger_ctx.deployment_manifest_id,
        symbol, action, event_type,
        {"portfolio_value": portfolio_value, "current_price": current_price},
        market_context, model_outputs, {"exit_reason": reason}, final_confidence,
        decisions.build_intent(action), decisions.build_data_completeness(), risk=ledger_ctx.risk,
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

    def sell(self, success: bool, reason: str, pnl_pct: float = 0.0, holding_days: int = 0) -> None:
        if success:
            record_exit_decision_safe(*self._args, "SELL", "EXECUTED", reason, **self._kwargs)
            self._record_outcome(pnl_pct, holding_days)
        else:
            record_exit_decision_safe(*self._args, "REJECT", "QUALIFIED_REJECTION",
                                      f"{reason} sell order failed to fill", **self._kwargs)

    def _record_outcome(self, pnl_pct: float, holding_days: int) -> None:
        """Completes Transaction B's atomic pair for exits (decision_events
        SELL + decision_outcome_events) -- this is what actually closes
        decision_state from OPEN to CLOSED, and is why check_fingerprint
        can safely be enabled now (Sprint 5), unlike Sprint 3."""
        ledger_ctx, symbol = self._args
        if ledger_ctx is None or ledger_ctx.trust_conn is None:
            return
        try:
            decision_id = outcomes.find_open_buy_decision_id(ledger_ctx.trust_conn, symbol)
            if decision_id is None:
                logger.warning(f"trust ledger outcome write skipped for {symbol}: no OPEN BUY decision found")
                return
            outcomes.write_decision_outcome_event(
                ledger_ctx.trust_conn, symbol, decision_id, _utc_now(), pnl_pct, holding_days,
            )
        except Exception as e:
            logger.warning(f"trust ledger outcome write failed for {symbol}: {e}")

    def reject(self, reason: str) -> None:
        record_exit_decision_safe(*self._args, "REJECT", "QUALIFIED_REJECTION", reason, **self._kwargs)

    def hold(self, reason: str = "no exit condition met") -> None:
        record_exit_decision_safe(*self._args, "HOLD", "QUALIFIED_REJECTION", reason, **self._kwargs)


def record_risk_evaluation_safe(
    trades_conn: sqlite3.Connection, trust_conn: sqlite3.Connection, risk: RiskManager,
    portfolio_value: float, sizing_base: float, cycle_deployed_notional: float,
) -> None:
    """Best-effort wrapper around bot.trust_ledger.risk.record_risk_evaluation
    -- keeps bot/main.py's call site to one line, matching the philosophy
    used everywhere else in this module."""
    try:
        risk_ledger.record_risk_evaluation(
            trades_conn, trust_conn, risk, portfolio_value, sizing_base, cycle_deployed_notional,
        )
    except Exception as e:
        logger.warning(f"trust ledger risk evaluation write failed: {e}")


def record_data_quality_safe(
    trust_conn: sqlite3.Connection, source: str, status: str, detail: str | None = None,
) -> None:
    """Best-effort wrapper around bot.trust_ledger.data_quality.record_data_quality_event
    -- same philosophy as record_risk_evaluation_safe above: a health-log write
    failure must never affect the caller it's reporting on."""
    try:
        data_quality.record_data_quality_event(trust_conn, source, status, detail)
    except Exception as e:
        logger.warning(f"trust ledger data quality write failed: {e}")
