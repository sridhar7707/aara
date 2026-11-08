"""ADR-083 / ADR-085 runner: month-end rebalance of the ETF trend overlay on the shared PAPER account.

    python scripts/etf_paper_rebalance.py --sleeve 5000                # dry run (default), reads no account
    python scripts/etf_paper_rebalance.py --sleeve 5000 --execute      # submit paper orders

--sleeve is the dollars the overlay manages. Only overlay symbols are planned or counted.
--execute is refused before 16:30 New York time, so the month-end decision uses the final close,
and refused if the paper log already has an execute for the same month (one rebalance a month).
Every order is written to the order log as it is submitted, so a failure mid-run is on record.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, as in other scripts
from bot.execution.etf_paper import ETF_UNIVERSE, assert_paper_endpoint, plan_orders, trend_targets  # noqa: E402

LOG_DIR = Path("data/etf_paper")
RUNS = LOG_DIR / "runs.csv"
ORDERS = LOG_DIR / "orders.csv"
HISTORY_DAYS = 400
EXECUTE_NOT_BEFORE = time(16, 30)
NY = ZoneInfo("America/New_York")


def _closes() -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(ETF_UNIVERSE, period=f"{HISTORY_DAYS}d", interval="1d", progress=False,
                      auto_adjust=True, group_by="ticker", threads=True)
    frames = {}
    for s in ETF_UNIVERSE:
        try:
            frames[s] = raw[s]["Close"]
        except KeyError:
            continue
    return pd.DataFrame(frames).sort_index()


def _account():
    from alpaca.trading.client import TradingClient
    from config import ALPACA_KEY, ALPACA_SECRET
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise SystemExit("ALPACA_KEY / ALPACA_SECRET not set (paper account).")
    client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
    acct = client.get_account()
    overlay = [p for p in client.get_all_positions() if p.symbol in ETF_UNIVERSE]
    values = {p.symbol: float(p.market_value) for p in overlay}
    qty = {p.symbol: float(p.qty) for p in overlay}
    return client, float(acct.cash), values, qty


def _append(path: Path, row: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def _already_executed(month: str) -> bool:
    if not RUNS.exists():
        return False
    rows = pd.read_csv(RUNS)
    done = rows[(rows["mode"] == "execute") & (rows["as_of"].astype(str).str[:7] == month)]
    return not done.empty


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sleeve", type=float, required=True, help="dollars the overlay manages")
    ap.add_argument("--execute", action="store_true", help="submit paper orders")
    args = ap.parse_args(argv[1:])

    from config import ALPACA_BASE_URL
    assert_paper_endpoint(ALPACA_BASE_URL)

    now_ny = datetime.now(NY)
    closes = _closes()
    as_of = closes.index[-1].date()
    if args.execute:
        if now_ny.time() < EXECUTE_NOT_BEFORE:
            raise SystemExit(f"refusing to execute before {EXECUTE_NOT_BEFORE:%H:%M} New York time "
                             f"(now {now_ny:%H:%M}); run after the close.")
        if as_of != now_ny.date():
            raise SystemExit(f"latest bar is {as_of}, not today ({now_ny.date()}); no final close yet.")
        if _already_executed(str(as_of)[:7]):
            raise SystemExit(f"already executed for {str(as_of)[:7]}; one rebalance per month.")

    prices = {s: float(closes[s].iloc[-1]) for s in closes.columns}
    weights = trend_targets(closes)

    if args.execute:
        client, cash, current, current_qty = _account()
    else:
        client, cash, current, current_qty = None, args.sleeve, {}, {}

    plan = plan_orders(args.sleeve, current, current_qty, weights, prices, cash_available=cash)
    print(f"as of {as_of} | sleeve ${args.sleeve:,.2f} | held by rule: {sorted(weights)} | cash ${cash:,.2f}")
    for p in plan:
        amount = f"qty {p['qty']}" if p["side"] == "sell" else f"notional {p['notional']:,.2f}"
        print(f"  {p['side']:4s} {p['symbol']:4s} {amount}")
    if not plan:
        print("  no trades needed")

    status, error = ("dry_run", "")
    if args.execute:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
        status = "executed"
        for p in plan:
            try:
                if p["side"] == "sell":
                    req = MarketOrderRequest(symbol=p["symbol"], qty=p["qty"], side=OrderSide.SELL,
                                             time_in_force=TimeInForce.DAY)
                else:
                    req = MarketOrderRequest(symbol=p["symbol"], notional=p["notional"], side=OrderSide.BUY,
                                             time_in_force=TimeInForce.DAY)
                order = client.submit_order(order_data=req)
                _append(ORDERS, {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "as_of": str(as_of), "symbol": p["symbol"], "side": p["side"],
                                 "notional": p["notional"], "qty": p["qty"], "order_id": str(order.id),
                                 "status": "submitted"})
                print(f"  submitted {p['side']} {p['symbol']}: order {order.id}")
            except Exception as exc:  # stop on the first failure; the order log shows what went out
                status, error = "failed", f"{p['side']} {p['symbol']}: {type(exc).__name__}: {exc}"
                _append(ORDERS, {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "as_of": str(as_of), "symbol": p["symbol"], "side": p["side"],
                                 "notional": p["notional"], "qty": p["qty"], "order_id": "",
                                 "status": f"error: {exc}"})
                print(f"  FAILED {error}", file=sys.stderr)
                break

    _append(RUNS, {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "execute" if args.execute else "dry_run",
                   "as_of": str(as_of), "sleeve": round(args.sleeve, 2), "cash": round(cash, 2), "status": status,
                   "error": error, "held": ";".join(sorted(weights)),
                   "orders": ";".join(f"{p['side']}:{p['symbol']}" for p in plan)})
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
