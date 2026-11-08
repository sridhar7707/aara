"""ADR-081 step 4: signal validation harness, criteria and corrected statistics."""
import numpy as np
import pandas as pd

from scripts import validate_signal as vs


def test_newey_west_matches_plain_t_for_independent_series():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0.1, 1.0, 5000))
    plain = x.mean() / (x.std(ddof=0) / np.sqrt(len(x)))
    assert abs(vs.newey_west_t(x, lags=0) - plain) < 1e-9
    assert abs(vs.newey_west_t(x, lags=20) - plain) < 0.5  # close for iid data


def test_newey_west_is_smaller_for_overlapping_windows():
    """Overlapping 21-day windows: the naive t overstates significance; NW corrects it."""
    rng = np.random.default_rng(1)
    base = rng.normal(0.0, 1.0, 5000 + 21)
    overlap = pd.Series([base[i:i + 21].sum() for i in range(5000)])  # MA of iid noise
    naive = overlap.mean() / (overlap.std(ddof=0) / np.sqrt(len(overlap)))
    nw = vs.newey_west_t(overlap, lags=20)
    assert abs(nw) < abs(naive)


def _panel(signal: float, n_days=400, n_names=40, seed=2):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_days, freq="B")
    cols = [f"S{i}" for i in range(n_names)]
    score = pd.DataFrame(rng.normal(size=(n_days, n_names)), index=idx, columns=cols)
    fwd = pd.DataFrame(rng.normal(size=(n_days, n_names)) * 0.02 + signal * score.values * 0.02,
                       index=idx, columns=cols)
    return score, fwd


def test_no_signal_is_not_significant_and_killed():
    score, fwd = _panel(signal=0.0)
    f = vs.evaluate_fold("null", score, fwd)
    assert abs(f.mean_ic) < 0.05
    assert f.net_spread < 0  # cost makes a null spread negative


def test_strong_signal_is_detected():
    score, fwd = _panel(signal=1.0)
    f = vs.evaluate_fold("strong", score, fwd)
    assert f.mean_ic > 0.2
    assert f.nw_t > vs.MIN_NW_T


def test_verdict_requires_all_criteria():
    good = [vs.FoldResult(f"f{i}", 0.05, 3.0, 0.004, 300) for i in range(5)]
    assert vs.verdict(good, full_nw_t=3.0) == ("PASS", [])
    assert vs.verdict(good[:4], full_nw_t=3.0)[0] == "KILL"           # too few folds
    assert vs.verdict(good, full_nw_t=1.0)[0] == "KILL"               # insufficient t
    mixed = good[:3] + [vs.FoldResult("x", 0, 0, -0.001, 1), vs.FoldResult("y", 0, 0, -0.001, 1)]
    assert vs.verdict(mixed, full_nw_t=3.0)[0] == "KILL"              # only 3 positive folds
