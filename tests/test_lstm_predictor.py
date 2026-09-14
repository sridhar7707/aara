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
    a genuine prediction, not an unavailability -- must NOT be flagged."""
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = lambda x: torch.tensor([[0.0]])
    predictor.scaler = None
    result = predictor.predict_proba(lstm_feature_df)
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is False


def test_lstm_predictor_genuine_prediction_return_type_and_value_unchanged(lstm_feature_df):
    """Backward-compatibility proof for ensemble.py and every other caller:
    the new flag is purely additive -- predict_proba() still returns a bare
    float, with the exact same value as before this change."""
    from bot.strategy.lstm_predictor import LSTMPredictor
    predictor = LSTMPredictor()
    predictor.model = lambda x: torch.tensor([[2.0]])
    predictor.scaler = None
    result = predictor.predict_proba(lstm_feature_df)
    assert isinstance(result, float)
    assert abs(result - float(torch.sigmoid(torch.tensor(2.0)))) < 1e-9
