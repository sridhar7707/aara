"""Tests for analytics/stat_tests.py."""
import math
import random

import pytest

from analytics.stat_tests import (
    deflated_sharpe,
    expectancy_stats,
    expected_max_sharpe,
    permutation_pvalue,
    probabilistic_sharpe,
    small_sample_warning,
    wilson_interval,
)


def test_expected_max_sharpe_rises_with_trials():
    e10 = expected_max_sharpe(10, 1.0)
    e100 = expected_max_sharpe(100, 1.0)
    e1000 = expected_max_sharpe(1000, 1.0)
    assert 0 < e10 < e100 < e1000


def test_expected_max_sharpe_needs_two_trials():
    with pytest.raises(ValueError):
        expected_max_sharpe(1, 1.0)


def test_psr_is_half_when_sharpe_equals_benchmark():
    assert probabilistic_sharpe(0.1, 0.1, 252, 0.0, 3.0) == pytest.approx(0.5)


def test_psr_rejects_tiny_samples_and_bad_denominator():
    with pytest.raises(ValueError):
        probabilistic_sharpe(0.1, 0.0, 2, 0.0, 3.0)
    with pytest.raises(ValueError):
        probabilistic_sharpe(1.0, 0.0, 252, 10.0, 3.0)  # 1 - 10*1 + 0.5*1 = -8.5 < 0


def test_deflated_sharpe_falls_as_trials_grow():
    few = deflated_sharpe(0.15, 5, 0.01, 500, 0.0, 3.0)
    many = deflated_sharpe(0.15, 500, 0.01, 500, 0.0, 3.0)
    assert many < few


def test_small_sample_warning():
    assert small_sample_warning(20) is not None
    assert small_sample_warning(500) is None


def test_wilson_interval_for_65_of_100():
    lo, hi = wilson_interval(65, 100)
    assert 0.55 < lo < 0.56
    assert 0.73 < hi < 0.745


def test_permutation_p_is_never_zero():
    pred = [True] * 200
    outcome = [True] * 200  # perfect hits, the smallest possible p
    res = permutation_pvalue(pred, outcome, n_perm=500, seed=1)
    assert res["p_value_one_sided"] >= 1 / 501


def test_permutation_detects_real_skill():
    rng = random.Random(7)
    outcome = [rng.random() < 0.5 for _ in range(300)]
    pred = [o if rng.random() < 0.8 else (not o) for o in outcome]  # 80% accurate
    res = permutation_pvalue(pred, outcome, n_perm=2000, seed=2)
    assert res["p_value_one_sided"] < 0.01
    assert res["hit_rate"] > 0.7


def test_permutation_random_predictions_not_significant():
    rng = random.Random(11)
    outcome = [rng.random() < 0.5 for _ in range(300)]
    pred = [rng.random() < 0.5 for _ in range(300)]
    res = permutation_pvalue(pred, outcome, n_perm=2000, seed=3)
    assert res["p_value_one_sided"] > 0.05


def test_always_up_base_rate_is_reported():
    pred = [True] * 10
    outcome = [True] * 6 + [False] * 4
    res = permutation_pvalue(pred, outcome, n_perm=100, seed=0)
    assert res["always_up_hit_rate"] == pytest.approx(0.6)
    assert res["hit_rate"] == pytest.approx(0.6)


def test_circular_method_runs():
    pred = [True, False] * 50
    outcome = [True, False] * 50
    res = permutation_pvalue(pred, outcome, n_perm=200, seed=4, method="circular")
    assert res["method"] == "circular"


def test_permutation_rejects_bad_input():
    with pytest.raises(ValueError):
        permutation_pvalue([True], [True, False])
    with pytest.raises(ValueError):
        permutation_pvalue([True], [True], method="bogus")


def test_expectancy_stats_on_known_series():
    returns = [0.02, 0.02, -0.01, 0.02, -0.01, 0.02, -0.01, 0.02]
    s = expectancy_stats(returns, n_boot=500, seed=0)
    assert s["expectancy"] == pytest.approx(sum(returns) / len(returns))
    assert s["payoff_ratio"] == pytest.approx(0.02 / 0.01)
    assert s["profit_factor"] == pytest.approx(0.10 / 0.03)  # five 0.02 wins, three -0.01 losses
    lo, hi = s["bootstrap_ci_95"]
    assert lo < s["expectancy"] < hi


def test_expectancy_needs_two_returns():
    with pytest.raises(ValueError):
        expectancy_stats([0.01])


def test_no_nan_leak_in_sharpe_inputs():
    assert not math.isnan(deflated_sharpe(0.1, 10, 0.02, 300, -0.2, 4.0))
