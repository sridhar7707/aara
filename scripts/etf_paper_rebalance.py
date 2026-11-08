"""ADR-083 runner: month-end rebalance of the ETF trend overlay on the PAPER account.

    python scripts/etf_paper_rebalance.py                 # dry run, needs no keys
    python scripts/etf_paper_rebalance.py --equity 10000  # dry run with a stated equity
    python scripts/etf_paper_rebalance.py --execute       # submit paper orders (needs ETF_PAPER_KEY/SECRET)

Dry run is the default. Nothing is submitted without --execute. The endpoint guard refuses
any URL other than the paper endpoint, before any call is made.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, as in other scripts
from bot.execution.etf_paper import ETF_UNIVERSE, PAPER_URL, assert_paper_endpoint, plan_orders, trend_targets

LOG = Path("data/etf_paper/runs.csv")
HISTORY_DAYS = 400


def _closes() -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(ETF_UNIVERSE, period=f"{HISTORY_DAYS}d", interval="1d", progress=False,
                      auto_adjust=True, group_by="ticker", threads=True)
    return pd.DataFrame({s: raw[s]["Close"] for s in ETF_UNIVERSE if s in raw.columns.get_level_values(0)}).sort_index()


def _account(url: str):
    from alpaca.trading.client import TradingClient
    key, secret = os.getenv("ETF_PAPER_KEY", ""), os.getenv("ETF_PAPER_SECRET", "")
    if not key or not secret:
        raise SystemExit("ETF_PAPER_KEY / ETF_PAPER_SECRET not set. Use a dedicated paper account (ADR-083).")
    client = TradingClient(key, secret, paper=True)
    equity = float(client.get_account().equity)
    values = {p.symbol: float(p.market_value) for p in client.get_all_positions()}
    return client, equity, values


def _log(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execute", action="store_true", help="submit paper orders")
    ap.add_argument("--equity", type=float, default=None, help="dry-run only: equity to plan against")
    args = ap.parse_args(argv[1:])

    url = os.getenv("ETF_PAPER_BASE_URL", PAPER_URL)
    assert_paper_endpoint(url)

    closes = _closes()
    prices = {s: float(closes[s].iloc[-1]) for s in closes.columns}
    weights = trend_targets(closes)

    if args.execute:
        client, equity, current = _account(url)
    else:
        if args.equity is None:
            print("Dry run needs --equity (no account is read). Example: --equity 10000")
            return 2
        client, equity, current = None, args.equity, {}

    plan = plan_orders(equity, current, weights, prices)
    print(f"as of {closes.index[-1].date()} | equity {equity:,.2f} | held by rule: {sorted(weights)}")
    for p in plan:
        amount = f"qty {p['qty']}" if p["side"] == "sell" else f"notional {p['notional']:,.2f}"
        print(f"  {p['side']:4s} {p['symbol']:4s} {amount}")
    if not plan:
        print("  no trades needed")

    if args.execute:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
        for p in plan:
            if p["side"] == "sell":
                req = MarketOrderRequest(symbol=p["symbol"], qty=p["qty"], side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
            else:
                req = MarketOrderRequest(symbol=p["symbol"], notional=p["notional"], side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
            order = client.submit_order(order_data=req)
            print(f"  submitted {p['side']} {p['symbol']}: order {order.id}")
            p["order_id"] = str(order.id)

    _log({"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "execute" if args.execute else "dry_run",
          "as_of": str(closes.index[-1].date()), "equity": round(equity, 2),
          "held": ";".join(sorted(weights)), "orders": ";".join(f"{p['side']}:{p['symbol']}" for p in plan)})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
