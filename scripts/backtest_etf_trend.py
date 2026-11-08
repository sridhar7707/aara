"""Backtest of the ETF trend rule that produced the in-sample PASS (ADR-081 next steps, ADR-082).

Provenance (quant review finding 9): this file is the committed copy of the scratch scripts trend_etf.py
(rule, folds, per-fold table) and risk_verdict.py (the three pass criteria). Run from the repo root:

    python scripts/backtest_etf_trend.py                  # reads data/raw/<SYMBOL>.csv
    python scripts/backtest_etf_trend.py --raw <dir>      # raw CSVs somewhere else

It NEEDS the raw price CSVs (data/raw/<SYMBOL>.csv for the 12 ETFs and SPY; first column the date, a
"close" column). They are not in git. Without them it exits with an error.

DEFINITION THAT WAS TESTED (do not edit to match anything else; change it only as a new, labelled test):
  - Frequency: MONTHLY. Closes are month-end closes (daily closes resampled with .resample("ME").last()).
  - Trend window: 10 MONTHS, a rolling mean of the last 10 month-end closes, current month-end included.
    It is NOT a 210-trading-day mean of daily closes. bot/execution/etf_paper.py uses TREND_WINDOW = 210
    daily closes as a proxy for this; that proxy was NOT what this backtest tested.
  - Signal: an ETF is held for month t+1 when its month-end close at t is strictly above its 10-month mean
    (signal.shift(1): decided at month-end t, earns month t+1). A mean that is still NaN (fewer than 10
    month-ends) counts as not held.
  - Weights: equal weight among the held ETFs; all cash (zero return) when none is held.
  - Cost: 10 bps (0.0010) per unit of turnover, turnover = sum of absolute monthly weight changes. The first
    month's entry from cash is not charged (diff() of the first row is treated as zero).
  - Universe (12): XLC XLE XLF XLI XLK XLP XLV XLY GLD TLT QQQ IWM. Benchmark: SPY, month-end to month-end.
  - Return of a month: sum(weight * ETF monthly pct_change, NaN as 0). Cash earns 0.
  - Folds (5): 2014-2016, 2017-2019 (to 06-30), 2019-2021 (from 07-01), 2022-2023, 2024-2026 (to 2026-07-22).
  - Pass criteria (risk_verdict.py), all three required:
      1. full-sample max drawdown of the strategy <= 0.60 x SPY's max drawdown
      2. full-sample annualised monthly Sharpe (mean/std * sqrt(12)) of the strategy >= SPY's
      3. strategy max drawdown smaller than SPY's in at least 3 of the 5 folds
  - Also printed, as in the scratch run: per-fold annualised return, Sharpe and excess vs SPY, and the full
    sample Newey-West t of monthly excess return (2 lags). The 12-1 momentum rule that the scratch script
    printed "for information only" is not reproduced here.
  - Data note: the "close" column in data/raw is used as stored; the scratch run did no further adjustment.
Result recorded when this was run (raw data ending 2026-07-22): VERDICT PASS (DD ratio 0.50, Sharpe 0.83 vs
0.75, smaller drawdown in 4/5 folds). It is an IN-SAMPLE result on the same history the rule was chosen from.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, as in other scripts
from scripts.validate_signal import newey_west_t  # noqa: E402

ETFS = ["XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLV", "XLY", "GLD", "TLT", "QQQ", "IWM"]
TREND_MONTHS = 10   # rolling mean of the last 10 month-end closes (NOT 210 trading days)
COST = 0.0010       # per unit of turnover
FOLDS = [("2014-2016", "2014-01-01", "2016-12-31"), ("2017-2019", "2017-01-01", "2019-06-30"),
         ("2019-2021", "2019-07-01", "2021-12-31"), ("2022-2023", "2022-01-01", "2023-12-31"),
         ("2024-2026", "2024-01-01", "2026-07-22")]
DD_RATIO_MAX = 0.60
MIN_FOLDS_BETTER = 3


def load_close(raw: Path, symbol: str) -> pd.Series:
    path = raw / f"{symbol}.csv"
    if not path.exists():
        raise SystemExit(f"missing {path}: this backtest needs the raw CSVs (see --raw).")
    d = pd.read_csv(path, index_col=0, parse_dates=True)
    d.columns = [c.lower() for c in d.columns]
    return d["close"]


def load_prices(raw: Path) -> pd.DataFrame:
    return pd.DataFrame({s: load_close(raw, s) for s in ETFS + ["SPY"]}).sort_index()


def strategy_returns(px: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(strategy monthly returns net of cost, SPY monthly returns) for the tested rule."""
    m = px.resample("ME").last()                  # month-end closes
    mret = m.pct_change()
    sig = (m > m.rolling(TREND_MONTHS).mean()).astype(float)
    held = sig.shift(1)[ETFS]                     # decide at month-end t, earn month t+1
    n = held.sum(axis=1)
    w = held.div(n.replace(0, np.nan), axis=0).fillna(0.0)   # equal weight among held, cash when none
    r = (w * mret[ETFS].fillna(0.0)).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    return (r - COST * turnover).dropna(), mret["SPY"]


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    return float(((eq / eq.cummax()) - 1).min())


def sharpe(x: pd.Series) -> float:
    return float(x.mean() / x.std() * np.sqrt(12))


def fold_table(r: pd.Series, spy: pd.Series) -> pd.DataFrame:
    ex = (r - spy.reindex(r.index)).dropna()
    rows = []
    for name, a, b in FOLDS:
        seg, sseg, rs = ex.loc[a:b], spy.loc[a:b], r.loc[a:b]
        if len(seg) < 12:
            continue
        rows.append(dict(fold=name, strat_ann=round(rs.mean() * 12 * 100, 2), spy_ann=round(sseg.mean() * 12 * 100, 2),
                         strat_sharpe=round(sharpe(rs), 2) if rs.std() else np.nan,
                         spy_sharpe=round(sharpe(sseg), 2), excess_ann=round(seg.mean() * 12 * 100, 2)))
    rows.append(dict(fold="FULL", strat_ann=round(r.mean() * 12 * 100, 2),
                     spy_ann=round(spy.reindex(r.index).mean() * 12 * 100, 2),
                     excess_ann=round(ex.mean() * 12 * 100, 2), nw_t_monthly=round(newey_west_t(ex, lags=2), 2)))
    return pd.DataFrame(rows)


def verdict(r: pd.Series, spy: pd.Series) -> tuple[bool, list[str]]:
    """The three criteria from risk_verdict.py. Returns (passed, report lines)."""
    s = spy.reindex(r.index).dropna()
    r = r.reindex(s.index)
    ratio = max_drawdown(r) / max_drawdown(s)
    lines = [f"full: strategy maxDD {max_drawdown(r) * 100:.1f}%, SPY {max_drawdown(s) * 100:.1f}%, ratio {ratio:.2f}"]
    better = 0
    for name, a, b in FOLDS:
        rs, ss = r.loc[a:b], s.loc[a:b]
        ok = max_drawdown(rs) > max_drawdown(ss)   # less negative = smaller drawdown
        better += ok
        lines.append(f"  {name}: strategy maxDD {max_drawdown(rs) * 100:.1f}%, SPY {max_drawdown(ss) * 100:.1f}%, "
                     f"strategy smaller: {ok}")
    c1, c2, c3 = ratio <= DD_RATIO_MAX, sharpe(r) >= sharpe(s), better >= MIN_FOLDS_BETTER
    lines += [f"Sharpe strategy {sharpe(r):.2f} vs SPY {sharpe(s):.2f}",
              f"criterion 1 (DD ratio <= {DD_RATIO_MAX:.2f}): {c1}",
              f"criterion 2 (Sharpe >= SPY): {c2}",
              f"criterion 3 (smaller DD in >={MIN_FOLDS_BETTER} folds): {c3} ({better}/{len(FOLDS)})",
              "VERDICT: " + ("PASS" if (c1 and c2 and c3) else "FAIL")]
    return bool(c1 and c2 and c3), lines


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Backtest of the 10-month month-end trend rule (see module docstring).")
    ap.add_argument("--raw", default="data/raw", help="directory holding <SYMBOL>.csv (default data/raw, from the repo root)")
    args = ap.parse_args(argv[1:])
    px = load_prices(Path(args.raw))
    r, spy = strategy_returns(px)
    pd.set_option("display.width", 220)
    print(fold_table(r, spy).to_string(index=False))
    passed, lines = verdict(r, spy)
    print("\n".join(lines))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
