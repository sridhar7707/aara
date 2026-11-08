"""Pre-registered signal validation (ADR-081 step 4).

Given a daily cross-section of scores and forward excess returns, reports:
- daily rank information coefficient (IC), with a Newey-West t-statistic that accounts for
  overlapping forward-return windows;
- the top-minus-bottom decile spread, net of a round-trip cost assumption;
- a PASS / KILL verdict against criteria fixed before the test is run.

The criteria are constants below. Change them only through an ADR, never after seeing results.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZON = 21                 # forward window in trading days; overlap lag = HORIZON - 1
ROUND_TRIP_COST = 0.0020     # 20 bps round trip, applied to each decile spread
MIN_NW_T = 2.0               # full-period IC t-statistic must exceed this
MIN_POSITIVE_FOLDS = 4       # out of 5 folds, the net spread must be positive
MIN_FOLDS = 5


@dataclass(frozen=True)
class FoldResult:
    name: str
    mean_ic: float
    nw_t: float
    net_spread: float         # mean daily top-minus-bottom decile excess return, after cost
    n_days: int


def newey_west_t(series: pd.Series, lags: int) -> float:
    """t-statistic of the mean of a series, Newey-West (Bartlett kernel) variance."""
    x = series.dropna().to_numpy(dtype=float)
    n = len(x)
    if n < 3:
        return float("nan")
    mu = x.mean()
    e = x - mu
    gamma0 = float(e @ e) / n
    lrv = gamma0
    for k in range(1, min(lags, n - 1) + 1):
        gamma_k = float(e[k:] @ e[:-k]) / n
        lrv += 2.0 * (1.0 - k / (lags + 1.0)) * gamma_k
    se = np.sqrt(max(lrv, 1e-18) / n)
    return float(mu / se) if se > 0 else float("nan")


def daily_rank_ic(score: pd.DataFrame, fwd: pd.DataFrame, min_names: int = 20) -> pd.Series:
    """Spearman rank IC per date. score and fwd are dates x symbols, aligned."""
    out = {}
    for d in score.index.intersection(fwd.index):
        s = score.loc[d]
        y = fwd.loc[d]
        ok = s.notna() & y.notna()
        if ok.sum() < min_names:
            continue
        out[d] = s[ok].rank().corr(y[ok].rank())
    return pd.Series(out, dtype=float).sort_index()


def daily_decile_spread(score: pd.DataFrame, fwd: pd.DataFrame, min_names: int = 20,
                        cost: float = ROUND_TRIP_COST) -> pd.Series:
    """Top-decile minus bottom-decile mean forward return per date, net of round-trip cost."""
    out = {}
    for d in score.index.intersection(fwd.index):
        s = score.loc[d]
        y = fwd.loc[d]
        ok = s.notna() & y.notna()
        if ok.sum() < min_names:
            continue
        r = s[ok].rank(pct=True)
        yy = y[ok]
        top = yy[r >= 0.9].mean()
        bot = yy[r <= 0.1].mean()
        out[d] = (top - bot) - cost
    return pd.Series(out, dtype=float).sort_index()


def evaluate_fold(name: str, score: pd.DataFrame, fwd: pd.DataFrame) -> FoldResult:
    ic = daily_rank_ic(score, fwd)
    spread = daily_decile_spread(score, fwd)
    return FoldResult(
        name=name,
        mean_ic=float(ic.mean()) if len(ic) else float("nan"),
        nw_t=newey_west_t(ic, HORIZON - 1),
        net_spread=float(spread.mean()) if len(spread) else float("nan"),
        n_days=int(len(ic)),
    )


def verdict(folds: list[FoldResult], full_nw_t: float) -> tuple[str, list[str]]:
    """PASS only if every pre-registered criterion holds. Returns (verdict, reasons)."""
    reasons: list[str] = []
    if len(folds) < MIN_FOLDS:
        reasons.append(f"only {len(folds)} folds; {MIN_FOLDS} required")
    if not np.isfinite(full_nw_t) or full_nw_t < MIN_NW_T:
        reasons.append(f"full-period NW t {full_nw_t:.2f} < {MIN_NW_T}")
    positive = sum(1 for f in folds if np.isfinite(f.net_spread) and f.net_spread > 0)
    if positive < MIN_POSITIVE_FOLDS:
        reasons.append(f"net spread positive in {positive} folds; {MIN_POSITIVE_FOLDS} required")
    return ("PASS" if not reasons else "KILL"), reasons
