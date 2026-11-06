from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import roc_auc_score
from loguru import logger
from bot.strategy.features import FEATURE_COLS
from bot.strategy.calibration import fit_conservative_calibration

XGB_MODEL_PATH  = Path("models/saved/xgb_predictor.pkl")
_XGB_META_PATH  = XGB_MODEL_PATH.with_suffix(".meta.json")
_XGB_CALIBRATION_PATH = Path("models/saved/xgb_calibration.pkl")
MODEL_MAX_AGE_DAYS = 30
FORWARD_PERIODS = 21   # 1-month target — aligned with MAX_HOLD_DAYS=45 medium-term horizon
MIN_MOVE_PCT    = 0.003  # require ≥0.3% move to label as "up" — filters 5-min microstructure noise


def forward_target(close: pd.Series, benchmark_close: pd.Series | None = None) -> pd.Series:
    """Binary target for ONE symbol. Must be applied per symbol before frames are combined
    (ADR-081 1.1): on a combined frame the shift crosses tickers.

    Without a benchmark: 1 if the close FORWARD_PERIODS bars ahead is at least
    MIN_MOVE_PCT higher. That label is dominated by market drift (base rate 0.40-0.71
    by year), so the model learned the market, not the stock.

    With a benchmark (ADR-081 1.6): 1 if the stock's forward return beats the benchmark's
    over the same bars. Base rate is about 0.50, and the market drift is removed.
    Rows where the benchmark has no value are NaN, so they are dropped.
    """
    stock_fwd = (close.shift(-FORWARD_PERIODS) - close) / close
    if benchmark_close is None:
        return (stock_fwd > MIN_MOVE_PCT).astype(int)
    # Benchmark forward return is computed on the benchmark's own dates, then aligned,
    # so gaps in the stock's bars cannot shift the benchmark window.
    bench_fwd = ((benchmark_close.shift(-FORWARD_PERIODS) - benchmark_close) / benchmark_close)
    bench_fwd = bench_fwd.reindex(close.index)
    target = ((stock_fwd - bench_fwd) > 0).astype(float)
    return target.where(stock_fwd.notna() & bench_fwd.notna())


def time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Three-way time split (ADR-081 1.2 / 1.3). Rows must be sorted by date.

    train: first 70% of rows; val: next 15% (early stopping only);
    holdout: last 15% (reported AUC and calibration only).
    A purge of FORWARD_PERIODS unique dates sits before each boundary, so a label
    whose window overlaps the next segment does not leak into the earlier one.
    """
    dates = pd.Index(sorted(df.index.unique()))
    k_val = dates.searchsorted(df.index[int(len(df) * 0.70)])
    k_hold = dates.searchsorted(df.index[int(len(df) * 0.85)])
    train_end = dates[max(k_val - FORWARD_PERIODS, 0)]
    val_end = dates[max(k_hold - FORWARD_PERIODS, 0)]
    train = df[df.index < train_end]
    val = df[(df.index >= dates[k_val]) & (df.index < val_end)]
    holdout = df[df.index >= dates[k_hold]]
    return train, val, holdout


def _expected_calibration_error(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Standard binned ECE: weighted mean |predicted - actual| across equal-width bins."""
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels, dtype=float)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(probs)
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (probs >= lo) & (probs < hi) if hi < 1.0 else (probs >= lo) & (probs <= hi)
        if not mask.any():
            continue
        bin_weight = mask.sum() / total
        ece += bin_weight * abs(probs[mask].mean() - labels[mask].mean())
    return float(ece)


class XGBPredictor:
    def __init__(self):
        self.model = None
        self.val_auc: float = 0.0  # populated by train(); read by train_model.py for report
        # True after predict_proba() returned its 0.5 fallback (no model,
        # or a prediction error) rather than a genuine computed
        # probability that happens to equal 0.5 -- see predict_proba()'s
        # own docstring. Purely additive/introspective: predict_proba()'s
        # return type and value are unchanged in every case, so ensemble.py
        # and every other caller are unaffected.
        self.last_prediction_is_fallback: bool = False
        self._calibration = None  # ADR-076 — observation-only calibrated probability
        # Calibration-quality metrics (ADR-076), populated by train() for
        # scripts/train_model.py's validation_report.json. Since ADR-081 1.2 these
        # are computed on the HOLDOUT segment, which early stopping never sees.
        # The calibrator is fit on the holdout as well, so calibration metrics are
        # in-sample for the calibrator; reported as such.
        self.calibration_brier_raw: float | None = None
        self.calibration_brier_calibrated: float | None = None
        self.calibration_ece: float | None = None
        self._load()

    def _load(self):
        if XGB_MODEL_PATH.exists():
            try:
                self.model = joblib.load(XGB_MODEL_PATH)
                # Detect feature set mismatch: model trained on a different FEATURE_COLS
                if hasattr(self.model, "feature_names_in_"):
                    trained = list(self.model.feature_names_in_)
                    if trained != FEATURE_COLS:
                        logger.warning(
                            f"XGBoost model trained on {len(trained)} features but "
                            f"FEATURE_COLS now has {len(FEATURE_COLS)} — model is stale. "
                            "Run scripts/train_model.py to retrain."
                        )
                        self.model = None
                        return
                logger.info("XGBoost model loaded.")
                self._check_model_age()
            except Exception as e:
                logger.warning(f"Failed to load XGBoost model: {e}")
        else:
            logger.warning("No XGBoost model found — will need training.")
        if _XGB_CALIBRATION_PATH.exists():
            try:
                # Self-produced artifact from our own train() below, same trust
                # boundary as XGB_MODEL_PATH above (also loaded via joblib.load).
                self._calibration = joblib.load(_XGB_CALIBRATION_PATH)
                logger.info("XGBoost calibration model loaded (ADR-076, observation-only).")
            except Exception as e:
                logger.warning(f"Failed to load XGBoost calibration model: {e}")
                self._calibration = None

    def _check_model_age(self) -> None:
        if not _XGB_META_PATH.exists():
            return
        try:
            meta = json.loads(_XGB_META_PATH.read_text())
            trained_at = meta.get("trained_at")
            if not trained_at:
                return
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(trained_at)).days
            if age_days > MODEL_MAX_AGE_DAYS:
                logger.warning(
                    f"XGBoost model is {age_days} days old (trained {trained_at[:10]}) — "
                    f"win rate may drift. Retrain with scripts/train_model.py."
                )
            else:
                logger.info(f"XGBoost model age: {age_days}d (trained {trained_at[:10]})")
        except Exception as e:
            logger.debug(f"Could not read model metadata: {e}")

    def train(self, df: pd.DataFrame, save: bool = True) -> None:
        try:
            from xgboost import XGBClassifier
        except ImportError:
            logger.error("xgboost not installed. Run: pip install xgboost")
            return

        df = df.copy()
        # ADR-081 1.1: the target must already be per-symbol (train_model.load_combined).
        # Refuse to build it here on a combined frame, where the shift crosses tickers.
        if "target" not in df.columns:
            raise ValueError("XGBPredictor.train needs a per-symbol 'target' column "
                             "(use forward_target() before combining symbols)")
        df.dropna(inplace=True)
        train_df, val_df, hold_df = time_split(df)

        mask = train_df[FEATURE_COLS].notna().all(axis=1)
        X = train_df.loc[mask, FEATURE_COLS]
        y = train_df.loc[mask, "target"]

        val_mask = val_df[FEATURE_COLS].notna().all(axis=1)
        X_val = val_df.loc[val_mask, FEATURE_COLS]
        y_val = val_df.loc[val_mask, "target"]

        hold_mask = hold_df[FEATURE_COLS].notna().all(axis=1)
        X_hold = hold_df.loc[hold_mask, FEATURE_COLS]
        y_hold = hold_df.loc[hold_mask, "target"]

        self.model = XGBClassifier(
            n_estimators=1000,         # high ceiling — early stopping finds the right count
            learning_rate=0.01,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            early_stopping_rounds=50,  # XGBoost 2.x: moved from fit() to constructor
            random_state=42,
        )
        self.model.fit(
            X, y,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        best_trees = self.model.best_iteration
        logger.info(f"XGBoost early stopped at tree {best_trees}")

        if len(X_hold) > 0:
            # Reported AUC and calibration use the holdout only (ADR-081 1.2).
            val_proba = self.model.predict_proba(X_hold)[:, 1]
            val_auc   = float(roc_auc_score(y_hold, val_proba))
            self.val_auc = val_auc
            if val_auc < 0.52:
                logger.warning(
                    f"XGBoost val AUC-ROC {val_auc:.3f} is near random — "
                    "model may have degraded. Review training data before deploying."
                )
            else:
                logger.info(f"XGBoost val AUC-ROC (holdout 15%, n={len(X_hold)}, effective n≈{len(X_hold) // FORWARD_PERIODS}): {val_auc:.3f}")

            try:
                self._calibration = fit_conservative_calibration(val_proba, y_hold.values)
                calibrated_val = self._calibration.predict(val_proba)
                self.calibration_brier_raw = float(np.mean((val_proba - y_hold.values) ** 2))
                self.calibration_brier_calibrated = float(np.mean((calibrated_val - y_hold.values) ** 2))
                self.calibration_ece = _expected_calibration_error(calibrated_val, y_hold.values)
                logger.info(
                    "XGBoost calibration model fit (ADR-076, observation-only) — "
                    f"brier raw={self.calibration_brier_raw:.4f} "
                    f"calibrated={self.calibration_brier_calibrated:.4f} "
                    f"ece={self.calibration_ece:.4f}"
                )
            except Exception as e:
                logger.warning(f"XGBoost calibration fit failed: {e}")
                self._calibration = None
        else:
            self._calibration = None

        if save:
            XGB_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, XGB_MODEL_PATH)
            _XGB_META_PATH.write_text(
                json.dumps({"trained_at": datetime.now(timezone.utc).isoformat()})
            )
            logger.info(f"XGBoost trained and saved to {XGB_MODEL_PATH}")
            if self._calibration is not None:
                joblib.dump(self._calibration, _XGB_CALIBRATION_PATH)
                logger.info(f"XGBoost calibration model saved to {_XGB_CALIBRATION_PATH}")

    def predict_proba(self, row: pd.Series) -> float:
        """Return probability (0-1) that price will be higher in {FORWARD_PERIODS} candles.

        Sets last_prediction_is_fallback to distinguish "model unavailable /
        prediction failed" (fallback 0.5) from a genuine computed
        probability that happens to equal 0.5 -- the return value itself is
        unchanged in either case."""
        if self.model is None:
            self.last_prediction_is_fallback = True
            return 0.5
        try:
            features = pd.DataFrame([row[FEATURE_COLS]])
            result = float(self.model.predict_proba(features)[0, 1])
            self.last_prediction_is_fallback = False
            return result
        except Exception as e:
            logger.error(f"XGBoost predict failed: {e}")
            self.last_prediction_is_fallback = True
            return 0.5

    def calibrated_proba(self, row: pd.Series, raw_prob: float | None = None) -> float | None:
        """Observation-only calibrated probability (ADR-076).

        Pass the already-computed raw_prob (from a predict_proba() call on
        this same row) to avoid a redundant second XGBoost inference —
        callers that already call predict_proba() every cycle should always
        do this. If omitted, computes it here (keeps this method usable on
        its own, e.g. in tests).

        Returns None when no calibration model is loaded or the base model
        is unavailable — never a fabricated fallback value. Not read by
        ensemble_signal(), XGB_MIN_CONFIDENCE, or any other live gate;
        recorded to signal_log for analysis only."""
        if self.model is None or self._calibration is None:
            return None
        try:
            raw = self.predict_proba(row) if raw_prob is None else raw_prob
            if self.last_prediction_is_fallback:
                return None
            return float(self._calibration.predict([raw])[0])
        except Exception as e:
            logger.warning(f"XGBoost calibrated_proba failed: {e}")
            return None

    def explain(self, row: pd.Series) -> list:
        """Return top-3 [(feature_name, shap_value), ...] driving this prediction.

        Uses XGBoost's built-in tree SHAP — no extra library required.
        Positive shap_value = pushed toward BUY; negative = pushed away.
        Returns [] if model is unavailable or SHAP computation fails.
        """
        if self.model is None:
            return []
        try:
            from xgboost import DMatrix
            X = row[FEATURE_COLS].values.reshape(1, -1).astype(float)
            dmat = DMatrix(X, feature_names=FEATURE_COLS)
            # pred_contribs shape: (1, n_features+1) — last column is the bias term
            contribs = self.model.get_booster().predict(dmat, pred_contribs=True)[0][:-1]
            idx = np.argsort(np.abs(contribs))[::-1][:3]
            return [(FEATURE_COLS[i], round(float(contribs[i]), 4)) for i in idx]
        except Exception as exc:
            logger.warning(f"XGBoost explain failed: {exc}")
            return []
