"""Tests for sentinel_engine.adapters.decision_adapter."""
import ast
import datetime
import inspect

import pytest

from sentinel_engine.adapters import decision_adapter
from sentinel_engine.adapters.decision_adapter import to_decision
from sentinel_engine.domain.decision import Decision


def _valid_input(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
    )
    defaults.update(overrides)
    return defaults


def test_to_decision_converts_valid_input_into_a_decision():
    result = to_decision(_valid_input())

    assert isinstance(result, Decision)


def test_to_decision_maps_required_fields_correctly():
    result = to_decision(_valid_input())

    assert result.decision_id == "dec-001"
    assert result.symbol == "AAPL"
    assert result.action == "BUY"
    assert result.timestamp == datetime.datetime(2026, 8, 4, 12, 0, 0)
    assert result.confidence == 0.78
    assert result.evidence_reference == "evidence-001"
    assert result.risk_reference == "risk-001"


@pytest.mark.parametrize("missing_field", [
    "decision_id", "symbol", "action", "timestamp",
    "confidence", "evidence_reference", "risk_reference",
])
def test_to_decision_rejects_input_missing_a_required_field(missing_field):
    data = _valid_input()
    del data[missing_field]

    with pytest.raises(ValueError):
        to_decision(data)


def test_to_decision_rejects_non_numeric_confidence():
    data = _valid_input(confidence="high")

    with pytest.raises(ValueError):
        to_decision(data)


def test_to_decision_rejects_non_datetime_timestamp():
    data = _valid_input(timestamp="2026-08-04")

    with pytest.raises(ValueError):
        to_decision(data)


def test_to_decision_rejects_empty_symbol():
    data = _valid_input(symbol="")

    with pytest.raises(ValueError):
        to_decision(data)


def test_decision_adapter_module_does_not_import_bot():
    source = inspect.getsource(decision_adapter)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("bot")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("bot")
