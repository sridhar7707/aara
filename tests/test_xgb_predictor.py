import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from tests.conftest import make_ohlcv
from bot.strategy.features import compute_features


@pytest.fixture()
def feature_df():
    raw = make_ohlcv(270)
    df = compute_features(raw)
    df["regime"] = 0
    return df.reset_index(drop=True)


def test_xgb_predictor_predict_returns_float_without_model():
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = None
    result = predictor.predict_proba(pd.Series({col: 0.0 for col in ["rsi", "macd_diff_pct"]}))
    assert isinstance(result, float)


def test_xgb_predictor_predict_returns_probability_range(feature_df):
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    if predictor.model is None:
        pytest.skip("No XGBoost model on disk")
    row = feature_df.iloc[-1]
    prob = predictor.predict_proba(row)
    assert 0.0 <= prob <= 1.0


def test_xgb_predictor_train_skips_without_xgboost(feature_df):
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    with patch.dict("sys.modules", {"xgboost": None}):
        predictor.train(feature_df)


# --- "model unavailable" vs "genuine neutral prediction" ------------------
#
# predict_proba() always returned a bare 0.5 on both a missing model and a
# genuine (if coincidental) neutral prediction, making the two
# indistinguishable to any caller. last_prediction_is_fallback (mirroring
# LSTMPredictor's existing is_degraded flag pattern) makes that distinction
# available without changing predict_proba()'s return type or value in any
# case -- ensemble.py and every other caller are unaffected.

def test_xgb_predictor_flags_fallback_when_model_is_none(feature_df):
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = None
    result = predictor.predict_proba(feature_df.iloc[-1])
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is True


def test_xgb_predictor_flags_fallback_on_predict_exception(feature_df):
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.side_effect = RuntimeError("boom")
    result = predictor.predict_proba(feature_df.iloc[-1])
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is True


def test_xgb_predictor_does_not_flag_fallback_for_a_genuine_neutral_prediction(feature_df):
    """A real, loaded model that happens to output exactly 0.5 is a
    genuine prediction, not an unavailability -- must NOT be flagged."""
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.return_value = np.array([[0.5, 0.5]])
    result = predictor.predict_proba(feature_df.iloc[-1])
    assert result == 0.5
    assert predictor.last_prediction_is_fallback is False


def test_xgb_predictor_genuine_prediction_return_type_and_value_unchanged(feature_df):
    """Backward-compatibility proof for ensemble.py and every other caller:
    the new flag is purely additive -- predict_proba() still returns a bare
    float, with the exact same value as before this change, in both the
    fallback and genuine-prediction cases."""
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.return_value = np.array([[0.23, 0.77]])
    result = predictor.predict_proba(feature_df.iloc[-1])
    assert isinstance(result, float)
    assert result == 0.77
