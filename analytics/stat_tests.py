"""Statistical checks for strategy and forecast logs (pure functions, stdlib only).

Units: every Sharpe-like input (sr, var_trials, sr_benchmark) must be per-period and
non-annualized, all at the same frequency as the returns used to estimate it. Callers
that hold annualized figures must de-annualize before calling these functions.

Observations: n_obs must be the count of independent observations. Overlapping holding
periods or same-day symbols make trades dependent; use daily portfolio returns, or pass
an effective N.
"""
from __future__ import annotations

import math
import random
from statistics import NormalDist, fmean, stdev

EULER_GAMMA = 0.5772156649
SMALL_SAMPLE_N = 50  # skew and kurtosis are unreliable below about this many observations

_NORMAL = NormalDist()


def small_sample_warning(n_obs: int) -> str | None:
    if n_obs < SMALL_SAMPLE_N:
        return (f"n_obs={n_obs} is below {SMALL_SAMPLE_N}: skew and kurtosis are unreliable, "
                "so treat the deflated Sharpe as indicative only")
    return None


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """Expected maximum Sharpe across n_trials independent trials with null mean 0.

    Formula from Bailey and Lopez de Prado (2014), appendix code:
    maxZ = (1 - g) * Phi^-1(1 - 1/N) + g * Phi^-1(1 - 1/(N*e)).
    """
    if n_trials < 2:
        raise ValueError("n_trials must be at least 2 (Phi^-1(0) is undefined)")
    if var_sr < 0:
        raise ValueError("var_sr must be non-negative")
    max_z = ((1 - EULER_GAMMA) * _NORMAL.inv_cdf(1 - 1 / n_trials)
             + EULER_GAMMA * _NORMAL.inv_cdf(1 - 1 / (n_trials * math.e)))
    return math.sqrt(var_sr) * max_z


def probabilistic_sharpe(sr: float, sr_benchmark: float, n_obs: int,
                         skew: float, kurt: float) -> float:
    """Probability that the true Sharpe exceeds sr_benchmark. kurt is raw (3 for normal)."""
    if n_obs < 3:
        raise ValueError("n_obs must be at least 3")
    denom_sq = 1 - skew * sr + (kurt - 1) / 4 * sr * sr
    if denom_sq <= 0:
        raise ValueError("non-positive variance term: check skew, kurt and sr")
    z = (sr - sr_benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom_sq)
    return _NORMAL.cdf(z)


def deflated_sharpe(sr: float, n_trials: int, var_trials: float, n_obs: int,
                    skew: float, kurt: float) -> float:
    """PSR with the benchmark raised to the expected maximum across n_trials."""
    benchmark = expected_max_sharpe(n_trials, var_trials)
    return probabilistic_sharpe(sr, benchmark, n_obs, skew, kurt)


def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% interval for a hit rate. Pass effective N when trades are dependent."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def permutation_pvalue(predicted_up: list[bool], outcome_up: list[bool], n_perm: int = 10000,
                       seed: int = 0, method: str = "iid") -> dict:
    """One-sided test that the hit rate beats chance.

    method="iid": shuffle outcomes. Use only when observations are independent.
    method="circular": rotate outcomes by a random offset, keeping their autocorrelation.
    Returns the observed hit rate, the always-up base rate (a hit rate above 50% can come
    from drift alone), and p = (k + 1) / (B + 1), which is never zero.
    """
    if len(predicted_up) != len(outcome_up) or not predicted_up:
        raise ValueError("predictions and outcomes must be non-empty and the same length")
    if method not in ("iid", "circular"):
        raise ValueError("method must be 'iid' or 'circular'")
    n = len(predicted_up)
    observed = sum(p == o for p, o in zip(predicted_up, outcome_up))
    base_rate = sum(outcome_up) / n
    rng = random.Random(seed)
    outcomes = list(outcome_up)
    at_least = 0
    for _ in range(n_perm):
        if method == "iid":
            rng.shuffle(outcomes)
            shuffled = outcomes
        else:
            k = rng.randrange(n)
            shuffled = outcome_up[k:] + outcome_up[:k]
        hits = sum(p == o for p, o in zip(predicted_up, shuffled))
        if hits >= observed:
            at_least += 1
    p_value = (at_least + 1) / (n_perm + 1)
    return {
        "n": n,
        "hit_rate": observed / n,
        "always_up_hit_rate": base_rate,
        "p_value_one_sided": p_value,
        "n_perm": n_perm,
        "method": method,
    }


def expectancy_stats(returns: list[float], n_boot: int = 5000, seed: int = 0) -> dict:
    """Mean return per trade, t-statistic, bootstrap 95% CI, payoff ratio, profit factor."""
    if len(returns) < 2:
        raise ValueError("need at least 2 returns")
    mean = fmean(returns)
    sd = stdev(returns)
    t_stat = mean / (sd / math.sqrt(len(returns))) if sd > 0 else float("nan")
    rng = random.Random(seed)
    boots = sorted(fmean(rng.choices(returns, k=len(returns))) for _ in range(n_boot))
    lo, hi = boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    avg_win = fmean(wins) if wins else 0.0
    avg_loss = fmean(losses) if losses else 0.0
    gross_loss = -sum(losses)
    return {
        "n": len(returns),
        "expectancy": mean,
        "t_stat": t_stat,
        "bootstrap_ci_95": (lo, hi),
        "payoff_ratio": (avg_win / -avg_loss) if avg_loss < 0 else float("nan"),
        "profit_factor": (sum(wins) / gross_loss) if gross_loss > 0 else float("nan"),
    }
