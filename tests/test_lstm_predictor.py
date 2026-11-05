import pytest
import pandas as pd
import numpy as np
import torch
from unittest.mock import MagicMock
from tests.conftest import make_ohlcv
from bot.strategy.features import compute_features


@pytest.fixture()
def feature_df():
    raw = make_ohlcv(270)
    df = compute_features(raw)
    df["regime"] = 0
    return df.reset_index(drop=True)


@pytest.fixture()
def lstm_feature_df():
    """270 raw bars survives dropna() as only 18 rows (252-bar momentum
    columns' warmup) -- too few for LSTM's SEQ_LEN=20 sequence requirement.
    More raw bars for tests that need a real, non-fallback sequence."""
    raw = make_ohlcv(320)
    df = compute_features(raw)
    df["regime"] = 0
    return df.reset_index(drop=True)


def test_lstm_predictor_predict_returns_float_without_model():
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = None
    row = pd.Series(np.zeros(20))
    result = predictor.predict_proba(row)
    assert isinstance(result, float)


def test_lstm_predictor_predict_no_model_returns_zero():
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = None
    row = pd.Series({"rsi": 50.0, "macd_diff_pct": 0.01})
    assert predictor.predict_proba(row) == 0.5


def test_lstm_predictor_predict_range_with_model(feature_df):
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    if predictor.model is None:
        pytest.skip("No LSTM model on disk")
    row = feature_df.iloc[-1]
    prob = predictor.predict_proba(row)
    assert 0.0 <= prob <= 1.0


# --- "model unavailable" vs "genuine neutral prediction" ------------------
#
# predict_proba() always returned a bare 0.5 on a missing model, too little
# history, a NaN sequence, or a genuine (if coincidental) neutral
# prediction -- making all of them indistinguishable to any caller.
# last_prediction_is_fallback (a per-call sibling to the existing
# load-time is_degraded flag) makes that distinction available without
# changing predict_proba()'s return type or value in any case -- ensemble.py
# and every other caller are unaffected.

def test_lstm_predictor_flags_fallback_when_model_is_none():
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = None
    row = pd.Series({"rsi": 50.0, "macd_diff_pct": 0.01})
    result = predictor.predict_proba(row)
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is True


def test_lstm_predictor_flags_fallback_when_too_few_bars(feature_df):
    from bot.strategy.lstm_predictor import LSTMPredictor
    from bot.strategy.lstm_predictor import SEQ_LEN
    predictor = LSTMPredictor()
    predictor.model = MagicMock()
    short_df = feature_df.iloc[: SEQ_LEN - 1]
    result = predictor.predict_proba(short_df)
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is True


def test_lstm_predictor_flags_fallback_on_predict_exception(lstm_feature_df):
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = MagicMock(side_effect=RuntimeError("boom"))
    predictor.scaler = None
    result = predictor.predict_proba(lstm_feature_df)
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is True


def test_lstm_predictor_does_not_flag_fallback_for_a_genuine_neutral_prediction(lstm_feature_df):
    """A real, loaded model that happens to output logit=0 (sigmoid=0.5) is
    a genuine prediction, not an unavailability -- must NOT be flagged.

    is_degraded is pinned False: this test's intent is a non-degraded model
    that happens to output 0.5, not a degraded one -- without pinning it,
    this test is silently coupled to whatever models/validation_report.json
    says on disk right now (ADR-074 found this while adding is_degraded
    handling to predict_proba(); it's a pre-existing test-isolation gap,
    not something that changed)."""
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = lambda x: torch.tensor([[0.0]])
    predictor.scaler = None
    predictor.is_degraded = False
    result = predictor.predict_proba(lstm_feature_df)
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is False


def test_lstm_predictor_genuine_prediction_return_type_and_value_unchanged(lstm_feature_df):
    """Backward-compatibility proof for ensemble.py and every other caller:
    the new flag is purely additive -- predict_proba() still returns a bare
    float, with the exact same value as before this change.

    is_degraded pinned False for the same reason as the test above."""
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = lambda x: torch.tensor([[2.0]])
    predictor.scaler = None
    predictor.is_degraded = False
    result = predictor.predict_proba(lstm_feature_df)
    assert isinstance(result, float)
    assert abs(result - float(torch.sigmoid(torch.tensor(2.0)))) < 1e-9


# --- ADR-074: a degraded model must not return a confident-looking value ---
#
# predict_proba() previously ignored is_degraded entirely -- a model whose
# own validation loss says it carries no directional signal could still
# return a confident sigmoid output (e.g. logit=2.0 -> ~0.88) if the raw
# forward pass happened to produce one, letting a known-bad model influence
# the live trading decision and every confidence display that reads it.

def test_lstm_predictor_degraded_model_forces_fallback_even_with_confident_output(lstm_feature_df):
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = lambda x: torch.tensor([[2.0]])  # would otherwise be a confident ~0.88
    predictor.scaler = None
    predictor.is_degraded = True
    result = predictor.predict_proba(lstm_feature_df)
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is True


# --- ADR-078: retirement vs genuine degradation log message ---------------
#
# ADR-077 writes an explicit retirement sentinel (lstm_val_loss=1.0,
# lstm_retired=true) so is_degraded stays True forever. The pre-ADR-078
# "DEGRADED ... Run: python scripts/train_model.py" message is now
# permanently false for that case (the script can never change it), so the
# log message must branch on lstm_retired without ever changing is_degraded
# or val_loss themselves.

@pytest.fixture()
def _loguru_sink():
    # loguru binds its default sink to sys.stderr at logger.add() time, before
    # pytest's capsys fixture swaps the stream for a given test -- capsys and
    # caplog (which hooks stdlib logging) both miss loguru output. A temporary
    # sink of our own is loguru's own documented way to capture it in tests.
    from loguru import logger
    messages = []
    sink_id = logger.add(lambda message: messages.append(message), level="DEBUG")
    yield messages
    logger.remove(sink_id)


def test_check_degradation_retired_report_logs_info_not_warning(tmp_path, monkeypatch, _loguru_sink):
    import json
    import bot.strategy.lstm_predictor as lstm_mod
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps({"lstm_val_loss": 1.0, "lstm_retired": True}))
    monkeypatch.setattr(lstm_mod, "_VALIDATION_REPORT_PATH", report_path)

    predictor = lstm_mod.LSTMPredictor()
    out = "".join(str(m) for m in _loguru_sink)

    assert predictor.is_degraded is True
    assert predictor.val_loss == 1.0
    assert "DEGRADED" not in out
    assert "Run: python scripts/train_model.py" not in out
    assert "retired" in out.lower()
    assert "ADR-077" in out


def test_check_degradation_non_retired_report_logs_original_warning(tmp_path, monkeypatch, _loguru_sink):
    """Proves the retirement branch doesn't regress the genuine-degradation
    alert path: a report with no lstm_retired flag (e.g. a pre-ADR-077
    report, or a future non-retired LSTM that genuinely degrades) must still
    produce the original actionable warning, verbatim."""
    import json
    import bot.strategy.lstm_predictor as lstm_mod
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps({"lstm_val_loss": 0.62}))
    monkeypatch.setattr(lstm_mod, "_VALIDATION_REPORT_PATH", report_path)

    predictor = lstm_mod.LSTMPredictor()
    out = "".join(str(m) for m in _loguru_sink)

    assert predictor.is_degraded is True
    assert predictor.val_loss == 0.62
    assert "DEGRADED" in out
    assert "Run: python scripts/train_model.py" in out


def test_lstm_predictor_not_degraded_preserves_existing_behavior(lstm_feature_df):
    """Same mocked confident model, is_degraded explicitly False (the default) --
    must behave exactly as before this fix, proving no regression."""
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = lambda x: torch.tensor([[2.0]])
    predictor.scaler = None
    predictor.is_degraded = False
    result = predictor.predict_proba(lstm_feature_df)
    assert abs(result - float(torch.sigmoid(torch.tensor(2.0)))) < 1e-9
    assert predictor.last_prediction_is_fallback is False
