"""Tests for sentinel_engine.adapters.evidence_adapter."""
import ast
import datetime
import inspect

import pytest

from sentinel_engine.adapters import evidence_adapter
from sentinel_engine.adapters.evidence_adapter import to_evidence_records
from sentinel_engine.evidence.evidence import Evidence


def _valid_model_outputs(**overrides):
    defaults = {
        "xgboost": {
            "signal": "BUY",
            "confidence": 0.78,
            "metadata": {"shap_drivers": [{"feature": "rsi", "shap_value": 0.12}]},
        },
        "lstm": {
            "signal": "HOLD",
            "confidence": 0.51,
            "metadata": {"is_degraded": False, "val_loss": 0.02},
        },
        "finbert": {
            "signal": "SELL",
            "confidence": 0.3,
            "metadata": {"raw_score": -0.4},
        },
    }
    defaults.update(overrides)
    return defaults


def test_to_evidence_records_produces_exactly_three_evidence_instances():
    result = to_evidence_records(_valid_model_outputs())

    assert len(result) == 3
    assert all(isinstance(item, Evidence) for item in result)


def test_to_evidence_records_maps_source_per_model():
    result = to_evidence_records(_valid_model_outputs())

    sources = {item.source for item in result}
    assert sources == {"xgboost", "lstm", "finbert"}


def test_to_evidence_records_sets_evidence_type_for_every_record():
    result = to_evidence_records(_valid_model_outputs())

    assert all(item.evidence_type == "MODEL_OUTPUT" for item in result)


def test_to_evidence_records_preserves_model_sub_dict_in_data():
    model_outputs = _valid_model_outputs()

    result = to_evidence_records(model_outputs)

    by_source = {item.source: item for item in result}
    for model in ("xgboost", "lstm", "finbert"):
        assert by_source[model].data == model_outputs[model]


@pytest.mark.parametrize("missing_model", ["xgboost", "lstm", "finbert"])
def test_to_evidence_records_rejects_missing_required_model(missing_model):
    model_outputs = _valid_model_outputs()
    del model_outputs[missing_model]

    with pytest.raises(ValueError):
        to_evidence_records(model_outputs)


@pytest.mark.parametrize("field", ["signal", "confidence", "metadata"])
def test_to_evidence_records_rejects_model_entry_missing_a_required_field(field):
    model_outputs = _valid_model_outputs()
    del model_outputs["finbert"][field]

    with pytest.raises(ValueError):
        to_evidence_records(model_outputs)


@pytest.mark.parametrize("field,bad_value", [
    ("signal", ""),
    ("signal", None),
    ("signal", 123),
    ("confidence", "high"),
    ("confidence", None),
    ("confidence", True),
    ("metadata", "not-a-dict"),
    ("metadata", None),
])
def test_to_evidence_records_rejects_malformed_model_entry(field, bad_value):
    model_outputs = _valid_model_outputs()
    model_outputs["xgboost"] = {**model_outputs["xgboost"], field: bad_value}

    with pytest.raises(ValueError):
        to_evidence_records(model_outputs)


def test_to_evidence_records_error_identifies_model_and_field():
    model_outputs = _valid_model_outputs()
    model_outputs["lstm"]["confidence"] = "not-numeric"

    with pytest.raises(ValueError) as exc_info:
        to_evidence_records(model_outputs)

    message = str(exc_info.value)
    assert "lstm" in message
    assert "confidence" in message


def test_to_evidence_records_ignores_additional_top_level_keys():
    model_outputs = _valid_model_outputs()
    model_outputs["sentiment_extra"] = {
        "signal": "BUY", "confidence": 0.9, "metadata": {},
    }

    result = to_evidence_records(model_outputs)

    assert len(result) == 3
    assert {item.source for item in result} == {"xgboost", "lstm", "finbert"}


def test_to_evidence_records_generates_unique_evidence_ids():
    result = to_evidence_records(_valid_model_outputs())

    ids = {item.evidence_id for item in result}
    assert len(ids) == 3


def test_to_evidence_records_collected_at_is_timezone_aware_utc():
    result = to_evidence_records(_valid_model_outputs())

    for item in result:
        assert item.collected_at.tzinfo is not None
        assert item.collected_at.tzinfo.utcoffset(item.collected_at) == datetime.timedelta(0)


def test_to_evidence_records_data_is_shallow_copy_independent_of_input():
    model_outputs = _valid_model_outputs()

    result = to_evidence_records(model_outputs)
    by_source = {item.source: item for item in result}

    model_outputs["xgboost"]["signal"] = "SELL"
    model_outputs["xgboost"]["confidence"] = 0.01

    assert by_source["xgboost"].data["signal"] == "BUY"
    assert by_source["xgboost"].data["confidence"] == 0.78


def test_evidence_adapter_module_does_not_import_bot():
    source = inspect.getsource(evidence_adapter)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("bot")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("bot")
