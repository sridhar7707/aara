"""Forward-test log for ADR-082. Append-only, one snapshot per trading day.

    python scripts/forward_log.py snapshot   # record today's membership, scores and prices
    python scripts/forward_log.py evaluate   # score the log against its own forward returns

Files (under data/forward_log/, gitignored because they are data):
    members/<date>.txt   S&P 500 constituents on that date, as listed
    prices.csv           date, symbol, close   (every symbol that day)
    scores.csv           date, symbol, score_momentum, trend_on   (ADR-082 rules A and B)

A snapshot for a date that is already logged is refused. Rows are never edited.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Run as a script (python scripts/forward_log.py), the repo root is not on sys.path, so the
# scripts package that evaluate() imports cannot be found. Add the root explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LOG_DIR = Path("data/forward_log")


class SkipDay(Exception):
    """An expected, non-error refusal: weekend, stale bar (holiday or not yet published), or already logged."""


class SnapshotError(Exception):
    """A real failure: empty or incomplete data, or a half-written log. Exits 1 so the job turns red."""
MEMBERS_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
ETFS = ["XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLV", "XLY", "GLD", "TLT", "QQQ", "IWM"]
BENCH = "SPY"
MOM_LOOKBACK, MOM_SKIP = 252, 21     # 12-1 momentum
TREND_WINDOW = 210                  # proxy for a 10-month moving average
HORIZON = 21                        # forward window, trading days
MIN_HISTORY = MOM_LOOKBACK + 1
MAX_HORIZON_CALENDAR_DAYS = 35   # 21 trading days span 29-31 calendar days; more means a gap


def momentum_score(closes: pd.DataFrame) -> pd.Series:
    """12-1 momentum on the last row: close(t-21) / close(t-252) - 1, per column."""
    if len(closes) < MIN_HISTORY:
        raise ValueError(f"need {MIN_HISTORY} daily closes, have {len(closes)}")
    return closes.iloc[-1 - MOM_SKIP] / closes.iloc[-1 - MOM_LOOKBACK] - 1


def trend_on(closes: pd.DataFrame) -> pd.Series:
    """True where the last close is above its trailing TREND_WINDOW mean."""
    if len(closes) < TREND_WINDOW:
        raise ValueError(f"need {TREND_WINDOW} daily closes, have {len(closes)}")
    return closes.iloc[-1] > closes.iloc[-TREND_WINDOW:].mean()


def _download_closes(symbols: list[str], days: int = 400) -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(symbols, period=f"{days}d", interval="1d", progress=False,
                      auto_adjust=True, group_by="ticker", threads=True)
    frames = {}
    for s in symbols:
        try:
            frames[s] = raw[s]["Close"] if len(symbols) > 1 else raw["Close"]
        except KeyError:
            continue
    return pd.DataFrame(frames).sort_index()


def current_members() -> list[str]:
    import requests
    html = requests.get(MEMBERS_URL, headers={"User-Agent": "AARA-forward-log (contact via repository owner)"},
                        timeout=60).text
    table = pd.read_html(io.StringIO(html))[0]
    return sorted(table["Symbol"].astype(str).str.replace(".", "-", regex=False))


def _logged_dates(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(pd.read_csv(path, usecols=["date"])["date"].astype(str))


def snapshot(today: str | None = None, members: list[str] | None = None) -> str:
    """Record one trading-day snapshot. Refuses if today's date is already logged."""
    today = today or pd.Timestamp.now(tz="America/New_York").date().isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    prices_path, scores_path = LOG_DIR / "prices.csv", LOG_DIR / "scores.csv"
    in_scores = today in _logged_dates(scores_path)
    in_prices = today in _logged_dates(prices_path)
    if in_scores != in_prices:
        raise SnapshotError(f"{today} is in one log file but not the other; the log needs manual repair.")
    if in_scores:
        raise SkipDay(f"{today} is already logged; the log is append-only.")

    if pd.Timestamp(today).weekday() >= 5:
        raise SkipDay(f"{today} is a weekend; no trading-day snapshot.")
    members = members or current_members()

    # Validate everything before writing anything, so a refused day leaves no trace.
    closes = _download_closes(sorted(set(members) | set(ETFS) | {BENCH}))
    if closes.empty:
        raise SnapshotError("price download returned no data (rate limit or outage); this is an error, not a skip.")
    if closes.index[-1].date().isoformat() != today:
        # Expected on market holidays, and on runs before the bar is published (the workflow retries).
        raise SkipDay(f"latest price bar is {closes.index[-1].date()}, not {today}; not logging a stale day.")
    # Completeness is checked on TODAY's row, not just on the index: a partial final bar must not be logged.
    closes = closes.dropna(axis=1, thresh=MIN_HISTORY)
    last_ok = closes.iloc[-1].notna()
    covered = sum(1 for m in members if m in closes.columns and bool(last_ok.get(m, False)))
    if covered < 0.95 * len(members):
        raise SnapshotError(f"only {covered}/{len(members)} members have today's price; refusing an incomplete day.")
    if not bool(last_ok.get(BENCH, False)):
        raise SnapshotError("benchmark (SPY) has no price today; refusing the day.")

    (LOG_DIR / "members").mkdir(exist_ok=True)
    (LOG_DIR / "members" / f"{today}.txt").write_text("\n".join(members), encoding="utf-8")

    mom = momentum_score(closes[[c for c in members if c in closes.columns]])
    tr = trend_on(closes[[c for c in ETFS if c in closes.columns]])
    scores = pd.concat([
        pd.DataFrame({"date": today, "symbol": mom.index, "score_momentum": mom.values, "trend_on": np.nan}),
        pd.DataFrame({"date": today, "symbol": tr.index, "score_momentum": np.nan,
                      "trend_on": tr.astype(float).values}),
    ], ignore_index=True)
    last = closes.iloc[-1]
    prices = pd.DataFrame({"date": today, "symbol": last.index, "close": last.values}).dropna()

    scores.to_csv(scores_path, mode="a", header=not scores_path.exists(), index=False)
    prices.to_csv(prices_path, mode="a", header=not prices_path.exists(), index=False)
    return f"logged {today}: {len(mom)} momentum scores, {len(tr)} trend signals, {len(prices)} prices"


def evaluate(horizon: int = HORIZON) -> dict:
    """Score the log against its own forward excess returns (rule A), and summarise rule B."""
    from scripts.validate_signal import evaluate_fold, newey_west_t, verdict, daily_rank_ic
    prices = pd.read_csv(LOG_DIR / "prices.csv", parse_dates=["date"])
    scores = pd.read_csv(LOG_DIR / "scores.csv", parse_dates=["date"])
    px = prices.pivot_table(index="date", columns="symbol", values="close").sort_index()
    fwd = px.shift(-horizon) / px - 1
    # A row shift is only a 21-trading-day window if no days are missing. Mask any forward
    # return whose window spans more than the calendar span of a normal 21-day horizon.
    dates = pd.Series(px.index, index=px.index)
    span = (dates.shift(-horizon) - dates).dt.days
    fwd = fwd.where(span.le(MAX_HORIZON_CALENDAR_DAYS), np.nan)
    bench = fwd[BENCH] if BENCH in fwd else None
    fwd = fwd.sub(bench, axis=0) if bench is not None else fwd
    a = scores.dropna(subset=["score_momentum"]).pivot_table(index="date", columns="symbol", values="score_momentum")
    a, fwd_a = a.align(fwd, join="inner", axis=0)
    fwd_a = fwd_a[a.columns.intersection(fwd_a.columns)]
    a = a[fwd_a.columns]
    if len(a) < 2 * horizon:
        return {"status": "too few days to evaluate", "days": int(len(a))}
    full = evaluate_fold("forward_full", a, fwd_a)
    ic = daily_rank_ic(a, fwd_a)
    full_t = newey_west_t(ic, horizon - 1)
    quarters = []
    for q, sub in a.groupby(a.index.to_period("Q")):
        if len(sub) >= 20:
            quarters.append(evaluate_fold(str(q), sub, fwd_a.loc[sub.index]))
    result, reasons = verdict(quarters, full_t) if quarters else ("KILL", ["no quarters with data"])
    return {"status": result, "reasons": reasons, "days": int(len(a)), "full": full,
            "nw_t_full": full_t, "quarters": quarters}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"snapshot", "evaluate"}:
        print(__doc__)
        return 2
    if argv[1] == "snapshot":
        try:
            print(snapshot())
        except SkipDay as e:
            print(f"SKIP: {e}")   # expected: exit 0, so the scheduled job does not show as failed
        except SnapshotError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1              # real failure: the job turns red and someone looks
        return 0
    else:
        r = evaluate()
        print(r.get("status"), r.get("reasons", ""), f"days={r.get('days')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
