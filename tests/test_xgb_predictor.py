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


# --- calibrated_proba (ADR-076, observation-only) --------------------------

def test_calibrated_proba_none_when_no_calibration_model(feature_df):
    """A pre-ADR-076 model has no calibration file -- must return None, not
    a fabricated value."""
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.return_value = np.array([[0.4, 0.6]])
    predictor._calibration = None
    assert predictor.calibrated_proba(feature_df.iloc[-1]) is None


def test_calibrated_proba_none_when_base_model_missing(feature_df):
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = None
    predictor._calibration = MagicMock()
    assert predictor.calibrated_proba(feature_df.iloc[-1]) is None


def test_calibrated_proba_returns_float_in_range_when_available(feature_df):
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.return_value = np.array([[0.1, 0.9]])
    predictor._calibration = MagicMock()
    predictor._calibration.predict.return_value = np.array([0.7])
    result = predictor.calibrated_proba(feature_df.iloc[-1])
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


def test_calibrated_proba_is_not_a_passthrough_of_raw_score(feature_df):
    """Proves calibration is actually applied, not bypassed: a confident raw
    score fed through a (mocked) conservative calibrator comes back lower."""
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.return_value = np.array([[0.1, 0.9]])
    predictor._calibration = MagicMock()
    predictor._calibration.predict.return_value = np.array([0.55])
    result = predictor.calibrated_proba(feature_df.iloc[-1])
    assert result == pytest.approx(0.55)
    assert result != 0.9


def test_calibrated_proba_reuses_raw_prob_without_a_second_inference(feature_df):
    """Efficiency fix: when the caller already ran predict_proba() on this row
    (the bot/main.py pattern, once per symbol per cycle), passing that value
    as raw_prob must skip a second XGBoost inference entirely."""
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor._calibration = MagicMock()
    predictor._calibration.predict.return_value = np.array([0.55])

    raw = predictor.predict_proba(feature_df.iloc[-1])  # first (only) real inference
    predictor.model.predict_proba.reset_mock()

    result = predictor.calibrated_proba(feature_df.iloc[-1], raw_prob=raw)

    predictor.model.predict_proba.assert_not_called()
    assert result == pytest.approx(0.55)


def test_calibrated_proba_none_when_predict_proba_is_fallback(feature_df):
    """If the raw prediction itself fell back to 0.5 (no model / error),
    the calibrated value must also be None, not a calibrated 0.5."""
    from bot.strategy.xgb_predictor import XGBPredictor
    predictor = XGBPredictor()
    predictor.model = MagicMock()
    predictor.model.predict_proba.side_effect = RuntimeError("boom")
    predictor._calibration = MagicMock()
    assert predictor.calibrated_proba(feature_df.iloc[-1]) is None
