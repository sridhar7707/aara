"""Translation boundary between bot's existing, unmodified
RiskManager/PaperExecutor execution path and the Sentinel Engine
DECISION_EXECUTED event representation (ADR-065).

Takes plain data -- the outcome bot/_main_cycle.py::_handle_entry() already
computes after risk.approve_buy() and client.buy() run, correlated back to
the existing Trust Ledger decision_id -- never a bot type, so this module
has zero import dependency on bot/. All fields are validated here because
this is a system boundary.

Per ADR-065 SS3.1, a single outcome representation (this module's
"outcome" field: FILLED / REJECTED / FAILED) is reused for all three cases
rather than inventing separate DecisionState members or EventType values
for rejection/failure -- the distinction lives in the payload, not the
vocabulary.

This adapter never calls DecisionService, never appends an event, and
never persists anything -- it only validates and shapes plain data for a
future caller (DecisionService.record_execution()) to consume.
"""
from datetime import datetime
from typing import Optional

_VALID_OUTCOMES = frozenset({"FILLED", "REJECTED", "FAILED"})


def to_execution_outcome(execution: dict) -> dict:
    """ADR-065: validates and returns a plain payload dict representing a
    completed execution attempt's outcome, ready for
    DecisionService.record_execution(decision_id, payload).

    Required keys: decision_id, symbol, action, side, outcome, is_paper,
    timestamp.
    Optional keys (validated only when present): notional, quantity,
    fill_price, order_id, reason.
    """
    if not isinstance(execution, dict):
        raise ValueError("execution must be a dict")

    decision_id = execution.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("execution['decision_id'] must be a non-empty string")

    symbol = execution.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("execution['symbol'] must be a non-empty string")

    action = execution.get("action")
    if not isinstance(action, str) or not action:
        raise ValueError("execution['action'] must be a non-empty string")

    side = execution.get("side")
    if not isinstance(side, str) or not side:
        raise ValueError("execution['side'] must be a non-empty string")

    outcome = execution.get("outcome")
    if outcome not in _VALID_OUTCOMES:
        raise ValueError(
            f"execution['outcome'] must be one of {sorted(_VALID_OUTCOMES)}, "
            f"got {outcome!r}"
        )

    is_paper = execution.get("is_paper")
    if not isinstance(is_paper, bool):
        raise ValueError("execution['is_paper'] must be a bool")

    timestamp = execution.get("timestamp")
    if not isinstance(timestamp, datetime):
        raise ValueError("execution['timestamp'] must be a datetime instance")
    if timestamp.tzinfo is None:
        raise ValueError("execution['timestamp'] must be timezone-aware")

    payload = {
        "decision_id": decision_id,
        "symbol": symbol,
        "action": action,
        "side": side,
        "outcome": outcome,
        "is_paper": is_paper,
        "timestamp": timestamp,
    }

    notional: Optional[object] = execution.get("notional")
    if notional is not None:
        if not isinstance(notional, (int, float)) or isinstance(notional, bool):
            raise ValueError("execution['notional'] must be numeric when present")
        payload["notional"] = notional

    quantity: Optional[object] = execution.get("quantity")
    if quantity is not None:
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool):
            raise ValueError("execution['quantity'] must be numeric when present")
        payload["quantity"] = quantity

    fill_price: Optional[object] = execution.get("fill_price")
    if fill_price is not None:
        if not isinstance(fill_price, (int, float)) or isinstance(fill_price, bool):
            raise ValueError("execution['fill_price'] must be numeric when present")
        payload["fill_price"] = fill_price

    order_id = execution.get("order_id")
    if order_id is not None:
        if not isinstance(order_id, str) or not order_id:
            raise ValueError("execution['order_id'] must be a non-empty string when present")
        payload["order_id"] = order_id

    reason = execution.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or not reason:
            raise ValueError("execution['reason'] must be a non-empty string when present")
        payload["reason"] = reason

    return payload
