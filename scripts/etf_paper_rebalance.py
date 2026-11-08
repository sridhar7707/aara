"""ADR-083 / ADR-085 runner: month-end rebalance of the ETF trend overlay on the shared PAPER account.

    python scripts/etf_paper_rebalance.py --sleeve 5000                # dry run (default), reads the account
    python scripts/etf_paper_rebalance.py --sleeve 5000 --execute      # submit paper orders

--sleeve is the dollars the overlay manages. Only overlay symbols are planned or counted.
Both modes read the account read-only (cash, equity, holdings, open orders) and refuse if it cannot be read.
Refusals, in both modes: data/HALT_TRADING exists; the account is trading_blocked; an overlay symbol is
already held or has an open order; the sleeve exceeds 10% of equity or the buys breach the cash reserve.
--execute is also refused until SHARED_ACCOUNT_EXECUTE_APPROVED is set (ADR-085 open item 1), before 16:30
New York time, and if the run log already has an execute row (started, executed or failed) for the month.
Orders carry a deterministic client_order_id; a "started" row is written to the run log before the first submit.
Measurement (quant review finding 3): every run row carries sleeve_value (overlay market value now) and
account_equity. Every execute run first records fills for earlier "submitted" orders into fills.csv
(append only; an order is re-checked until it reaches a terminal status, then never again).
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, as in other scripts
from bot.execution.etf_paper import (  # noqa: E402
    ETF_UNIVERSE, assert_paper_endpoint, check_sleeve, client_order_id, overlay_symbols_in,
    overlay_value_ok, plan_orders, trend_targets,
)
from config import ALPACA_BASE_URL, MIN_CASH_RESERVE_PCT  # noqa: E402

# ADR-085 open item 1: the owner must accept running the overlay on the shared account before this is True.
SHARED_ACCOUNT_EXECUTE_APPROVED = False

LOG_DIR = Path("data/etf_paper")
RUNS = LOG_DIR / "runs_v2.csv"   # runs.csv had an older 6-column header and is no longer read (C3)
ORDERS = LOG_DIR / "orders.csv"
FILLS = LOG_DIR / "fills.csv"
TERMINAL_STATUSES = {"filled", "canceled", "expired", "rejected"}   # a fill row with one of these is final
HALT_FILE = Path(__file__).resolve().parent.parent / "data" / "HALT_TRADING"  # same file bot/main.py checks
HISTORY_DAYS = 400
EXECUTE_NOT_BEFORE = time(16, 30)
NY = ZoneInfo("America/New_York")


@dataclass
class AccountState:
    client: object
    cash: float
    equity: float
    trading_blocked: bool
    held_symbols: list[str]                 # overlay symbols currently held
    values: dict[str, float] = field(default_factory=dict)
    qty: dict[str, float] = field(default_factory=dict)
    open_order_symbols: list[str] = field(default_factory=list)   # overlay symbols with an open order


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


def _read_account(client) -> AccountState:
    """Read-only account snapshot: account, positions and open orders. Raises if any read fails."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    acct = client.get_account()
    overlay = [p for p in client.get_all_positions() if p.symbol in ETF_UNIVERSE]
    open_orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))
    return AccountState(
        client=client, cash=float(acct.cash), equity=float(acct.equity),
        trading_blocked=bool(acct.trading_blocked),
        held_symbols=overlay_symbols_in(p.symbol for p in overlay),
        values={p.symbol: float(p.market_value) for p in overlay},
        qty={p.symbol: float(p.qty) for p in overlay},
        open_order_symbols=overlay_symbols_in(o.symbol for o in open_orders))


def _account() -> AccountState:
    from alpaca.trading.client import TradingClient
    from config import ALPACA_KEY, ALPACA_SECRET
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise SystemExit("ALPACA_KEY / ALPACA_SECRET not set (paper account); cannot read the account.")
    try:
        return _read_account(TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True))
    except Exception as exc:
        raise SystemExit(f"refusing: cannot read the paper account ({type(exc).__name__}: {exc}).")


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    if not new:
        with path.open(newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
        if header != list(row):
            raise RuntimeError(f"{path} header {header} does not match the row {list(row)}; "
                               "refusing to append misaligned columns")
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def _run_row(mode: str, as_of, sleeve: float, cash: float, status: str, error: str,
             weights: dict, plan: list[dict], sleeve_value: float, account_equity: float) -> dict:
    return {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": mode,
            "as_of": str(as_of), "sleeve": round(sleeve, 2), "cash": round(cash, 2), "status": status,
            "error": error, "held": ";".join(sorted(weights)),
            "orders": ";".join(f"{p['side']}:{p['symbol']}" for p in plan),
            "sleeve_value": round(sleeve_value, 2), "account_equity": round(account_equity, 2)}


def _enum_text(value) -> str:
    """'OrderStatus.FILLED' / enum / 'filled' -> 'filled'."""
    text = str(getattr(value, "value", value))
    return text.rsplit(".", 1)[-1].lower()


def _record_fills(client) -> None:
    """Append a fills.csv row for each earlier 'submitted' order that has no final fill recorded.

    Append only. A failed lookup is logged to stderr and skipped; this step never blocks a rebalance.
    An order whose latest status is not terminal (e.g. still accepted) is looked up again next time.
    """
    try:
        if not ORDERS.exists():
            return
        orders = pd.read_csv(ORDERS, dtype=str, keep_default_na=False)
        submitted = orders[(orders["status"] == "submitted") & (orders["order_id"] != "")]
        final: set[str] = set()
        if FILLS.exists():
            fills = pd.read_csv(FILLS, dtype=str, keep_default_na=False)
            final = set(fills.loc[fills["status"].isin(TERMINAL_STATUSES), "order_id"])
    except Exception as exc:
        print(f"WARNING: fills step skipped, cannot read the order/fill logs ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return
    for _, o in submitted.drop_duplicates("order_id").iterrows():
        oid = o["order_id"]
        if oid in final:
            continue
        try:
            order = client.get_order_by_id(oid)
            _append(FILLS, {
                "order_id": oid, "symbol": o["symbol"], "side": o["side"],
                "filled_qty": getattr(order, "filled_qty", None) or 0,
                "filled_avg_price": getattr(order, "filled_avg_price", None) or "",
                "status": _enum_text(order.status),
                "checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        except Exception as exc:
            print(f"WARNING: fill lookup failed for order {oid} ({o['side']} {o['symbol']}): "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)


def _already_executed(month: str) -> bool:
    """True if runs_v2.csv has any execute row (started, executed or failed) for the month."""
    if not RUNS.exists():
        return False
    rows = pd.read_csv(RUNS, dtype=str)
    missing = {"mode", "as_of"} - set(rows.columns)
    if missing:
        raise RuntimeError(f"{RUNS} is missing columns {sorted(missing)}; refusing to guess whether this month ran")
    done = rows[(rows["mode"] == "execute") & (rows["as_of"].astype(str).str[:7] == month)]
    return not done.empty


def _refuse_if_unsafe(state: AccountState, sleeve: float) -> None:
    """Account-level refusals shared by dry run and execute."""
    if state.trading_blocked:
        raise SystemExit("refusing: the account reports trading_blocked.")
    if state.open_order_symbols:
        raise SystemExit(f"refusing: open orders exist for overlay symbols {state.open_order_symbols}; "
                         "wait for them to fill or cancel them.")
    if state.held_symbols:
        raise SystemExit(f"refusing: overlay symbols already held {state.held_symbols}; "
                         "the operator must clear them first.")
    if not overlay_value_ok(state.values, sleeve):
        raise SystemExit(f"refusing: overlay holdings ${sum(state.values.values()):,.2f} exceed "
                         f"1.05 x the sleeve ${sleeve:,.2f}.")


def _execute_plan(client, plan: list[dict], month: str, as_of) -> tuple[str, str]:
    """Submit the plan. Returns (status, error). Stops on the first failed submit.

    If the order log cannot be written after a successful submit, the order id goes to stderr and the
    error is re-raised: a submitted order is never recorded as failed with an empty id.
    """
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    for p in plan:
        coid = client_order_id(month, p["symbol"], p["side"])
        base = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "as_of": str(as_of),
                "symbol": p["symbol"], "side": p["side"], "notional": p["notional"], "qty": p["qty"]}
        try:
            if p["side"] == "sell":
                req = MarketOrderRequest(symbol=p["symbol"], qty=p["qty"], side=OrderSide.SELL,
                                         time_in_force=TimeInForce.DAY, client_order_id=coid)
            else:
                req = MarketOrderRequest(symbol=p["symbol"], notional=p["notional"], side=OrderSide.BUY,
                                         time_in_force=TimeInForce.DAY, client_order_id=coid)
            order = client.submit_order(order_data=req)
        except Exception as exc:  # stop on the first failure; the order log shows what went out
            error = f"{p['side']} {p['symbol']}: {type(exc).__name__}: {exc}"
            print(f"  FAILED {error}", file=sys.stderr)
            _append(ORDERS, {**base, "order_id": "", "status": f"error: {exc}"})
            return "failed", error
        try:
            _append(ORDERS, {**base, "order_id": str(order.id), "status": "submitted"})
        except Exception:
            print(f"ORDER SUBMITTED but the order log write failed: {p['side']} {p['symbol']} "
                  f"order_id={order.id} client_order_id={coid}", file=sys.stderr)
            raise
        print(f"  submitted {p['side']} {p['symbol']}: order {order.id}")
    return "executed", ""


def _verify_after(client, sleeve: float) -> None:
    """Re-read positions after the orders; warn (never reverse orders) if overlay value exceeds the sleeve."""
    try:
        fresh = {p.symbol: float(p.market_value) for p in client.get_all_positions() if p.symbol in ETF_UNIVERSE}
    except Exception as exc:
        print(f"WARNING: post-run position read failed ({type(exc).__name__}: {exc}); "
              "overlay value not verified.", file=sys.stderr)
        return
    if not overlay_value_ok(fresh, sleeve):
        print(f"WARNING: overlay holdings ${sum(fresh.values()):,.2f} exceed 1.05 x the sleeve ${sleeve:,.2f} "
              "after the run. Orders were not reversed; review the account.", file=sys.stderr)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sleeve", type=float, required=True, help="dollars the overlay manages")
    ap.add_argument("--execute", action="store_true", help="submit paper orders")
    args = ap.parse_args(argv[1:])

    assert_paper_endpoint(ALPACA_BASE_URL)
    if args.execute and not SHARED_ACCOUNT_EXECUTE_APPROVED:
        raise SystemExit("refusing to execute: the owner must accept ADR-085 open item 1 first "
                         "(set SHARED_ACCOUNT_EXECUTE_APPROVED in this script).")
    if HALT_FILE.exists():
        raise SystemExit(f"refusing: {HALT_FILE} exists (emergency halt). Delete it to resume.")

    now_ny = datetime.now(NY)
    closes = _closes()
    as_of = closes.index[-1].date()
    month = str(as_of)[:7]
    if args.execute:
        if now_ny.time() < EXECUTE_NOT_BEFORE:
            raise SystemExit(f"refusing to execute before {EXECUTE_NOT_BEFORE:%H:%M} New York time "
                             f"(now {now_ny:%H:%M}); run after the close.")
        if as_of != now_ny.date():
            raise SystemExit(f"latest bar is {as_of}, not today ({now_ny.date()}); no final close yet.")
        if _already_executed(month):
            raise SystemExit(f"already executed for {month}; one rebalance per month.")

    state = _account()   # read-only, identical in dry run and execute
    if args.execute:
        _record_fills(state.client)   # before the safety refusals: pending orders are what they would trip on
    _refuse_if_unsafe(state, args.sleeve)

    prices = {s: float(closes[s].iloc[-1]) for s in closes.columns}
    weights = trend_targets(closes)
    plan = plan_orders(args.sleeve, state.values, state.qty, weights, prices, cash_available=state.cash)
    cash_after_buys = state.cash - sum(p["notional"] for p in plan if p["side"] == "buy")
    try:
        check_sleeve(args.sleeve, state.equity, cash_after_buys, MIN_CASH_RESERVE_PCT)
    except ValueError as exc:
        raise SystemExit(f"refusing: {exc}")

    print(f"as of {as_of} | sleeve ${args.sleeve:,.2f} | held by rule: {sorted(weights)} | "
          f"cash ${state.cash:,.2f} | equity ${state.equity:,.2f}")
    for p in plan:
        amount = f"qty {p['qty']}" if p["side"] == "sell" else f"notional {p['notional']:,.2f}"
        print(f"  {p['side']:4s} {p['symbol']:4s} {amount}")
    if not plan:
        print("  no trades needed")

    mode = "execute" if args.execute else "dry_run"
    status, error = "dry_run", ""
    sleeve_value, equity = float(sum(state.values.values())), state.equity
    if args.execute:
        _append(RUNS, _run_row(mode, as_of, args.sleeve, state.cash, "started", "", weights, plan,
                               sleeve_value, equity))
        status, error = _execute_plan(state.client, plan, month, as_of)
        _verify_after(state.client, args.sleeve)
    _append(RUNS, _run_row(mode, as_of, args.sleeve, state.cash, status, error, weights, plan,
                           sleeve_value, equity))
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
