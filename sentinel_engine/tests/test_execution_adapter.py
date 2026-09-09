"""Tests for sentinel_engine.adapters.execution_adapter (ADR-065)."""
import datetime

import pytest

from sentinel_engine.adapters.execution_adapter import to_execution_outcome

_TS = datetime.datetime(2026, 9, 4, 14, 30, 0, tzinfo=datetime.timezone.utc)


def _base(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        side="buy",
        outcome="FILLED",
        is_paper=True,
        timestamp=_TS,
    )
    defaults.update(overrides)
    return defaults


def test_valid_filled_execution_translates_all_required_fields():
    payload = to_execution_outcome(_base(
        notional=1000.0, quantity=5.2, fill_price=192.31, order_id="ord-1",
    ))

    assert payload["decision_id"] == "dec-001"
    assert payload["symbol"] == "AAPL"
    assert payload["action"] == "BUY"
    assert payload["side"] == "buy"
    assert payload["outcome"] == "FILLED"
    assert payload["is_paper"] is True
    assert payload["timestamp"] == _TS
    assert payload["notional"] == 1000.0
    assert payload["quantity"] == 5.2
    assert payload["fill_price"] == 192.31
    assert payload["order_id"] == "ord-1"


def test_valid_rejected_execution_omits_absent_optional_fields():
    payload = to_execution_outcome(_base(outcome="REJECTED", reason="risk.approve_buy() declined"))

    assert payload["outcome"] == "REJECTED"
    assert payload["reason"] == "risk.approve_buy() declined"
    assert "fill_price" not in payload
    assert "order_id" not in payload


def test_valid_failed_execution():
    payload = to_execution_outcome(_base(outcome="FAILED", reason="order never filled"))
    assert payload["outcome"] == "FAILED"
    assert payload["reason"] == "order never filled"


@pytest.mark.parametrize("field", ["decision_id", "symbol", "action", "side"])
def test_missing_required_string_field_is_rejected(field):
    execution = _base()
    del execution[field]
    with pytest.raises(ValueError, match=field):
        to_execution_outcome(execution)


def test_invalid_outcome_value_is_rejected():
    with pytest.raises(ValueError, match="outcome"):
        to_execution_outcome(_base(outcome="MAYBE"))


def test_non_bool_is_paper_is_rejected():
    with pytest.raises(ValueError, match="is_paper"):
        to_execution_outcome(_base(is_paper="yes"))


def test_missing_timestamp_is_rejected():
    execution = _base()
    del execution["timestamp"]
    with pytest.raises(ValueError, match="timestamp"):
        to_execution_outcome(execution)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        to_execution_outcome(_base(timestamp=datetime.datetime(2026, 9, 4, 14, 30, 0)))


def test_non_numeric_notional_is_rejected():
    with pytest.raises(ValueError, match="notional"):
        to_execution_outcome(_base(notional="a lot"))


def test_non_numeric_fill_price_is_rejected():
    with pytest.raises(ValueError, match="fill_price"):
        to_execution_outcome(_base(fill_price="oops"))


def test_execution_adapter_module_does_not_import_bot():
    import ast
    import pathlib
    import sentinel_engine.adapters.execution_adapter as module

    source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("bot")
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("bot")
