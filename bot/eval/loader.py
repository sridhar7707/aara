"""Data loading utilities for the evaluation framework.

All public functions return DataFrames with consistent column names
that metrics.py and ablation.py expect.
"""
from __future__ import annotations
import sqlite3

import pandas as pd

from config import TRADE_DB_PATH


def _con(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, check_same_thread=False)


def load_completed_trades(
    db_path: str = TRADE_DB_PATH,
    days: int = 365,
    con: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Load BUY→SELL round-trip pairs with component scores captured at entry.

    Each real SELL is attributed to the most recent BUY for that symbol at or
    before the SELL's timestamp. A BUY can therefore collect several SELL rows
    — a partial fill followed by the remainder close — and those are folded
    into ONE completed round trip: shares and realized P&L summed, exit price
    notional-weighted, and the final SELL's timestamp / reason / holding_days
    taken as the trip's close. This is the only reliable link without a
    foreign-key trade_id column.
    SELL_RECONCILE and SELL_TRIM rows are excluded entirely (not just their
    P&L) — neither represents a real close (a reconcile never really
    happened; a trim is a partial sell that leaves the position open, per
    bot/_main_positions.py::_trim_position()).

    Returned columns:
      symbol, buy_ts, sell_ts, entry_price, exit_price, exit_shares,
      pnl_pct, holding_days, realized_pnl, regime, exit_reason,
      xgb_prob, lstm_prob, sentiment_score, macro_score, ensemble_score,
      stop_loss, take_profit, risk_reward_ratio, notional, portfolio_value
    """
    cutoff = (pd.Timestamp.now() - pd.Timedelta(days=days)).isoformat()
    _own_con = con is None
    if _own_con:
        con = _con(db_path)
    try:
        buys = pd.read_sql_query(
            """
            SELECT rowid            AS _id,
                   symbol,
                   timestamp        AS buy_ts,
                   price            AS entry_price,
                   notional,
                   portfolio_value,
                   xgb_prob,
                   lstm_prob,
                   sentiment_score,
                   macro_score,
                   ensemble_score,
                   regime,
                   stop_loss,
                   take_profit,
                   risk_reward_ratio
            FROM trades
            WHERE action = 'BUY' AND timestamp >= ?
            ORDER BY symbol, timestamp, rowid
            """,
            con, params=[cutoff],
        )
        sells = pd.read_sql_query(
            """
            SELECT rowid      AS _id,
                   symbol,
                   timestamp  AS sell_ts,
                   price      AS exit_price,
                   shares,
                   notional,
                   pnl_pct,
                   holding_days,
                   realized_pnl,
                   action     AS exit_reason
            FROM trades
            WHERE action LIKE 'SELL%' AND action NOT IN ('SELL_RECONCILE', 'SELL_TRIM')
              AND timestamp >= ?
            ORDER BY symbol, timestamp, rowid
            """,
            con, params=[cutoff],
        )
    finally:
        if _own_con:
            con.close()

    if buys.empty or sells.empty:
        return pd.DataFrame()

    buys["_rank"]  = buys.groupby("symbol").cumcount()

    sells["shares"]       = pd.to_numeric(sells["shares"],       errors="coerce").fillna(0.0)
    sells["notional"]     = pd.to_numeric(sells["notional"],     errors="coerce").fillna(0.0)
    sells["pnl_pct"]      = pd.to_numeric(sells["pnl_pct"],      errors="coerce").fillna(0.0)
    sells["holding_days"] = pd.to_numeric(sells["holding_days"], errors="coerce").fillna(0.0)
    sells["realized_pnl"] = pd.to_numeric(sells["realized_pnl"], errors="coerce").fillna(0.0)

    # Attribute each real SELL to the most recent BUY for that symbol, by
    # chronological row order (timestamp then rowid -- rowid breaks ties when
    # several trades land in the same wall-clock microsecond). Walk buys and
    # sells together per symbol counting buys seen: a BUY's rank is (buys so
    # far - 1); a SELL takes the rank of the last BUY before it. SELLs with no
    # preceding BUY get rank -1 and are dropped as orphans. Because a SELL only
    # advances the counter via BUY rows, a partial fill and its later remainder
    # close land on the SAME rank and are folded into one round trip below.
    _b = buys[["symbol", "buy_ts", "_id"]].rename(columns={"buy_ts": "_ts"})
    _b["_is_buy"] = 1
    _s = sells[["symbol", "sell_ts", "_id"]].rename(columns={"sell_ts": "_ts"})
    _s["_is_buy"] = 0
    stream = pd.concat([_b, _s], ignore_index=True).sort_values(
        ["symbol", "_ts", "_id"], kind="stable"
    )
    stream["_rank"] = stream.groupby("symbol")["_is_buy"].cumsum() - 1
    sell_ranks = stream.loc[stream["_is_buy"] == 0, ["symbol", "_id", "_rank"]]

    sells = sells.merge(sell_ranks, on=["symbol", "_id"], how="left")
    sells = sells[sells["_rank"] >= 0]
    if sells.empty:
        return pd.DataFrame()

    # Fold the (possibly multiple) SELLs of one BUY into a single round trip:
    # sum shares and realized P&L, notional-weight the exit price, and take the
    # final SELL's timestamp / reason / holding_days as the trip's close.
    sells = sells.sort_values(["symbol", "_rank", "sell_ts", "_id"])
    agg = sells.groupby(["symbol", "_rank"], as_index=False).agg(
        sell_ts=("sell_ts", "last"),
        exit_shares=("shares", "sum"),
        _exit_notional=("notional", "sum"),
        realized_pnl=("realized_pnl", "sum"),
        pnl_pct=("pnl_pct", "last"),
        holding_days=("holding_days", "last"),
        exit_reason=("exit_reason", "last"),
    )
    agg["exit_price"] = [
        (n / s if s else 0.0) for n, s in zip(agg["_exit_notional"], agg["exit_shares"])
    ]
    agg = agg.drop(columns=["_exit_notional"])

    merged = pd.merge(buys, agg, on=["symbol", "_rank"], how="inner").drop(
        columns=["_rank", "_id"]
    )
    merged["buy_ts"]       = pd.to_datetime(merged["buy_ts"],  utc=True, errors="coerce")
    merged["sell_ts"]      = pd.to_datetime(merged["sell_ts"], utc=True, errors="coerce")
    merged["pnl_pct"]      = pd.to_numeric(merged["pnl_pct"],      errors="coerce").fillna(0.0)
    merged["holding_days"] = pd.to_numeric(merged["holding_days"], errors="coerce").fillna(0.0)
    merged["realized_pnl"] = pd.to_numeric(merged["realized_pnl"], errors="coerce").fillna(0.0)
    # Defensive sanity check: a sell can never close a buy that hasn't happened
    # yet. The chronological walk already enforces this, but keep the guard in
    # case of coerced-NaT rows slipping through.
    merged = merged[merged["sell_ts"] >= merged["buy_ts"]]
    return merged.reset_index(drop=True)


def load_equity_curve(
    db_path: str = TRADE_DB_PATH,
    days: int = 365,
    con: sqlite3.Connection | None = None,
) -> pd.Series:
    """Daily equity curve from portfolio_snapshots.

    Returns Series[datetime → portfolio_value], last snapshot per day.
    Empty Series when no data exists.
    """
    cutoff = (pd.Timestamp.now() - pd.Timedelta(days=days)).isoformat()
    _own_con = con is None
    if _own_con:
        con = _con(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT timestamp, portfolio_value FROM portfolio_snapshots
            WHERE timestamp >= ? AND portfolio_value > 0
            ORDER BY timestamp ASC
            """,
            con, params=[cutoff],
        )
    finally:
        if _own_con:
            con.close()

    if df.empty:
        return pd.Series(dtype=float)

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).set_index("timestamp")
    return df["portfolio_value"].resample("1D").last().dropna()


def load_signal_log(
    db_path: str = TRADE_DB_PATH,
    days: int = 90,
    con: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """All per-cycle signal evaluations, including cycles where no trade fired.

    Columns: timestamp, symbol, xgb_prob, lstm_prob, sentiment_score,
             macro_score, ensemble_score, ensemble_action, regime
    """
    cutoff = (pd.Timestamp.now() - pd.Timedelta(days=days)).isoformat()
    _own_con = con is None
    if _own_con:
        con = _con(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT timestamp, symbol, xgb_prob, lstm_prob, sentiment_score,
                   macro_score, ensemble_score, ensemble_action, regime
            FROM signal_log
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            con, params=[cutoff],
        )
    finally:
        if _own_con:
            con.close()

    if df.empty:
        return pd.DataFrame()

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df.reset_index(drop=True)


def fetch_spy_daily(days: int = 365) -> pd.Series:
    """Fetch SPY daily returns from yfinance.

    Returns Series[datetime.date → daily_pct_return], empty on failure.
    """
    try:
        import yfinance as yf
        spy = yf.download("SPY", period=f"{days}d", progress=False, auto_adjust=True)
        if spy.empty:
            return pd.Series(dtype=float)
        closes = spy["Close"].squeeze()
        rets = closes.pct_change().dropna()
        rets.index = pd.to_datetime(rets.index).date
        return rets
    except Exception:
        return pd.Series(dtype=float)
