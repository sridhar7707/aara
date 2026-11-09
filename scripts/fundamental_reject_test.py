"""ADR-089: fundamentals reject-only test on free data (SEC EDGAR + yfinance).

Universe: current S&P 500 members (survivorship-biased: a REJECT is informative, a pass is not).
Signals (fixed in ADR-089): ROE = annual net income / equity; earnings yield = annual net income / market cap.
Point-in-time: a figure is used only from its SEC filing date onward.
Target: one-month forward excess return over SPY. Criteria and statistics: scripts/validate_signal.py.

Run from the repo root:  python scripts/fundamental_reject_test.py
Caches EDGAR and price data under data/fundamental_test/ (git-ignored).
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.validate_signal import FoldResult, newey_west_t, verdict  # noqa: E402

CACHE = Path("data/fundamental_test")
FACTS_DIR = CACHE / "facts"
HEADERS = {"User-Agent": "AARA-research-reject-test (contact via repository owner)"}
MEMBERS_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
START, END = "2009-01-01", "2026-07-31"
SAMPLE_START, SAMPLE_END = "2013-01-01", "2026-06-30"   # month-end signal dates
COST = 0.0020                                            # 20 bp round trip (ADR-089)
FOLDS = [("2014-2016", "2014-01-01", "2016-12-31"), ("2017-2019", "2017-01-01", "2019-12-31"),
         ("2019-2021", "2019-07-01", "2021-12-31"), ("2022-2023", "2022-01-01", "2023-12-31"),
         ("2024-2026", "2024-01-01", "2026-06-30")]


def members() -> list[str]:
    html = requests.get(MEMBERS_URL, headers=HEADERS, timeout=60).text
    table = pd.read_html(io.StringIO(html))[0]
    return table["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()


def cik_map() -> dict[str, int]:
    tick = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=60).json()
    out = {}
    for v in tick.values():
        out.setdefault(v["ticker"].replace("-", "."), int(v["cik_str"]))
    return out


def fetch_facts(cik: int) -> dict | None:
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = FACTS_DIR / f"{cik:010d}.json"
    if not path.exists():
        time.sleep(0.12)
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                         headers=HEADERS, timeout=60)
        if r.status_code != 200:
            return None
        path.write_text(r.text, encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def _records(section: dict, concept: str, unit_key: str, annual: bool) -> pd.DataFrame:
    """(end, filed, val) rows from one taxonomy section ('us-gaap' or 'dei').
    Annual income uses 10-K full-year durations; equity and shares are instants."""
    rows = []
    node = section.get(concept, {}).get("units", {}).get(unit_key, [])
    for x in node:
        if "filed" not in x or "end" not in x or "val" not in x:
            continue
        if annual:
            if x.get("form") != "10-K" or x.get("fp") != "FY" or "start" not in x:
                continue
            days = (pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).days
            if not 350 <= days <= 380:
                continue
        rows.append((pd.Timestamp(x["end"]), pd.Timestamp(x["filed"]), float(x["val"])))
    return pd.DataFrame(rows, columns=["end", "filed", "val"]).sort_values("filed").drop_duplicates(["end", "filed"])


def asof_value(frame: pd.DataFrame, when: pd.Timestamp) -> float | None:
    """Latest value whose filing date is on or before `when` (point-in-time)."""
    if frame is None or frame.empty:
        return None
    known = frame[frame["filed"] <= when]
    if known.empty:
        return None
    return float(known.sort_values("filed").iloc[-1]["val"])


def download_prices(symbols: list[str]) -> pd.DataFrame:
    import yfinance as yf
    frames = {}
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        raw = yf.download(batch, start=START, end=END, interval="1d", progress=False,
                          auto_adjust=True, group_by="ticker", threads=True)
        for s in batch:
            try:
                col = raw[s]["Close"] if len(batch) > 1 else raw["Close"]
                frames[s] = col
            except KeyError:
                continue
    return pd.DataFrame(frames).sort_index()


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    syms = members()
    ciks = cik_map()
    print(f"members: {len(syms)}")

    shares_dfs, ni_dfs, eq_dfs = {}, {}, {}
    for s in syms:
        cik = ciks.get(s) or ciks.get(s.replace("-", "."))
        if cik is None:
            continue
        facts = fetch_facts(cik)
        if not facts:
            continue
        gaap = facts.get("facts", {}).get("us-gaap", {})
        dei = facts.get("facts", {}).get("dei", {})
        ni = _records(gaap, "NetIncomeLoss", "USD", annual=True)
        eq = _records(gaap, "StockholdersEquity", "USD", annual=False)
        sh = _records(dei, "EntityCommonStockSharesOutstanding", "shares", annual=False)
        if ni.empty or eq.empty:
            continue
        ni_dfs[s], eq_dfs[s], shares_dfs[s] = ni, eq, sh
    print(f"companies with usable facts: {len(ni_dfs)}")

    px = download_prices(sorted(ni_dfs.keys()) + ["SPY"])
    all_month_ends = px.resample("ME").last().index
    pairs = [(all_month_ends[i], all_month_ends[i + 1]) for i in range(len(all_month_ends) - 1)
             if pd.Timestamp(SAMPLE_START) <= all_month_ends[i] <= pd.Timestamp(SAMPLE_END)]

    roe_rows, ey_rows, fwd_rows = {}, {}, {}
    for m, nxt_day in pairs:
        month_row = px.loc[:m].iloc[-1]
        nxt_row = px.loc[:nxt_day].iloc[-1]
        spy_fwd = nxt_row["SPY"] / month_row["SPY"] - 1
        roe, ey, fwd = {}, {}, {}
        for s in ni_dfs:
            p0, p1 = month_row.get(s), nxt_row.get(s)
            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                continue
            ni = asof_value(ni_dfs[s], m)
            eq = asof_value(eq_dfs[s], m)
            sh = asof_value(shares_dfs.get(s), m)
            if ni is None or eq is None or eq <= 0:
                continue
            roe[s] = ni / eq
            if sh and sh > 0:
                ey[s] = ni / (p0 * sh)
            fwd[s] = p1 / p0 - 1 - spy_fwd
        roe_rows[m], ey_rows[m], fwd_rows[m] = roe, ey, fwd

    def monthly_series(rows: dict[pd.Timestamp, dict]) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
        ic, spread = {}, {}
        for m, sig in rows.items():
            f = fwd_rows[m]
            common = [s for s in sig if s in f]
            if len(common) < 30:
                continue
            x = pd.Series({s: sig[s] for s in common})
            y = pd.Series({s: f[s] for s in common})
            ic[m] = x.rank().corr(y.rank())
            r = x.rank(pct=True)
            spread[m] = y[r >= 0.9].mean() - y[r <= 0.1].mean() - COST
        return pd.Series(ic).sort_index(), pd.Series(spread).sort_index(), None

    results = []
    lines = ["# ADR-089 results (reject-only, survivorship-biased)", ""]
    for label, rows in [("ROE (quality)", roe_rows), ("Earnings yield (value)", ey_rows)]:
        ic, spread, _unused = monthly_series(rows)
        full_t = newey_west_t(ic, lags=2)
        folds = []
        for name, a, b in FOLDS:
            ic_f = ic.loc[a:b]
            sp_f = spread.loc[a:b]
            if len(ic_f) < 6:
                continue
            folds.append(FoldResult(name, float(ic_f.mean()), newey_west_t(ic_f, lags=2),
                                    float(sp_f.mean()), int(len(ic_f))))
        result, reasons = verdict(folds, full_t)
        line = (f"{label}: months={len(ic)}, mean IC={ic.mean():+.4f}, full NW t={full_t:+.2f}, "
                f"folds={len(folds)}, verdict={result}" + (f" ({'; '.join(reasons)})" if reasons else ""))
        print(line)
        lines.append(f"- {line}")
        for f in folds:
            lines.append(f"  - {f.name}: mean IC {f.mean_ic:+.4f}, NW t {f.nw_t:+.2f}, "
                         f"net spread {f.net_spread * 100:+.2f}% /month, months {f.n_days}")
        results.append((label, result))
    lines.append("")
    lines.append("Outcome: " + ", ".join(f"{k} = {v}" for k, v in results)
                 + ". A REJECT closes the signal. NOT REJECTED is not a confirmation (survivorship bias).")
    out = Path("docs/analysis/ADR-089-results.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
