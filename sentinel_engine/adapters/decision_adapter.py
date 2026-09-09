"""Translation boundary between existing bot concepts and the Sentinel
Decision contract.

Takes plain data (the shape bot code will eventually pass in), never a bot
type, so this module has zero import dependency on bot/. All fields are
validated here because this is a system boundary.

Batch 2 (per docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md):
`action` is now validated against DecisionAction's fixed five-value
vocabulary -- this is "the appropriate boundary" the P0 contract asks for;
Decision itself stays a trusting domain object, matching every other field
here. The six new optional Decision fields are validated only when present
in the input, and are otherwise omitted so Decision falls back to its own
defaults -- this adapter never invents a value for them.

ADR-069 (B2): `action_source`, when present, is validated against the fixed
ActionSource vocabulary ("STRATEGY" / "SENTINEL"), the same boundary
treatment `action` gets. Absent or None -> omitted, so Decision keeps its
own `None` default (legacy / unknown provenance).
"""
from datetime import datetime

from sentinel_engine.domain.action_source import ActionSource
from sentinel_engine.domain.decision import Decision
from sentinel_engine.domain.decision_action import DecisionAction

_REQUIRED_FIELDS = (
    "decision_id",
    "symbol",
    "action",
    "timestamp",
    "confidence",
    "evidence_reference",
    "risk_reference",
)

_OPTIONAL_STRING_FIELDS = ("horizon", "thesis", "counterfactual")
_OPTIONAL_NUMERIC_FIELDS = ("desired_allocation", "minimum_viable_allocation", "uncertainty")


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
    if not DecisionAction.has_value(action):
        allowed = ", ".join(member.value for member in DecisionAction)
        raise ValueError(f"action must be one of ({allowed}), got {action!r}")
    if not isinstance(timestamp, datetime):
        raise ValueError("timestamp must be a datetime instance")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("confidence must be numeric")
    if not isinstance(evidence_reference, str) or not evidence_reference:
        raise ValueError("evidence_reference must be a non-empty string")
    if not isinstance(risk_reference, str) or not risk_reference:
        raise ValueError("risk_reference must be a non-empty string")

    optional_kwargs = {}

    for field in _OPTIONAL_STRING_FIELDS:
        if field in data and data[field] is not None:
            value = data[field]
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field} must be a non-empty string when provided")
            optional_kwargs[field] = value

    for field in _OPTIONAL_NUMERIC_FIELDS:
        if field in data and data[field] is not None:
            value = data[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{field} must be numeric when provided")
            optional_kwargs[field] = float(value)

    if data.get("action_source") is not None:
        action_source = data["action_source"]
        if not isinstance(action_source, str) or not ActionSource.has_value(action_source):
            allowed = ", ".join(member.value for member in ActionSource)
            raise ValueError(
                f"action_source must be one of ({allowed}) when provided, got {action_source!r}"
            )
        optional_kwargs["action_source"] = action_source

    return Decision(
        decision_id=decision_id,
        symbol=symbol,
        action=action,
        timestamp=timestamp,
        confidence=float(confidence),
        evidence_reference=evidence_reference,
        risk_reference=risk_reference,
        **optional_kwargs,
    )
