"""Tests for sentinel_engine.adapters.governance_adapter (ADR-014)."""
import ast
import datetime
import inspect

import pytest

from sentinel_engine.adapters import governance_adapter
from sentinel_engine.adapters.governance_adapter import to_approval, to_policy_id
from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus


def _valid_decision_row(**overrides):
    defaults = {
        "decision_id": "dec-001",
        "candidate_event_id": "cand-001",
        "timestamp": "2026-08-12T12:00:00+00:00",
        "asset": "AAPL",
        "action": "BUY",
        "event_type": "EXECUTED",
        "portfolio_snapshot": {"portfolio_value": 10000.0, "available_cash": 5000.0},
        "market_context": {"regime": "bull"},
        "model_outputs": {
            "xgboost": {"signal": "BUY", "confidence": 0.78, "metadata": {}},
            "lstm": {"signal": "HOLD", "confidence": 0.51, "metadata": {}},
            "finbert": {"signal": "SELL", "confidence": 0.3, "metadata": {}},
        },
        "risk_checks": {},
        "final_confidence": 0.7,
        "deployment_manifest_id": "manifest-001",
        "intent": {"primary_intent": "OPPORTUNITY_ENTRY", "contributing_modules": []},
        "data_completeness": {"status": "COMPLETE", "missing_inputs": [], "stale_inputs": []},
        "record_hash": "hash-001",
        "previous_record_hash": None,
        "sequence_number": 1,
    }
    defaults.update(overrides)
    return defaults


# --- to_policy_id ------------------------------------------------------


def test_to_policy_id_is_deterministic_for_same_decision_row():
    decision_row = _valid_decision_row()

    assert to_policy_id(decision_row) == to_policy_id(decision_row)


def test_to_policy_id_derives_from_action():
    assert to_policy_id(_valid_decision_row(action="BUY")) == "phase1a-buy"
    assert to_policy_id(_valid_decision_row(action="SELL")) == "phase1a-sell"
    assert to_policy_id(_valid_decision_row(action="HOLD")) == "phase1a-hold"
    assert to_policy_id(_valid_decision_row(action="REJECT")) == "phase1a-reject"


def test_to_policy_id_returns_a_str():
    result = to_policy_id(_valid_decision_row())

    assert isinstance(result, str)


def test_to_policy_id_rejects_missing_action():
    decision_row = _valid_decision_row()
    del decision_row["action"]

    with pytest.raises(ValueError):
        to_policy_id(decision_row)


@pytest.mark.parametrize("bad_action", ["", None, 123])
def test_to_policy_id_rejects_malformed_action(bad_action):
    decision_row = _valid_decision_row(action=bad_action)

    with pytest.raises(ValueError):
        to_policy_id(decision_row)


def test_to_policy_id_rejects_non_dict_input():
    with pytest.raises(ValueError):
        to_policy_id(["not", "a", "dict"])


def test_to_policy_id_ignores_additional_decision_row_keys():
    decision_row = _valid_decision_row(unexpected_field="anything")

    assert to_policy_id(decision_row) == "phase1a-buy"


# --- to_approval ---------------------------------------------------------


def test_to_approval_returns_an_approval_instance():
    result = to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine")

    assert isinstance(result, Approval)


def test_to_approval_preserves_decision_id_exactly():
    decision_row = _valid_decision_row(decision_id="dec-xyz-999")

    result = to_approval(decision_row, ApprovalStatus.APPROVED, "autonomous_phase1a_engine")

    assert result.decision_id == "dec-xyz-999"


def test_to_approval_preserves_supplied_status():
    approved = to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine")
    rejected = to_approval(_valid_decision_row(), ApprovalStatus.REJECTED, "autonomous_phase1a_engine")

    assert approved.status == ApprovalStatus.APPROVED
    assert rejected.status == ApprovalStatus.REJECTED


def test_to_approval_preserves_supplied_approved_by():
    result = to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine")

    assert result.approved_by == "autonomous_phase1a_engine"


def test_to_approval_never_defaults_approved_by_to_a_human_role_value():
    """ADR-014 Section 5: the adapter must never silently choose a
    provenance value -- approved_by has no default at all."""
    signature = inspect.signature(to_approval)

    assert signature.parameters["approved_by"].default is inspect.Parameter.empty


@pytest.mark.parametrize("human_role_value", ["risk_officer", "cro"])
def test_to_approval_rejects_existing_human_role_approved_by_values(human_role_value):
    with pytest.raises(ValueError):
        to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, human_role_value)


@pytest.mark.parametrize("bad_approved_by", ["", None])
def test_to_approval_rejects_malformed_approved_by(bad_approved_by):
    with pytest.raises(ValueError):
        to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, bad_approved_by)


def test_to_approval_rejects_non_approval_status_status():
    with pytest.raises(ValueError):
        to_approval(_valid_decision_row(), "APPROVED", "autonomous_phase1a_engine")


def test_to_approval_rejects_missing_decision_id():
    decision_row = _valid_decision_row()
    del decision_row["decision_id"]

    with pytest.raises(ValueError):
        to_approval(decision_row, ApprovalStatus.APPROVED, "autonomous_phase1a_engine")


@pytest.mark.parametrize("bad_decision_id", ["", None, 123])
def test_to_approval_rejects_malformed_decision_id(bad_decision_id):
    decision_row = _valid_decision_row(decision_id=bad_decision_id)

    with pytest.raises(ValueError):
        to_approval(decision_row, ApprovalStatus.APPROVED, "autonomous_phase1a_engine")


def test_to_approval_rejects_non_dict_decision_row():
    with pytest.raises(ValueError):
        to_approval(["not", "a", "dict"], ApprovalStatus.APPROVED, "autonomous_phase1a_engine")


def test_to_approval_generates_a_unique_approval_id_when_not_supplied():
    first = to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine")
    second = to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine")

    assert first.approval_id != second.approval_id


def test_to_approval_accepts_a_caller_supplied_approval_id():
    result = to_approval(
        _valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine",
        approval_id="approval-001",
    )

    assert result.approval_id == "approval-001"


@pytest.mark.parametrize("bad_approval_id", ["", 123])
def test_to_approval_rejects_malformed_approval_id(bad_approval_id):
    with pytest.raises(ValueError):
        to_approval(
            _valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine",
            approval_id=bad_approval_id,
        )


def test_to_approval_timestamp_defaults_to_timezone_aware_utc():
    result = to_approval(_valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine")

    assert result.timestamp.tzinfo is not None
    assert result.timestamp.tzinfo.utcoffset(result.timestamp) == datetime.timedelta(0)


def test_to_approval_accepts_a_caller_supplied_timezone_aware_timestamp():
    supplied = datetime.datetime(2026, 8, 12, 9, 30, tzinfo=datetime.timezone.utc)

    result = to_approval(
        _valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine",
        timestamp=supplied,
    )

    assert result.timestamp == supplied


def test_to_approval_rejects_naive_timestamp():
    naive = datetime.datetime(2026, 8, 12, 9, 30)

    with pytest.raises(ValueError):
        to_approval(
            _valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine",
            timestamp=naive,
        )


def test_to_approval_rejects_non_datetime_timestamp():
    with pytest.raises(ValueError):
        to_approval(
            _valid_decision_row(), ApprovalStatus.APPROVED, "autonomous_phase1a_engine",
            timestamp="2026-08-12T09:30:00+00:00",
        )


def test_to_approval_ignores_additional_decision_row_keys():
    decision_row = _valid_decision_row(unexpected_field="anything")

    result = to_approval(decision_row, ApprovalStatus.APPROVED, "autonomous_phase1a_engine")

    assert result.decision_id == decision_row["decision_id"]


# --- ADR-014 architectural boundaries -------------------------------------


def test_governance_adapter_module_does_not_import_bot():
    source = inspect.getsource(governance_adapter)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("bot")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("bot")


def test_governance_adapter_module_does_not_import_governance_service():
    source = inspect.getsource(governance_adapter)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "governance_service" not in module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "governance_service" not in alias.name


def test_governance_adapter_module_does_not_import_database_or_dashboard():
    source = inspect.getsource(governance_adapter)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("database")
                assert not alias.name.startswith("dashboard")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("database")
            assert not module.startswith("dashboard")


def test_governance_adapter_module_does_not_construct_policy():
    """ADR-014 Section 4: the adapter produces a policy_id string only --
    it must never construct/register an actual Policy domain object."""
    source = inspect.getsource(governance_adapter)

    assert "Policy(" not in source
