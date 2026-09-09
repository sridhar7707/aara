"""ADR-068 (B1) -- deterministic, signal-only evidence-polarity classification
in sentinel_engine.adapters.evidence_adapter.to_evidence_records().

Contract:
    Evidence.data["signal"] == "BUY"  -> EvidencePolarity.SUPPORTING
    Evidence.data["signal"] == "SELL" -> EvidencePolarity.CONTRADICTING
    Evidence.data["signal"] == "HOLD" -> None
    any other value                   -> None (never invented, never raises)

Classification only: no aggregation / weighting / scoring / counting; every
other Evidence field is unchanged. The upstream signal is authoritative; the
LSTM [0.45, 0.55] ensemble band and metadata["is_degraded"] are not consulted.
"""
import datetime

import pytest

from sentinel_engine.adapters.evidence_adapter import to_evidence_records
from sentinel_engine.evidence.evidence_polarity import EvidencePolarity


def _model_outputs(xgb_signal="HOLD", lstm_signal="HOLD", finbert_signal="HOLD",
                   *, lstm_confidence=0.51, lstm_is_degraded=False):
    return {
        "xgboost": {
            "signal": xgb_signal,
            "confidence": 0.7,
            "metadata": {"shap_drivers": [{"feature": "rsi", "shap_value": 0.1}]},
        },
        "lstm": {
            "signal": lstm_signal,
            "confidence": lstm_confidence,
            "metadata": {"is_degraded": lstm_is_degraded, "val_loss": 0.02},
        },
        "finbert": {
            "signal": finbert_signal,
            "confidence": 0.6,
            "metadata": {"raw_score": 0.2, "headlines": ["h1"]},
        },
    }


def _by_source(records):
    return {r.source: r for r in records}


# -- 1-9: per-model BUY/SELL/HOLD -> polarity -------------------------------

@pytest.mark.parametrize("model", ["xgboost", "lstm", "finbert"])
@pytest.mark.parametrize("signal,expected", [
    ("BUY", EvidencePolarity.SUPPORTING.value),
    ("SELL", EvidencePolarity.CONTRADICTING.value),
    ("HOLD", None),
])
def test_signal_maps_to_polarity_per_model(model, signal, expected):
    outputs = _model_outputs()
    outputs[model]["signal"] = signal

    record = _by_source(to_evidence_records(outputs))[model]

    assert record.polarity == expected


def test_supporting_and_contradicting_use_the_ratified_vocabulary():
    records = _by_source(to_evidence_records(
        _model_outputs(xgb_signal="BUY", finbert_signal="SELL")
    ))
    assert records["xgboost"].polarity == EvidencePolarity.SUPPORTING.value
    assert records["finbert"].polarity == EvidencePolarity.CONTRADICTING.value
    assert EvidencePolarity.has_value(records["xgboost"].polarity)
    assert EvidencePolarity.has_value(records["finbert"].polarity)


# -- 10-15: structural invariants unchanged -------------------------------

def test_exactly_three_model_output_records():
    records = to_evidence_records(_model_outputs(xgb_signal="BUY"))
    assert len(records) == 3
    assert all(r.evidence_type == "MODEL_OUTPUT" for r in records)


def test_sources_remain_xgboost_lstm_finbert():
    records = to_evidence_records(_model_outputs())
    assert {r.source for r in records} == {"xgboost", "lstm", "finbert"}


def test_evidence_ids_valid_and_unique():
    records = to_evidence_records(_model_outputs())
    ids = [r.evidence_id for r in records]
    assert all(isinstance(i, str) and i for i in ids)
    assert len(set(ids)) == 3


def test_evidence_data_is_unchanged_by_polarity_assignment():
    outputs = _model_outputs(xgb_signal="BUY", lstm_signal="SELL", finbert_signal="HOLD")
    by_source = _by_source(to_evidence_records(outputs))
    for model in ("xgboost", "lstm", "finbert"):
        assert by_source[model].data == outputs[model]


def test_collected_at_remains_populated_and_utc():
    for r in to_evidence_records(_model_outputs(xgb_signal="BUY")):
        assert r.collected_at is not None
        assert r.collected_at.tzinfo is not None
        assert r.collected_at.tzinfo.utcoffset(r.collected_at) == datetime.timedelta(0)


def test_only_polarity_changes_everything_else_matches_input():
    outputs = _model_outputs(xgb_signal="BUY", lstm_signal="SELL", finbert_signal="HOLD")
    by_source = _by_source(to_evidence_records(outputs))

    assert by_source["xgboost"].polarity == EvidencePolarity.SUPPORTING.value
    assert by_source["lstm"].polarity == EvidencePolarity.CONTRADICTING.value
    assert by_source["finbert"].polarity is None

    for model in ("xgboost", "lstm", "finbert"):
        rec = by_source[model]
        assert rec.evidence_type == "MODEL_OUTPUT"
        assert rec.source == model
        assert rec.data == outputs[model]
        assert rec.collected_at is not None


# -- 16: unexpected signal -> None, no raise -----------------------------

@pytest.mark.parametrize("weird_signal", ["STRONG_BUY", "WATCH", "buy", "NEUTRAL", "REJECT", "  "])
def test_unexpected_but_valid_signal_preserves_polarity_none(weird_signal):
    # any non-empty string the adapter's validation accepts, other than the
    # exact "BUY"/"SELL", classifies to None -- polarity is never invented.
    outputs = _model_outputs()
    outputs["xgboost"]["signal"] = weird_signal
    record = _by_source(to_evidence_records(outputs))["xgboost"]
    assert record.polarity is None


def test_empty_signal_still_rejected_by_existing_validation():
    outputs = _model_outputs()
    outputs["xgboost"]["signal"] = ""
    with pytest.raises(ValueError):
        to_evidence_records(outputs)


# -- 17: is_degraded does NOT affect polarity ---------------------------

def test_lstm_is_degraded_true_does_not_affect_polarity():
    supporting = _by_source(to_evidence_records(
        _model_outputs(lstm_signal="BUY", lstm_is_degraded=True)
    ))["lstm"]
    neutral = _by_source(to_evidence_records(
        _model_outputs(lstm_signal="HOLD", lstm_is_degraded=True)
    ))["lstm"]
    contradicting = _by_source(to_evidence_records(
        _model_outputs(lstm_signal="SELL", lstm_is_degraded=True)
    ))["lstm"]

    assert supporting.polarity == EvidencePolarity.SUPPORTING.value
    assert neutral.polarity is None
    assert contradicting.polarity == EvidencePolarity.CONTRADICTING.value
    # the flag is still carried in data, untouched
    assert supporting.data["metadata"]["is_degraded"] is True


# -- 18: LSTM [0.45, 0.55] band gets no special treatment --------------

@pytest.mark.parametrize("lstm_conf", [0.45, 0.46, 0.50, 0.51, 0.55])
def test_lstm_indeterminate_band_confidence_does_not_alter_polarity(lstm_conf):
    # classification follows the already-produced signal value only; the
    # ensemble's [0.45, 0.55] band is never consulted here.
    buy = _by_source(to_evidence_records(
        _model_outputs(lstm_signal="BUY", lstm_confidence=lstm_conf)
    ))["lstm"]
    sell = _by_source(to_evidence_records(
        _model_outputs(lstm_signal="SELL", lstm_confidence=lstm_conf)
    ))["lstm"]
    hold = _by_source(to_evidence_records(
        _model_outputs(lstm_signal="HOLD", lstm_confidence=lstm_conf)
    ))["lstm"]

    assert buy.polarity == EvidencePolarity.SUPPORTING.value
    assert sell.polarity == EvidencePolarity.CONTRADICTING.value
    assert hold.polarity is None


# -- classification only: no aggregation / netting ---------------------

def test_each_record_classified_independently_no_netting():
    # three contradicting signals stay three independent CONTRADICTING
    # records -- nothing is collapsed, counted, or netted.
    records = to_evidence_records(
        _model_outputs(xgb_signal="SELL", lstm_signal="SELL", finbert_signal="SELL")
    )
    assert [r.polarity for r in records] == [EvidencePolarity.CONTRADICTING.value] * 3
    assert len(records) == 3


def test_mixed_signals_are_not_reconciled():
    records = _by_source(to_evidence_records(
        _model_outputs(xgb_signal="BUY", lstm_signal="SELL", finbert_signal="BUY")
    ))
    assert records["xgboost"].polarity == EvidencePolarity.SUPPORTING.value
    assert records["lstm"].polarity == EvidencePolarity.CONTRADICTING.value
    assert records["finbert"].polarity == EvidencePolarity.SUPPORTING.value


def test_evidence_has_no_aggregate_polarity_attribute():
    record = to_evidence_records(_model_outputs(xgb_signal="BUY"))[0]
    for attr in ("net_polarity", "polarity_score", "supporting_count",
                 "contradicting_count", "polarity_weight"):
        assert not hasattr(record, attr)
