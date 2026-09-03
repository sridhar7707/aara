"""Pure derivation: one :class:`TradeDecisionRow` -> the Decision Center
read-model types (``DecisionContract`` and the Detail-panel entry lists).

Every function here is deterministic and free of I/O -- no sqlite,
filesystem, network, or ``sentinel_engine`` import. ``json`` (stdlib) is
used only to parse the already-in-memory ``feature_drivers`` string, and a
parse failure never raises out of these functions.

Wave 1 mapping rules (locked -- see the Wave 1 decision record):

* ``confidence`` = ``ensemble_score`` verbatim (``0.0`` when the column was
  ``NULL`` -- ``DecisionContract.confidence`` is a non-optional float).
* ``status`` -- ``EVIDENCE_ATTACHED`` when the row carries model or feature
  evidence (a non-``NULL`` ``ensemble_score``, any non-zero model
  sub-score, or a parseable non-empty ``feature_drivers`` payload), else
  ``DECISION_CREATED``. ``GOVERNANCE_EVALUATED`` / ``APPROVAL_RECORDED``
  are NEVER emitted -- an autonomous bot trade has no governed approval
  lifecycle, and this module must not imply one.
* ``evidence_reference`` / ``risk_reference`` = ``""`` -- there is no real
  pointer to fabricate; the UI already renders an empty reference as
  "none".
* Governance -- a single ``BUY_THRESHOLD`` entry, and only when
  ``ensemble_score`` is present (the bot did apply the >= threshold gate
  before executing). No MACD / correlation / other gate is invented.
* Approvals -- always ``[]``.
* Audit -- a single ``DECISION_CREATED`` event; its payload keys are a
  subset of gradio_view.py's ``_AUDIT_PAYLOAD_ALLOWED_KEYS`` allowlist
  (kept in sync by test).
* ``ai_reasoning`` is surfaced ONLY as a bounded ``AI_RATIONALE`` evidence
  entry -- never as a governance/approval fact, never by restructuring the
  Why section.
* ``stop_loss`` / ``take_profit`` / ``risk_reward_ratio`` are NOT surfaced
  anywhere in Wave 1.

An unparseable ``timestamp`` raises :class:`TradingIntelligenceReadError`
rather than yielding a fabricated timeline instant -- the source/controller
path already treats that type as a read failure.
"""
import json
import logging
from datetime import datetime
from typing import Any, List, Optional

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionState
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.projections.trade_decision_row import TradeDecisionRow

logger = logging.getLogger(__name__)

# The model's current BUY decision threshold (bot configuration). Surfaced
# as evidence *context* only -- never recomputed or used to re-judge the
# trade here.
_BUY_THRESHOLD = 0.52

_EVIDENCE_SOURCE = "aara-bot"

# Bounded regardless of future column growth.
_MAX_EVIDENCE_ENTRIES = 4
_MAX_GOVERNANCE_ENTRIES = 2
_MAX_AUDIT_ENTRIES = 3

# Mirror of gradio_view.py's _AUDIT_PAYLOAD_ALLOWED_KEYS -- every key put on
# an AuditEntry.payload below must be in that allowlist. A test
# (test_trade_decision_derivation.py) asserts this stays a subset.
_AUDIT_PAYLOAD_ALLOWED_KEYS = frozenset({
    "symbol", "action", "confidence",
})

_MODEL_SUBSCORE_FIELDS = ("xgb_prob", "lstm_prob", "sentiment_score", "macro_score")
_MODEL_SUBSCORE_KEYS = {
    "xgb_prob": "xgb",
    "lstm_prob": "lstm",
    "sentiment_score": "sentiment",
    "macro_score": "macro",
}


def parse_timestamp(raw: str) -> datetime:
    """Parse a ``trades.timestamp`` string to a naive datetime (UTC by the
    bot's convention -- the whole read chain treats these as naive-UTC).
    Raises :class:`TradingIntelligenceReadError` for a value ISO parsing
    cannot handle."""
    try:
        return datetime.fromisoformat(str(raw))
    except (TypeError, ValueError) as exc:
        raise TradingIntelligenceReadError(
            f"trades row has an unparseable timestamp: {raw!r}"
        ) from exc


def _parsed_feature_drivers(row: TradeDecisionRow) -> Optional[Any]:
    """The ``feature_drivers`` string parsed to a non-empty dict/list, or
    ``None`` (missing, blank, malformed, ``null``, ``{}``, ``[]``). Never
    raises."""
    raw = row.feature_drivers_raw
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        logger.debug("feature_drivers not valid JSON for %s", row.decision_id)
        return None
    if isinstance(parsed, (dict, list)) and len(parsed) > 0:
        return parsed
    return None


def _has_model_or_feature_evidence(row: TradeDecisionRow) -> bool:
    if row.ensemble_score is not None:
        return True
    for field in _MODEL_SUBSCORE_FIELDS:
        value = getattr(row, field)
        if value is not None and value != 0.0:
            return True
    return _parsed_feature_drivers(row) is not None


def _ai_reasoning_text(row: TradeDecisionRow) -> Optional[str]:
    if row.ai_reasoning is None:
        return None
    text = str(row.ai_reasoning).strip()
    return text or None


def to_decision_contract(row: TradeDecisionRow) -> DecisionContract:
    status = (
        DecisionState.EVIDENCE_ATTACHED
        if _has_model_or_feature_evidence(row)
        else DecisionState.DECISION_CREATED
    )
    return DecisionContract(
        decision_id=row.decision_id,
        symbol=row.symbol,
        action=row.action,
        status=status,
        confidence=row.ensemble_score if row.ensemble_score is not None else 0.0,
        evidence_reference="",
        risk_reference="",
        updated_at=parse_timestamp(row.timestamp),
        approval_status=None,
    )


def _model_ensemble_data(row: TradeDecisionRow) -> dict:
    data: dict = {}
    if row.ensemble_score is not None:
        data["ensemble"] = row.ensemble_score
        data["threshold"] = _BUY_THRESHOLD
    for field, key in _MODEL_SUBSCORE_KEYS.items():
        value = getattr(row, field)
        if value is not None and value != 0.0:
            data[key] = value
    if row.regime is not None and str(row.regime).strip():
        data["regime"] = row.regime
    return data


def to_evidence_entries(row: TradeDecisionRow) -> List[EvidenceEntry]:
    """At most one entry each of MODEL_ENSEMBLE / FEATURE_DRIVERS /
    AI_RATIONALE, in that order, omitting any with no real content.
    Bounded at ``_MAX_EVIDENCE_ENTRIES``."""
    attached_at = parse_timestamp(row.timestamp)
    entries: List[EvidenceEntry] = []

    model_data = _model_ensemble_data(row)
    if model_data:
        entries.append(EvidenceEntry(
            evidence_id=f"{row.decision_id}-model",
            evidence_type="MODEL_ENSEMBLE",
            source=_EVIDENCE_SOURCE,
            attached_at=attached_at,
            data=model_data,
        ))

    drivers = _parsed_feature_drivers(row)
    if drivers is not None:
        entries.append(EvidenceEntry(
            evidence_id=f"{row.decision_id}-drivers",
            evidence_type="FEATURE_DRIVERS",
            source=_EVIDENCE_SOURCE,
            attached_at=attached_at,
            data={"drivers": drivers},
        ))

    rationale = _ai_reasoning_text(row)
    if rationale is not None:
        entries.append(EvidenceEntry(
            evidence_id=f"{row.decision_id}-rationale",
            evidence_type="AI_RATIONALE",
            source=_EVIDENCE_SOURCE,
            attached_at=attached_at,
            data={"text": rationale},
        ))

    return entries[:_MAX_EVIDENCE_ENTRIES]


def to_governance_entries(row: TradeDecisionRow) -> List[GovernanceEntry]:
    """A single ``BUY_THRESHOLD`` entry, only when ``ensemble_score`` is
    present. No other gate is invented. Bounded at
    ``_MAX_GOVERNANCE_ENTRIES``."""
    if row.ensemble_score is None:
        return []
    return [GovernanceEntry(
        policy_id="BUY_THRESHOLD",
        enabled=True,
        evaluated_at=parse_timestamp(row.timestamp),
    )][:_MAX_GOVERNANCE_ENTRIES]


def to_approvals(row: TradeDecisionRow) -> List[ApprovalEntry]:
    """Always empty -- an autonomous bot trade records no human approval."""
    return []


def to_audit_entries(row: TradeDecisionRow) -> List[AuditEntry]:
    """A single ``DECISION_CREATED`` event. Payload keys are a subset of
    gradio_view.py's ``_AUDIT_PAYLOAD_ALLOWED_KEYS``. Bounded at
    ``_MAX_AUDIT_ENTRIES``."""
    payload: dict = {"symbol": row.symbol, "action": row.action}
    if row.ensemble_score is not None:
        payload["confidence"] = row.ensemble_score
    assert set(payload).issubset(_AUDIT_PAYLOAD_ALLOWED_KEYS)
    return [AuditEntry(
        event_id=f"{row.decision_id}-created",
        event_type="DECISION_CREATED",
        created_at=parse_timestamp(row.timestamp),
        payload=payload,
    )][:_MAX_AUDIT_ENTRIES]
