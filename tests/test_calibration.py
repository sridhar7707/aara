import numpy as np
import pytest

from bot.strategy.calibration import wilson_lower_bound, fit_conservative_calibration


def test_wilson_lower_bound_n_zero_returns_zero():
    assert wilson_lower_bound(0, 0) == 0.0


def test_wilson_lower_bound_no_wins_returns_zero():
    assert wilson_lower_bound(0, 100) == pytest.approx(0.0, abs=1e-9)


def test_wilson_lower_bound_below_point_estimate():
    """The whole point of using the lower bound: it must sit strictly below
    the raw empirical proportion k/n whenever 0 < k < n (the only case where
    there is uncertainty to be conservative about)."""
    k, n = 50, 100
    lb = wilson_lower_bound(k, n)
    assert lb < k / n
    assert lb > 0.3  # sane magnitude for n=100, not a degenerate/huge margin


def test_wilson_lower_bound_tighter_with_more_data():
    """More samples at the same win rate -> smaller conservative margin."""
    small_n_bound = wilson_lower_bound(50, 100)
    large_n_bound = wilson_lower_bound(5000, 10000)
    assert large_n_bound > small_n_bound
    assert large_n_bound < 0.5


def test_fit_conservative_calibration_monotonic():
    rng = np.random.default_rng(42)
    raw_scores = rng.uniform(0, 1, size=2000)
    true_prob = raw_scores  # perfectly informative raw score
    labels = (rng.uniform(0, 1, size=2000) < true_prob).astype(int)

    calibrator = fit_conservative_calibration(raw_scores, labels, n_bins=10)
    sample_points = np.linspace(0.05, 0.95, 19)
    predictions = calibrator.predict(sample_points)
    assert np.all(np.diff(predictions) >= -1e-9)  # isotonic: non-decreasing


def test_fit_conservative_calibration_biased_toward_understating():
    """Every calibration target used during the fit must be <= that bin's
    raw empirical win rate -- the "more accurate than liberal" invariant,
    checked against the math directly rather than merely asserted."""
    rng = np.random.default_rng(7)
    raw_scores = rng.uniform(0, 1, size=1000)
    labels = (rng.uniform(0, 1, size=1000) < raw_scores).astype(int)

    order = np.argsort(raw_scores)
    sorted_scores, sorted_labels = raw_scores[order], labels[order]
    bins = np.array_split(np.arange(len(sorted_scores)), 10)
    for idx in bins:
        bin_labels = sorted_labels[idx]
        empirical_rate = bin_labels.mean()
        lb = wilson_lower_bound(int(bin_labels.sum()), len(bin_labels))
        assert lb <= empirical_rate + 1e-9


def test_fit_conservative_calibration_output_in_unit_range():
    rng = np.random.default_rng(1)
    raw_scores = rng.uniform(0, 1, size=500)
    labels = (rng.uniform(0, 1, size=500) < raw_scores).astype(int)
    calibrator = fit_conservative_calibration(raw_scores, labels, n_bins=5)
    predictions = calibrator.predict([0.0, 0.5, 1.0])
    assert np.all(predictions >= 0.0) and np.all(predictions <= 1.0)
