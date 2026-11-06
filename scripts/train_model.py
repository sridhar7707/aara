"""Offline training script — trains all models and saves validation artefacts.
Run locally or on HuggingFace ZeroGPU.

Outputs after a successful run:
  models/saved/                   — trained model artefacts (pkl / pt)
  models/validation_report.json   — XGB val AUC + calibration quality, training metadata.
                                     lstm_val_loss is a retirement sentinel (ADR-077), not
                                     a live measurement — see LSTMPredictor below.
  models/feature_importance.json  — XGBoost feature importances (used by dashboard chart)

Split (ADR-081 1.2): rows before TRAIN_CUTOFF (30 days before today) are split in time into
train (70%), early-stopping validation (15%) and holdout (15%), with a purge at each boundary.
The reported AUC and calibration use the holdout only. The holdout is NOT the last 30 days.
Re-run scripts/download_data.py first if raw data is missing or stale.

LSTM retired from this pipeline (ADR-077, 2026-11-04): 10 straight weekly retrains
showed identical immediate overfitting (val loss diverges from epoch 3 on, best-ever
val_loss still above the degraded threshold) regardless of growing training data —
a structural issue, not a "needs more data" one. LSTMPredictor.train() is left
callable for a future, separately-scoped experiment; it is simply no longer invoked
here. bot/strategy/lstm_predictor.py's degradation logic is untouched and still
correctly excludes it from every live ensemble decision (it already has for 10+
weeks) via the sentinel this script writes below.
"""
from __future__ import annotations

import json, os, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from loguru import logger
from bot.strategy.features import FEATURE_COLS, compute_features
from bot.strategy.regime_classifier import RegimeClassifier, label_regime
from bot.strategy.xgb_predictor import XGBPredictor, FORWARD_PERIODS as XGB_FP, forward_target
from bot.strategy.lstm_predictor import LSTM_DEGRADED_VAL_LOSS
from config import TRAINING_SYMBOLS, INITIAL_CAPITAL

# Retirement sentinel (ADR-077) — not a real measurement. Must stay strictly
# greater than LSTM_DEGRADED_VAL_LOSS so LSTMPredictor._check_degradation()
# keeps setting is_degraded=True, which keeps predict_proba() returning exactly
# 0.5, which keeps ensemble.py's indeterminate-band detection excluding it from
# live ensemble weight — exactly the behavior it has already had for 10+ weeks.
_LSTM_RETIRED_SENTINEL = 1.0
assert _LSTM_RETIRED_SENTINEL > LSTM_DEGRADED_VAL_LOSS

DATA_DIR = "data/raw"

# Training cutoff: rows before this date are used. The final 15% of them is the holdout (ADR-081 1.2).
# Recomputed at runtime so the model is never trained on stale out-of-distribution data.
_HOLDOUT_DAYS = 30
TRAIN_CUTOFF = (datetime.now(timezone.utc) - timedelta(days=_HOLDOUT_DAYS)).strftime("%Y-%m-%d")


def load_combined(cutoff: str | None = None) -> pd.DataFrame:
    # Load SPY close first so compute_features can compute rs_vs_spy features
    spy_close: pd.Series | None = None
    spy_path = f"{DATA_DIR}/SPY.csv"
    if os.path.exists(spy_path):
        spy_raw = pd.read_csv(spy_path, index_col=0, parse_dates=True)
        if cutoff:
            spy_raw = spy_raw[spy_raw.index < cutoff]
        spy_close = spy_raw["close"]

    frames = []
    for sym in TRAINING_SYMBOLS:
        path = f"{DATA_DIR}/{sym}.csv"
        if not os.path.exists(path):
            logger.warning(f"Missing data for {sym} — skipping.")
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if cutoff:
            df = df[df.index < cutoff]
        df = compute_features(df, spy_close=spy_close)
        # ADR-081 1.1 / 1.4: labels are built per symbol, before frames are combined,
        # so their forward windows never cross tickers.
        df["regime"] = label_regime(df)
        # ADR-081 1.6: label = beats SPY over the horizon. The absolute-return label was
        # dominated by market drift (base rate 0.40-0.71 by year) and the model learned the market.
        if spy_close is None:
            raise FileNotFoundError("SPY.csv is required for the excess-over-SPY target (ADR-081 1.6)")
        df["target"] = forward_target(df["close"], benchmark_close=spy_close)
        if sym == "SPY":
            df["target"] = float("nan")  # the benchmark has no excess return against itself
        df["symbol"] = sym
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No data found. Run scripts/download_data.py first.")
    return pd.concat(frames).sort_index()


def main():
    logger.info(f"Loading training data (cutoff={TRAIN_CUTOFF}) — {len(TRAINING_SYMBOLS)} symbols...")
    df = load_combined(cutoff=TRAIN_CUTOFF)
    date_min = df.index.min().date().isoformat()
    date_max = df.index.max().date().isoformat()
    logger.info(f"Training rows: {len(df):,} | date range: {date_min} → {date_max}")

    logger.info("Training regime classifier...")
    regime_clf = RegimeClassifier()
    regime_clf.train(df)

    # Use combined data for XGBoost (more samples = better generalisation)
    logger.info("Training XGBoost predictor...")
    xgb = XGBPredictor()
    xgb.train(df.drop(columns=["symbol", "regime"], errors="ignore"))

    os.makedirs("models", exist_ok=True)

    # ── Validation report ─────────────────────────────────────────────────────
    # Captures out-of-sample quality signal from each model's internal 80/20 split.
    # Pushed to HF alongside model weights so the dashboard can display it without
    # having to load the model files.
    report = {
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "train_cutoff":     TRAIN_CUTOFF,
        "training_symbols": len(TRAINING_SYMBOLS),
        "training_rows":    len(df),
        "date_range":       {"from": date_min, "to": date_max},
        "xgb_val_auc":      round(xgb.val_auc, 4),
        # ADR-077 — LSTM retired from this pipeline. Not a real measurement;
        # see _LSTM_RETIRED_SENTINEL above for why this must stay > 0.58.
        "lstm_val_loss":    _LSTM_RETIRED_SENTINEL,
        "lstm_retired":     True,
        "lstm_retired_since": "2026-11-04",
        # ADR-076 — calibration quality, observation-only, not read by any gate.
        # Computed on the same val split the calibrator was fit on (no third
        # split exists at this data volume); None if calibration fit failed.
        "xgb_calibration_brier_raw":        None if xgb.calibration_brier_raw is None else round(xgb.calibration_brier_raw, 4),
        "xgb_calibration_brier_calibrated": None if xgb.calibration_brier_calibrated is None else round(xgb.calibration_brier_calibrated, 4),
        "xgb_calibration_ece":              None if xgb.calibration_ece is None else round(xgb.calibration_ece, 4),
        "feature_count":    len(FEATURE_COLS),
        "feature_cols":     FEATURE_COLS,
        "forward_periods":  XGB_FP,
    }
    with open("models/validation_report.json", "w") as fh:
        json.dump(report, fh, indent=2)
    logger.info(
        f"Validation report → models/validation_report.json (xgb_auc={report['xgb_val_auc']})"
    )

    # ── Runtime version snapshot ──────────────────────────────────────────────
    # Saved alongside model weights so the bot can detect training/inference
    # library mismatches at startup before they silently corrupt predictions.
    import sklearn as _sk
    import torch as _torch
    import xgboost as _xgb_mod
    runtime_versions = {
        "scikit-learn": _sk.__version__,
        "torch":        _torch.__version__,
        "xgboost":      _xgb_mod.__version__,
    }
    with open("models/runtime_versions.json", "w") as fh:
        json.dump(runtime_versions, fh, indent=2)
    logger.info(f"Runtime versions → models/runtime_versions.json: {runtime_versions}")

    # ── Feature importance ────────────────────────────────────────────────────
    # XGBClassifier.feature_importances_ = normalised gain — same scale across runs.
    # Saved separately so the dashboard can render the explainability chart without
    # loading the full 10 MB model file.
    if xgb.model is not None:
        importances = dict(zip(FEATURE_COLS, xgb.model.feature_importances_.tolist()))
        with open("models/feature_importance.json", "w") as fh:
            json.dump(importances, fh, indent=2)
        logger.info("Feature importance → models/feature_importance.json")

    # ── Artifact verification ─────────────────────────────────────────────────
    from pathlib import Path
    required = {
        "XGBoost model":      Path("models/saved/xgb_predictor.pkl"),
        "Regime model":       Path("models/saved/regime_classifier.pkl"),
        "Validation report":  Path("models/validation_report.json"),
        "Feature importance": Path("models/feature_importance.json"),
        "Runtime versions":   Path("models/runtime_versions.json"),
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        logger.error(f"Training completed but artifacts are MISSING: {missing}")
        sys.exit(1)
    for name, path in required.items():
        size_kb = path.stat().st_size / 1024
        logger.info(f"  {name}: {path}  ({size_kb:.1f} KB)")
    logger.info("All models trained and verified successfully.")

    # ── Model quality gate ────────────────────────────────────────────────────
    # LSTM excluded (ADR-077) — its degraded state is a settled, intentional
    # retirement now, not a weekly quality anomaly to flag.
    _issues = []
    if report["xgb_val_auc"] < 0.52:
        _issues.append(
            f"XGB val_auc={report['xgb_val_auc']:.4f} < 0.52 (near coin-flip; check feature quality)"
        )
    if _issues:
        logger.warning("⚠ MODEL QUALITY ISSUES DETECTED — bot will operate in degraded mode:")
        for issue in _issues:
            logger.warning(f"  • {issue}")
    else:
        logger.info(f"Model quality OK — xgb_auc={report['xgb_val_auc']:.4f}")


if __name__ == "__main__":
    main()
