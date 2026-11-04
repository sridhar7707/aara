"""Conservative probability calibration (ADR-076).

Pure functions only — no execution/order-placement/live-trading-cycle
imports. Used by XGBPredictor to fit an observation-only calibrated
probability; never imported by bot/main.py's decision path.
"""
import math

import numpy as np
from sklearn.isotonic import IsotonicRegression


def wilson_lower_bound(k: int, n: int, confidence: float = 0.95) -> float:
    """Lower bound of the Wilson score interval for a binomial proportion.

    Returns 0.0 when n == 0. Deliberately the LOWER bound, not the point
    estimate k/n, so downstream calibration is biased toward understating
    confidence rather than overstating it."""
    if n == 0:
        return 0.0
    z = 1.959963984540054 if confidence == 0.95 else abs(
        _z_score_for_confidence(confidence)
    )
    phat = k / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return max(0.0, (center - margin) / denom)


def _z_score_for_confidence(confidence: float) -> float:
    from scipy.stats import norm
    return norm.ppf(1 - (1 - confidence) / 2)


def fit_conservative_calibration(
    raw_scores: np.ndarray, labels: np.ndarray,
    n_bins: int = 10, confidence: float = 0.95,
) -> IsotonicRegression:
    """Fit an isotonic calibrator whose targets are each bin's Wilson LOWER
    bound win rate, not the raw empirical mean — the "more accurate than
    liberal" mechanism: every calibration target understates confidence by
    a statistically principled margin that shrinks as bin sample size grows.

    Bins are equal-frequency (by rank), not equal-width, so every bin has a
    real sample count."""
    raw_scores = np.asarray(raw_scores, dtype=float)
    labels = np.asarray(labels, dtype=float)
    order = np.argsort(raw_scores)
    sorted_scores = raw_scores[order]
    sorted_labels = labels[order]

    bin_edges = np.array_split(np.arange(len(sorted_scores)), n_bins)
    midpoints, targets = [], []
    for idx in bin_edges:
        if len(idx) == 0:
            continue
        bin_scores = sorted_scores[idx]
        bin_labels = sorted_labels[idx]
        k = int(bin_labels.sum())
        n = len(bin_labels)
        midpoints.append(float(bin_scores.mean()))
        targets.append(wilson_lower_bound(k, n, confidence))

    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(midpoints, targets)
    return calibrator
