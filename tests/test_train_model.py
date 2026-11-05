"""Tests for scripts/train_model.py's LSTM retirement (ADR-077)."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import scripts.train_model as train_model


def test_lstm_predictor_not_imported():
    """ADR-077 — train_model.py must no longer import or reference
    LSTMPredictor at all; the weekly retrain should never train it."""
    assert not hasattr(train_model, "LSTMPredictor")


def test_retirement_sentinel_exceeds_degraded_threshold():
    """The sentinel written into every report must stay strictly above
    LSTM_DEGRADED_VAL_LOSS -- this is the exact invariant that keeps
    LSTMPredictor.is_degraded True and the ensemble excluding it. Importing
    the module already asserts this at import time; this test makes the
    invariant explicit and independently checkable."""
    from bot.strategy.lstm_predictor import LSTM_DEGRADED_VAL_LOSS
    assert train_model._LSTM_RETIRED_SENTINEL > LSTM_DEGRADED_VAL_LOSS


def _fake_training_df(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "close": close,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "volume": rng.integers(1_000, 10_000, n),
    }, index=idx)
    for i, col in enumerate(train_model.FEATURE_COLS):
        df[col] = rng.normal(0, 1, n)
    df["symbol"] = "FAKE"
    df["regime"] = 0
    return df


@pytest.fixture()
def _mocked_main(tmp_path, monkeypatch):
    """Run the real main() against fully mocked models and a tiny synthetic
    dataset, inside an isolated tmp_path cwd, so no real training happens
    and no real repo files are touched."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(train_model, "load_combined", lambda cutoff=None: _fake_training_df())

    fake_xgb = MagicMock()
    fake_xgb.val_auc = 0.552
    fake_xgb.calibration_brier_raw = None
    fake_xgb.calibration_brier_calibrated = None
    fake_xgb.calibration_ece = None
    fake_xgb.model.feature_importances_.tolist.return_value = [0.0] * len(train_model.FEATURE_COLS)
    monkeypatch.setattr(train_model, "XGBPredictor", lambda: fake_xgb)

    fake_regime = MagicMock()
    monkeypatch.setattr(train_model, "RegimeClassifier", lambda: fake_regime)

    # Regime/XGB "save" steps write real files elsewhere in train(); since
    # both are mocked here, create the artifacts main() checks for directly.
    saved = tmp_path / "models" / "saved"
    saved.mkdir(parents=True)
    (saved / "xgb_predictor.pkl").write_bytes(b"fake")
    (saved / "regime_classifier.pkl").write_bytes(b"fake")

    train_model.main()
    return tmp_path


def test_report_has_retirement_sentinel_not_a_measurement(_mocked_main):
    report = json.loads((_mocked_main / "models" / "validation_report.json").read_text())
    assert report["lstm_val_loss"] == train_model._LSTM_RETIRED_SENTINEL
    assert report["lstm_retired"] is True
    assert "lstm_retired_since" in report


def test_artifact_verification_does_not_require_lstm_files(_mocked_main):
    """Confirms the real failure mode this ADR fixes: before it, a fresh CI
    checkout with no LSTM files (since LSTMPredictor.train() never ran) would
    sys.exit(1) here and fail the entire weekly retrain, including XGB."""
    assert not (_mocked_main / "models" / "saved" / "lstm_predictor.pt").exists()
    assert not (_mocked_main / "models" / "saved" / "lstm_scaler.pkl").exists()
    # main() completing without raising SystemExit is itself the assertion;
    # also confirm the XGB artifact it does require is present.
    assert (_mocked_main / "models" / "saved" / "xgb_predictor.pkl").exists()


def test_quality_gate_has_no_lstm_branch(_mocked_main, caplog):
    """No 'LSTM' mention anywhere in main()'s logged output -- the quality
    gate no longer evaluates it at all."""
    assert "LSTM" not in caplog.text
    assert "lstm" not in caplog.text


# --- ADR-077 primary safety test ------------------------------------------
#
# The one way this retirement could go wrong: if lstm_val_loss were ever
# omitted or read back as <= LSTM_DEGRADED_VAL_LOSS, LSTMPredictor.is_degraded
# would flip to False, predict_proba() would stop forcing the 0.5 fallback,
# and ensemble.py would stop excluding it from live ensemble weight --
# silently re-enabling a frozen, never-retrained-again model in live trading.
# Verified end-to-end against the real report this script writes, not assumed.

def test_retired_sentinel_keeps_lstm_degraded_and_excluded_from_ensemble(_mocked_main, monkeypatch):
    import importlib
    from bot.strategy import lstm_predictor as lstm_mod
    monkeypatch.setattr(lstm_mod, "_VALIDATION_REPORT_PATH", _mocked_main / "models" / "validation_report.json")

    predictor = lstm_mod.LSTMPredictor()
    assert predictor.is_degraded is True

    predictor.model = MagicMock()  # loaded model present -- degradation alone must still force fallback
    row = pd.Series({col: 0.0 for col in train_model.FEATURE_COLS})
    long_df = pd.concat([pd.DataFrame([row] * 25)], ignore_index=True)
    result = predictor.predict_proba(long_df)
    assert result == 0.5

    from bot.strategy.ensemble import ensemble_signal, WEIGHTS
    action, _ = ensemble_signal(xgb_prob=0.70, lstm_prob=result, sentiment_score=0.0, regime="TRENDING_UP")
    # With lstm indeterminate at 0.5, w_xgb becomes WEIGHTS["xgb"]+WEIGHTS["lstm"] = 0.825.
    # score = 0.825*0.70 + 0*0.5(lstm, zero weight) + 0.175*0.5(neutral sentiment) + 0*0.5(macro)
    #       = 0.5775 + 0.0875 = 0.665 -> above STRONG_BUY_THRESHOLD(0.65) -> STRONG_BUY.
    # If the weight transfer failed to happen (the regression this test exists to
    # catch), lstm would instead carry its full 0.175 weight: score would be
    # 0.65*0.70 + 0.175*0.5 + 0.175*0.5 = 0.455 + 0.0875 + 0.0875 = 0.63 -> only BUY.
    # The two outcomes are deliberately on opposite sides of a threshold so this
    # test fails loudly, not silently, if the exclusion ever breaks.
    assert action == "STRONG_BUY"
