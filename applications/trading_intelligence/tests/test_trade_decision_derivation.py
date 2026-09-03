"""Tests for applications.trading_intelligence.adapters.trade_decision_derivation.

All functions under test are pure -- these tests never touch a database.
"""
import ast
import datetime
import inspect

import pytest

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionState
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.projections.trade_decision_row import TradeDecisionRow
from applications.trading_intelligence.adapters import trade_decision_derivation as d

_TS = "2026-09-02T14:39:08"
_TS_DT = datetime.datetime(2026, 9, 2, 14, 39, 8)
_FEATURE_DRIVERS = '{"momentum": 0.41, "trend": "up"}'
_AI_REASONING = "Ensemble cleared the BUY threshold on strengthening momentum."


def _row(**overrides):
    base = dict(
        trade_id=45, timestamp=_TS, symbol="SLB", action="BUY",
        ensemble_score=0.5222, xgb_prob=0.5385, lstm_prob=0.4375,
        sentiment_score=0.0936, macro_score=0.6403, regime="HIGH_VOLATILITY",
        stop_loss=53.2437, take_profit=65.1426, risk_reward_ratio=2.0,
        feature_drivers_raw=_FEATURE_DRIVERS, ai_reasoning=_AI_REASONING,
    )
    base.update(overrides)
    return TradeDecisionRow(**base)


# --------------------------------------------------------------------------
# to_decision_contract
# --------------------------------------------------------------------------

def test_to_decision_contract_maps_trade_45():
    contract = d.to_decision_contract(_row())

    assert contract == DecisionContract(
        decision_id="trade-45",
        symbol="SLB",
        action="BUY",
        status=DecisionState.EVIDENCE_ATTACHED,
        confidence=0.5222,
        evidence_reference="",
        risk_reference="",
        updated_at=_TS_DT,
        approval_status=None,
    )


def test_to_decision_contract_status_is_a_decision_state_member():
    assert d.to_decision_contract(_row()).status in DecisionState


def test_to_decision_contract_no_evidence_is_decision_created_confidence_zero():
    contract = d.to_decision_contract(_row(
        ensemble_score=None, xgb_prob=None, lstm_prob=None,
        sentiment_score=None, macro_score=None, regime=None,
        feature_drivers_raw=None, ai_reasoning=None,
    ))
    assert contract.status is DecisionState.DECISION_CREATED
    assert contract.confidence == 0.0


def test_to_decision_contract_ai_reasoning_alone_does_not_flip_status():
    contract = d.to_decision_contract(_row(
        ensemble_score=None, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw=None, ai_reasoning="some narrative",
    ))
    assert contract.status is DecisionState.DECISION_CREATED


def test_to_decision_contract_feature_drivers_alone_flips_status():
    contract = d.to_decision_contract(_row(
        ensemble_score=None, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw='{"a": 1}', ai_reasoning=None,
    ))
    assert contract.status is DecisionState.EVIDENCE_ATTACHED


def test_to_decision_contract_nonzero_subscore_alone_flips_status():
    contract = d.to_decision_contract(_row(
        ensemble_score=None, xgb_prob=0.61, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw=None, ai_reasoning=None,
    ))
    assert contract.status is DecisionState.EVIDENCE_ATTACHED


def test_to_decision_contract_never_emits_governance_or_approval_states():
    for row in (
        _row(),
        _row(ensemble_score=None, feature_drivers_raw=None, ai_reasoning=None,
             xgb_prob=None, lstm_prob=None, sentiment_score=None, macro_score=None),
    ):
        assert d.to_decision_contract(row).status not in (
            DecisionState.GOVERNANCE_EVALUATED, DecisionState.APPROVAL_RECORDED,
        )


def test_to_decision_contract_is_deterministic():
    row = _row()
    assert d.to_decision_contract(row) == d.to_decision_contract(row)


def test_to_decision_contract_raises_on_unparseable_timestamp():
    with pytest.raises(TradingIntelligenceReadError):
        d.to_decision_contract(_row(timestamp="not-a-timestamp"))


def test_to_decision_contract_accepts_space_separated_timestamp():
    contract = d.to_decision_contract(_row(timestamp="2026-09-02 14:39:08"))
    assert contract.updated_at == _TS_DT


# --------------------------------------------------------------------------
# to_evidence_entries
# --------------------------------------------------------------------------

def test_to_evidence_entries_trade_45_has_three_ordered_entries():
    entries = d.to_evidence_entries(_row())

    assert [e.evidence_type for e in entries] == [
        "MODEL_ENSEMBLE", "FEATURE_DRIVERS", "AI_RATIONALE",
    ]
    assert [e.evidence_id for e in entries] == [
        "trade-45-model", "trade-45-drivers", "trade-45-rationale",
    ]
    assert all(e.source == "aara-bot" for e in entries)
    assert all(e.attached_at == _TS_DT for e in entries)


def test_to_evidence_entries_model_ensemble_data():
    model = d.to_evidence_entries(_row())[0]
    assert model.data == {
        "ensemble": 0.5222,
        "threshold": 0.52,
        "xgb": 0.5385,
        "lstm": 0.4375,
        "sentiment": 0.0936,
        "macro": 0.6403,
        "regime": "HIGH_VOLATILITY",
    }


def test_to_evidence_entries_feature_drivers_and_rationale_payloads():
    entries = d.to_evidence_entries(_row())
    assert entries[1].data == {"drivers": {"momentum": 0.41, "trend": "up"}}
    assert entries[2].data == {"text": _AI_REASONING}


def test_to_evidence_entries_drops_zero_subscores_keeps_ensemble():
    model = d.to_evidence_entries(_row(
        xgb_prob=0.0, lstm_prob=0.0, sentiment_score=0.0, macro_score=0.0,
        regime=None, feature_drivers_raw=None, ai_reasoning=None,
    ))[0]
    assert model.data == {"ensemble": 0.5222, "threshold": 0.52}


def test_to_evidence_entries_no_model_ensemble_entry_when_nothing_numeric():
    entries = d.to_evidence_entries(_row(
        ensemble_score=None, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw=None, ai_reasoning=None,
    ))
    assert entries == []


@pytest.mark.parametrize("bad", ['{"a": 1', "[]", "{}", "null", "   ", "", None])
def test_to_evidence_entries_no_feature_entry_for_empty_or_malformed_json(bad):
    entries = d.to_evidence_entries(_row(
        ensemble_score=None, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw=bad, ai_reasoning=None,
    ))
    assert entries == []


@pytest.mark.parametrize("blank", ["", "   ", "\n\t", None])
def test_to_evidence_entries_no_rationale_entry_for_blank_ai_reasoning(blank):
    entries = d.to_evidence_entries(_row(
        ensemble_score=None, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw=None, ai_reasoning=blank,
    ))
    assert entries == []


def test_to_evidence_entries_bounded_at_four():
    assert len(d.to_evidence_entries(_row())) <= 4


def test_to_evidence_entries_json_list_drivers_supported():
    entries = d.to_evidence_entries(_row(
        ensemble_score=None, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0, regime=None,
        feature_drivers_raw='["a", "b"]', ai_reasoning=None,
    ))
    assert entries[0].evidence_type == "FEATURE_DRIVERS"
    assert entries[0].data == {"drivers": ["a", "b"]}


# --------------------------------------------------------------------------
# to_governance_entries / to_approvals
# --------------------------------------------------------------------------

def test_to_governance_entries_buy_threshold_when_ensemble_present():
    entries = d.to_governance_entries(_row())
    assert entries == [GovernanceEntry(
        policy_id="BUY_THRESHOLD", enabled=True, evaluated_at=_TS_DT,
    )]


def test_to_governance_entries_empty_when_no_ensemble_score():
    assert d.to_governance_entries(_row(ensemble_score=None)) == []


def test_to_governance_entries_bounded_at_two():
    assert len(d.to_governance_entries(_row())) <= 2


def test_to_approvals_is_always_empty():
    assert d.to_approvals(_row()) == []
    assert d.to_approvals(_row(ensemble_score=None)) == []
    assert isinstance(d.to_approvals(_row()), list)
    for entry in d.to_approvals(_row()):  # pragma: no cover - never runs
        assert isinstance(entry, ApprovalEntry)


# --------------------------------------------------------------------------
# to_audit_entries
# --------------------------------------------------------------------------

def test_to_audit_entries_single_decision_created_event():
    entries = d.to_audit_entries(_row())
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, AuditEntry)
    assert entry.event_id == "trade-45-created"
    assert entry.event_type == "DECISION_CREATED"
    assert entry.created_at == _TS_DT
    assert entry.payload == {"symbol": "SLB", "action": "BUY", "confidence": 0.5222}


def test_to_audit_entries_omits_confidence_when_ensemble_missing():
    entry = d.to_audit_entries(_row(ensemble_score=None))[0]
    assert entry.payload == {"symbol": "SLB", "action": "BUY"}
    assert "confidence" not in entry.payload


def test_to_audit_entries_payload_never_carries_decision_id():
    assert "decision_id" not in d.to_audit_entries(_row())[0].payload


def test_to_audit_entries_bounded_at_three():
    assert len(d.to_audit_entries(_row())) <= 3


def test_audit_payload_keys_are_a_subset_of_the_gradio_view_allowlist():
    from applications.trading_intelligence.ui.decision_center.gradio_view import (
        _AUDIT_PAYLOAD_ALLOWED_KEYS as view_allowlist,
    )
    assert d._AUDIT_PAYLOAD_ALLOWED_KEYS.issubset(view_allowlist)


# --------------------------------------------------------------------------
# purity
# --------------------------------------------------------------------------

def test_module_has_no_io_imports():
    module = inspect.getsource(d)
    tree = ast.parse(module)
    forbidden = (
        "sqlite3", "socket", "requests", "httpx", "urllib", "pathlib",
        "os", "shutil", "subprocess", "sentinel_engine", "bot", "dashboard",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), f"forbidden import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(forbidden), (
                f"forbidden import from {module_name!r}"
            )
