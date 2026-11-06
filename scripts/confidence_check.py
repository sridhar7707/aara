"""Check if the bot is ready to graduate from paper trading to real money."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import sqlite3
import numpy as np
from loguru import logger
from config import TRADE_DB_PATH, BENCHMARK
import yfinance as yf
from datetime import datetime, timedelta, timezone
import bot.monitor.telegram_bot as tg

THRESHOLDS = {
    "min_days": 60,
    "min_win_rate": 0.52,
    "min_win_rate_trades": 30,  # ADR-081 3.2: fewer closed exits than this is UNKNOWN, not a pass
    "min_sharpe": 1.0,
    "max_drawdown": 0.15,
    "max_consecutive_losing_days": 4,
    # "Adapts and learns" gate (distinct from the performance gate above) --
    # the user's real-money condition is explicitly two-part: good enough
    # performance AND genuine adaptive/learning behavior, not just a date.
    "adaptive_learning_min_commits": 3,     # fewer than this → status UNKNOWN, not FAIL
    "adaptive_learning_max_auc_decline": 0.02,
    "adaptive_learning_min_auc": 0.52,
    "adaptive_learning_max_stale_days": 10,  # retrain.yml runs weekly; 10d of silence is a real stall
}


def load_trades():
    con = sqlite3.connect(TRADE_DB_PATH)
    try:
        rows = con.execute(
            "SELECT timestamp, action, pnl_pct, portfolio_value FROM trades ORDER BY timestamp"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        con.close()
    return rows


def _daily_close_values(trades: list) -> list:
    """One portfolio snapshot per trading weekday (last trade of day), forward-filled for no-trade days.
    Quiet days contribute zero return rather than being excluded — prevents Sharpe inflation.
    """
    import datetime as dt
    daily: dict[str, float] = {}
    for ts, action, pnl_pct, pv in trades:
        daily[ts[:10]] = pv  # last trade of each day wins
    if not daily:
        return []
    keys = sorted(daily.keys())
    start_d = dt.date.fromisoformat(keys[0])
    end_d   = dt.date.fromisoformat(keys[-1])
    result, prev_val, d = [], daily[keys[0]], start_d
    while d <= end_d:
        ds = d.isoformat()
        if ds in daily:
            prev_val = daily[ds]
        if d.weekday() < 5:  # Mon–Fri only
            result.append(prev_val)
        d += dt.timedelta(days=1)
    return result


def compute_sharpe(values: list) -> float:
    v = np.array(values)
    if len(v) < 2:
        return 0.0
    returns = np.diff(v) / (v[:-1] + 1e-8)
    # Daily returns → annualise with sqrt(252)
    return float(np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252))


def compute_max_drawdown(values):
    values = np.array(values)
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd


def run_check():
    trades = load_trades()
    if not trades:
        logger.warning("No trades found. Run paper trading first.")
        return False

    timestamps = [t[0] for t in trades]
    start = datetime.fromisoformat(timestamps[0])
    end = datetime.fromisoformat(timestamps[-1])
    days_trading = (end - start).days

    # ADR-081 3.1: only real exits count. SELL_RECONCILE records a broker read, and
    # SELL_TRIM is a partial exit, so neither is a trade outcome.
    sell_trades = [t for t in trades
                   if t[1].startswith("SELL") and t[1] not in ("SELL_RECONCILE", "SELL_TRIM")]
    wins = sum(1 for t in sell_trades if t[2] > 0)
    win_rate = wins / len(sell_trades) if sell_trades else 0.0
    wr_low, wr_high = wilson_interval(wins, len(sell_trades))

    # Use daily snapshots for Sharpe/drawdown/streaks — trade-row values inflate Sharpe
    # by excluding quiet (no-trade) days from the denominator.
    daily_values = _daily_close_values(trades)
    sharpe = compute_sharpe(daily_values)
    max_dd = compute_max_drawdown(daily_values)

    daily_arr = np.array(daily_values)
    if len(daily_arr) >= 2:
        daily_returns = (np.diff(daily_arr) / (daily_arr[:-1] + 1e-8)).tolist()
    else:
        daily_returns = []
    max_consec_loss = _max_consecutive_losses(daily_returns)

    # vs S&P 500 over the same period
    bot_return = (daily_values[-1] - daily_values[0]) / daily_values[0] if daily_values and daily_values[0] else 0.0
    spy_return = 0.0
    try:
        spy = yf.download("SPY", start=start.date(), end=end.date(), progress=False, auto_adjust=True)
        if len(spy) > 1:
            spy_return = float((spy["Close"].iloc[-1] - spy["Close"].iloc[0]) / spy["Close"].iloc[0])
    except Exception:
        pass

    results = {
        "Days trading":          (days_trading, THRESHOLDS["min_days"], days_trading >= THRESHOLDS["min_days"]),
        # ADR-081 3.2: below the sample floor the result is UNKNOWN and cannot pass readiness.
        "Win rate":              (f"{win_rate:.1%} (n={len(sell_trades)}, 95% CI {wr_low:.0%}-{wr_high:.0%})"
                                  + ("" if len(sell_trades) >= THRESHOLDS["min_win_rate_trades"]
                                     else " UNKNOWN: below sample floor"),
                                  f"{THRESHOLDS['min_win_rate']:.1%}",
                                  len(sell_trades) >= THRESHOLDS["min_win_rate_trades"]
                                  and win_rate >= THRESHOLDS["min_win_rate"]),
        "Sharpe ratio":          (f"{sharpe:.2f}", f"{THRESHOLDS['min_sharpe']:.2f}", sharpe >= THRESHOLDS["min_sharpe"]),
        "Max drawdown":          (f"{max_dd:.1%}", f"{THRESHOLDS['max_drawdown']:.1%}", max_dd <= THRESHOLDS["max_drawdown"]),
        "Max consec losing days":(max_consec_loss, THRESHOLDS["max_consecutive_losing_days"], max_consec_loss <= THRESHOLDS["max_consecutive_losing_days"]),
        "vs S&P 500":            (f"{bot_return:.1%} vs {spy_return:.1%}", "Outperforming", bot_return > spy_return),
    }

    all_pass = True
    logger.info("=== CONFIDENCE CHECK ===")
    for metric, (value, threshold, passed) in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"  {status}  {metric}: {value} (min: {threshold})")
        if not passed:
            all_pass = False

    # "Adapts and learns" -- the second, separate half of the real-money bar
    # (the user's own condition: good performance AND genuine adaptive
    # behavior, not just a date). Pulls real weekly-retrain history from HF;
    # UNKNOWN (missing creds/network/not enough history yet) never fails the
    # overall check -- only a genuinely observed stall or AUC decline does.
    adaptive = check_adaptive_learning(_pull_validation_history())
    if adaptive["status"] == "UNKNOWN":
        logger.info(f"  UNKNOWN  Adaptive learning (retrain health): {adaptive['detail']} — not counted against readiness")
    else:
        passed = adaptive["status"] == "PASS"
        value = (f"AUC {adaptive['auc_recent_avg']:.3f} recent vs {adaptive['auc_earlier_avg']:.3f} earlier, "
                  f"last retrain {adaptive['days_since_last_retrain']}d ago")
        logger.info(f"  {adaptive['status']}  Adaptive learning (retrain health): {value} "
                     f"(min AUC {THRESHOLDS['adaptive_learning_min_auc']}, "
                     f"max decline {THRESHOLDS['adaptive_learning_max_auc_decline']}, "
                     f"max stale {THRESHOLDS['adaptive_learning_max_stale_days']}d)")
        if not passed:
            all_pass = False

    if all_pass:
        logger.info("ALL CHECKS PASSED — Bot is ready for real money.")
        tg.alert_confidence_passed()
    else:
        logger.warning("NOT READY — Keep paper trading.")
    return all_pass


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a win rate. (0, 1) when n is 0 (no information)."""
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _max_consecutive_losses(day_returns):
    max_streak = current = 0
    for r in day_returns:
        if r < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def check_adaptive_learning(history: list, max_auc_decline: float = None,
                             min_auc: float = None, max_stale_days: int = None,
                             min_commits: int = None) -> dict:
    """Pure function: given real weekly-retrain validation_report.json dicts
    (each needs 'xgb_val_auc' and '_commit_at', a tz-aware datetime; oldest
    first), decide whether the model is still being retrained on schedule
    and whether XGB val AUC has been declining -- the "adapts and learns"
    half of the real-money bar, distinct from run_check()'s performance gate.

    Returns status "UNKNOWN" (not "FAIL") when there isn't enough history to
    judge a trend -- an unrelated data-availability gap must never read as a
    real-money-readiness failure."""
    max_auc_decline = THRESHOLDS["adaptive_learning_max_auc_decline"] if max_auc_decline is None else max_auc_decline
    min_auc         = THRESHOLDS["adaptive_learning_min_auc"] if min_auc is None else min_auc
    max_stale_days  = THRESHOLDS["adaptive_learning_max_stale_days"] if max_stale_days is None else max_stale_days
    min_commits     = THRESHOLDS["adaptive_learning_min_commits"] if min_commits is None else min_commits

    if len(history) < min_commits:
        return {"status": "UNKNOWN", "detail": f"only {len(history)} retrain commit(s) found — need {min_commits}+ to assess a trend"}

    ordered = sorted(history, key=lambda r: r["_commit_at"])
    latest_age_days = (datetime.now(timezone.utc) - ordered[-1]["_commit_at"]).days
    stalled = latest_age_days > max_stale_days

    aucs = [float(r.get("xgb_val_auc", 0.0)) for r in ordered]
    half = max(len(aucs) // 2, 1)
    first_half_avg  = sum(aucs[:half]) / half
    second_half_avg = sum(aucs[half:]) / max(len(aucs) - half, 1)
    declining   = (first_half_avg - second_half_avg) > max_auc_decline
    below_floor = aucs[-1] < min_auc

    passed = not stalled and not declining and not below_floor
    return {
        "status": "PASS" if passed else "FAIL",
        "latest_auc": round(aucs[-1], 4),
        "auc_earlier_avg": round(first_half_avg, 4),
        "auc_recent_avg": round(second_half_avg, 4),
        "days_since_last_retrain": latest_age_days,
        "stalled": stalled,
        "declining": declining,
        "below_floor": below_floor,
        "n_commits": len(ordered),
    }


def _pull_validation_history(n_commits: int = 8) -> list:
    """Pull validation_report.json across the last n_commits real auto-retrain
    commits on the HF model repo. Returns [] on any failure (missing creds,
    network, HF outage) -- the caller (check_adaptive_learning) treats an
    empty/short history as UNKNOWN, never as a readiness failure caused by
    something unrelated to the model itself."""
    import json
    from config import HF_TOKEN, HF_REPO_ID
    if not HF_TOKEN or not HF_REPO_ID:
        logger.warning("adaptive_learning: HF_TOKEN/HF_REPO_ID not set — skipping (status will be UNKNOWN).")
        return []
    try:
        from huggingface_hub import HfApi, hf_hub_download
        api = HfApi(token=HF_TOKEN)
        commits = [c for c in api.list_repo_commits(repo_id=HF_REPO_ID) if c.title.startswith("auto-retrain")]
    except Exception as exc:
        logger.warning(f"adaptive_learning: could not reach HF Hub: {exc}")
        return []

    history = []
    for c in commits[:n_commits]:
        try:
            path = hf_hub_download(repo_id=HF_REPO_ID, filename="validation_report.json",
                                    revision=c.commit_id, token=HF_TOKEN)
            r = json.loads(Path(path).read_text())
            r["_commit_at"] = c.created_at
            history.append(r)
        except Exception as exc:
            logger.debug(f"adaptive_learning: skipping commit {c.commit_id[:8]}: {exc}")
    return history


if __name__ == "__main__":
    run_check()
