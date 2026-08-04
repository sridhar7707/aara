"""Translation boundary between existing bot concepts and the Sentinel
Decision contract.

Takes plain data (the shape bot code will eventually pass in), never a bot
type, so this module has zero import dependency on bot/. All fields are
validated here because this is a system boundary.
"""
from datetime import datetime

from sentinel_engine.domain.decision import Decision

_REQUIRED_FIELDS = (
    "decision_id",
    "symbol",
    "action",
    "timestamp",
    "confidence",
    "evidence_reference",
    "risk_reference",
)


def to_decision(data: dict) -> Decision:
    missing = [field for field in _REQUIRED_FIELDS if field not in data]
    if missing:
        raise ValueError(f"Missing required field(s) for Decision: {', '.join(missing)}")

    decision_id = data["decision_id"]
    symbol = data["symbol"]
    action = data["action"]
    timestamp = data["timestamp"]
    confidence = data["confidence"]
    evidence_reference = data["evidence_reference"]
    risk_reference = data["risk_reference"]

    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("decision_id must be a non-empty string")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("symbol must be a non-empty string")
    if not isinstance(action, str) or not action:
        raise ValueError("action must be a non-empty string")
    if not isinstance(timestamp, datetime):
        raise ValueError("timestamp must be a datetime instance")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("confidence must be numeric")
    if not isinstance(evidence_reference, str) or not evidence_reference:
        raise ValueError("evidence_reference must be a non-empty string")
    if not isinstance(risk_reference, str) or not risk_reference:
        raise ValueError("risk_reference must be a non-empty string")

    return Decision(
        decision_id=decision_id,
        symbol=symbol,
        action=action,
        timestamp=timestamp,
        confidence=float(confidence),
        evidence_reference=evidence_reference,
        risk_reference=risk_reference,
    )
