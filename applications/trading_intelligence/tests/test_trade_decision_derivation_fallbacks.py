"""TASK 4 -- derivation hardening for NULL / malformed production rows.

10 of 19 production BUY rows predate the rationale/risk columns and carry
NULL there; some rows may carry blank or malformed ``feature_drivers``.
Every such row must still yield a valid, bounded ``DecisionDetailArea``
with no fabrication and no exception -- except an unparseable ``timestamp``,
which must surface as ``TradingIntelligenceReadError`` (never a fake
instant).
"""
import datetime

import pytest

from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.decision_view import DecisionState
from applications.trading_intelligence.projections.trade_decision_row import TradeDecisionRow
from applications.trading_intelligence.adapters import trade_decision_derivation as d

_TS = "2026-07-01T09:30:00"
_TS_DT = datetime.datetime(2026, 7, 1, 9, 30, 0)


def _row(**overrides):
    base = dict(
        trade_id=12, timestamp=_TS, symbol="AMD", action="BUY",
        ensemble_score=None, xgb_prob=None, lstm_prob=None,
        sentiment_score=None, macro_score=None, regime=None,
        stop_loss=None, take_profit=None, risk_reward_ratio=None,
        feature_drivers_raw=None, ai_reasoning=None,
    )
    base.update(overrides)
    return TradeDecisionRow(**base)


# A spread of production-like dirty rows. Each must derive cleanly.
_DIRTY_ROWS = {
    "all_null_optionals": _row(),
    "null_rationale_and_drivers_with_scores": _row(
        ensemble_score=0.55, xgb_prob=0.6, lstm_prob=0.5,
        sentiment_score=0.1, macro_score=0.4, regime="NORMAL",
    ),
    "empty_string_drivers": _row(ensemble_score=0.55, feature_drivers_raw=""),
    "whitespace_drivers": _row(ensemble_score=0.55, feature_drivers_raw="   \n\t "),
    "malformed_json_drivers": _row(ensemble_score=0.55, feature_drivers_raw='{"a": '),
    "json_empty_list_drivers": _row(ensemble_score=0.55, feature_drivers_raw="[]"),
    "json_empty_object_drivers": _row(ensemble_score=0.55, feature_drivers_raw="{}"),
    "json_null_drivers": _row(ensemble_score=0.55, feature_drivers_raw="null"),
    "json_scalar_drivers": _row(ensemble_score=0.55, feature_drivers_raw="42"),
    "all_zero_model_fields": _row(
        ensemble_score=0.0, xgb_prob=0.0, lstm_prob=0.0,
        sentiment_score=0.0, macro_score=0.0,
    ),
    "missing_ensemble_score_only": _row(
        ensemble_score=None, xgb_prob=0.61, lstm_prob=0.44,
        sentiment_score=0.0, macro_score=0.0, regime="BULL",
    ),
    "missing_regime": _row(ensemble_score=0.55, xgb_prob=0.6, regime=None),
    "regime_blank_string": _row(ensemble_score=0.55, regime="   "),
    "blank_ai_reasoning": _row(ensemble_score=0.55, ai_reasoning="   "),
    "rationale_only": _row(ai_reasoning="a plain sentence"),
}


@pytest.mark.parametrize("name", sorted(_DIRTY_ROWS))
def test_derivation_never_raises_and_stays_bounded(name):
    row = _DIRTY_ROWS[name]

    contract = d.to_decision_contract(row)
    evidence = d.to_evidence_entries(row)
    governance = d.to_governance_entries(row)
    approvals = d.to_approvals(row)
    audit = d.to_audit_entries(row)

    assert contract.status in DecisionState
    assert contract.status not in (
        DecisionState.GOVERNANCE_EVALUATED, DecisionState.APPROVAL_RECORDED,
    )
    assert contract.evidence_reference == ""
    assert contract.risk_reference == ""
    assert contract.approval_status is None
    assert isinstance(contract.confidence, float)
    assert contract.updated_at == _TS_DT

    assert len(evidence) <= d._MAX_EVIDENCE_ENTRIES
    assert len(governance) <= d._MAX_GOVERNANCE_ENTRIES
    assert len(audit) <= d._MAX_AUDIT_ENTRIES
    assert approvals == []

    # No fabricated content: a FEATURE_DRIVERS entry only ever appears for
    # genuinely parseable non-empty JSON.
    driver_entries = [e for e in evidence if e.evidence_type == "FEATURE_DRIVERS"]
    assert len(driver_entries) <= 1


def test_all_null_optionals_row_is_decision_created_with_no_evidence_or_governance():
    row = _DIRTY_ROWS["all_null_optionals"]
    assert d.to_decision_contract(row).status is DecisionState.DECISION_CREATED
    assert d.to_evidence_entries(row) == []
    assert d.to_governance_entries(row) == []
    assert d.to_audit_entries(row)[0].payload == {"symbol": "AMD", "action": "BUY"}


def test_all_zero_model_fields_still_yield_ensemble_evidence_and_governance():
    row = _DIRTY_ROWS["all_zero_model_fields"]
    evidence = d.to_evidence_entries(row)
    assert [e.evidence_type for e in evidence] == ["MODEL_ENSEMBLE"]
    assert evidence[0].data == {"ensemble": 0.0, "threshold": 0.52}
    assert len(d.to_governance_entries(row)) == 1  # ensemble_score is present (0.0)


def test_missing_ensemble_score_suppresses_governance_but_keeps_model_evidence():
    row = _DIRTY_ROWS["missing_ensemble_score_only"]
    assert d.to_governance_entries(row) == []
    model = d.to_evidence_entries(row)[0]
    assert model.evidence_type == "MODEL_ENSEMBLE"
    assert "ensemble" not in model.data
    assert model.data == {"xgb": 0.61, "lstm": 0.44, "regime": "BULL"}


def test_blank_regime_is_not_emitted_as_the_string_none_or_whitespace():
    row = _DIRTY_ROWS["regime_blank_string"]
    model = d.to_evidence_entries(row)[0]
    assert "regime" not in model.data


@pytest.mark.parametrize("bad_ts", ["", "not-a-date", "2026-13-40", "09:30", None])
def test_unparseable_timestamp_raises_for_every_deriving_function(bad_ts):
    row = _row(ensemble_score=0.55, timestamp=bad_ts)
    with pytest.raises(TradingIntelligenceReadError):
        d.to_decision_contract(row)
    with pytest.raises(TradingIntelligenceReadError):
        d.to_evidence_entries(row)
    with pytest.raises(TradingIntelligenceReadError):
        d.to_governance_entries(row)
    with pytest.raises(TradingIntelligenceReadError):
        d.to_audit_entries(row)


def test_a_table_of_mixed_rows_all_produce_valid_decision_states():
    rows = list(_DIRTY_ROWS.values())
    contracts = [d.to_decision_contract(r) for r in rows]
    assert all(c.status in DecisionState for c in contracts)
