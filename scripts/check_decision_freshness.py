"""Read-only Trust Ledger freshness check.

Written after the 2026-08-06 to 2026-08-14 incident: candidate_evaluation_events
kept accumulating on schedule every trading day while decision_events silently
stopped for 11 days -- root cause was bot/_main_market.py's stale-5-min-feed
bug (fixed by ADR-026), but nothing surfaced the gap until a manual check.
Every failure along that path was graceful by design (record_decision_safe()
is deliberately best-effort; a stale bar just logs an INFO line) -- existing
monitoring only checks whether the process is alive (watchdog.yml's /run/cron
ping) and whether a workflow step exited non-zero, never whether the pipeline
actually produced the output it's supposed to.

This script checks the opposite: is the Trust Ledger producing what it should,
not just running without crashing. Three checks, each independently useful:

1. Pipeline staleness -- no candidate_evaluation_events row recently enough
   -> trading workflows likely aren't dispatching at all.
2. Decision-write freeze -- candidates evaluated on the latest active day but
   zero decision_events written that same day -> the write path is broken
   while evaluation keeps working (this is exactly what happened).
3. Data-availability degradation -- most of the latest day's candidates show
   data_available=0 -> a market-data feed problem likely to cascade into #2.

Read-only: never repairs, only reports.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3  # noqa: E402

from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH, get_ledger_conn  # noqa: E402

STALENESS_HOURS = 72
DATA_AVAILABILITY_THRESHOLD = 0.5


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def check_pipeline_staleness(
    conn: sqlite3.Connection, now: datetime, max_hours: int = STALENESS_HOURS,
) -> CheckResult:
    """Fails if the newest candidate_evaluation_events row is older than
    max_hours -- the trading workflows likely aren't dispatching at all."""
    latest = conn.execute("SELECT MAX(timestamp) FROM candidate_evaluation_events").fetchone()[0]
    if latest is None:
        return CheckResult("pipeline_staleness", False, "no candidate_evaluation_events rows exist at all")
    age_hours = (now - datetime.fromisoformat(latest)).total_seconds() / 3600
    if age_hours > max_hours:
        return CheckResult(
            "pipeline_staleness", False,
            f"latest candidate_evaluation_events row is {age_hours:.1f}h old "
            f"(threshold {max_hours}h) -- trading workflows may not be dispatching",
        )
    return CheckResult("pipeline_staleness", True, f"latest candidate row {age_hours:.1f}h old")


def check_decision_write_freeze(conn: sqlite3.Connection) -> CheckResult:
    """Fails if the most recent day with candidate activity has zero
    decision_events -- candidates are being screened but nothing is being
    decided/recorded. Reproduces the exact 2026-08-06..08-14 incident shape."""
    latest_date = conn.execute(
        "SELECT MAX(substr(timestamp, 1, 10)) FROM candidate_evaluation_events"
    ).fetchone()[0]
    if latest_date is None:
        return CheckResult("decision_write_freeze", False, "no candidate_evaluation_events rows exist at all")

    decision_count = conn.execute(
        "SELECT COUNT(*) FROM decision_events WHERE substr(timestamp, 1, 10) = ?",
        (latest_date,),
    ).fetchone()[0]
    if decision_count == 0:
        candidate_count = conn.execute(
            "SELECT COUNT(*) FROM candidate_evaluation_events WHERE substr(timestamp, 1, 10) = ?",
            (latest_date,),
        ).fetchone()[0]
        return CheckResult(
            "decision_write_freeze", False,
            f"{candidate_count} candidates evaluated on {latest_date} but zero "
            "decision_events written that day",
        )
    return CheckResult(
        "decision_write_freeze", True,
        f"{decision_count} decision_events written on {latest_date} (latest candidate day)",
    )


def check_data_availability(
    conn: sqlite3.Connection, threshold: float = DATA_AVAILABILITY_THRESHOLD,
) -> CheckResult:
    """Fails if more than `threshold` of the latest day's candidates show
    data_available=0 -- likely a market-data feed problem (root cause of the
    2026-08-06..08-14 freeze was exactly this, at 17/20 and 20/20)."""
    latest_date = conn.execute(
        "SELECT MAX(substr(timestamp, 1, 10)) FROM candidate_evaluation_events"
    ).fetchone()[0]
    if latest_date is None:
        return CheckResult("data_availability", False, "no candidate_evaluation_events rows exist at all")

    total = conn.execute(
        "SELECT COUNT(*) FROM candidate_evaluation_events WHERE substr(timestamp, 1, 10) = ?",
        (latest_date,),
    ).fetchone()[0]
    unavailable = conn.execute(
        "SELECT COUNT(*) FROM candidate_evaluation_events "
        "WHERE substr(timestamp, 1, 10) = ? AND data_available = 0",
        (latest_date,),
    ).fetchone()[0]
    ratio = unavailable / total if total else 0.0
    detail = f"{unavailable}/{total} ({ratio:.0%}) candidates on {latest_date} had data_available=0"
    if ratio > threshold:
        return CheckResult(
            "data_availability", False,
            f"{detail} (threshold {threshold:.0%}) -- market-data feed may be degraded",
        )
    return CheckResult("data_availability", True, detail)


def run_checks(conn: sqlite3.Connection, now: datetime | None = None) -> list[CheckResult]:
    now = now or datetime.now(timezone.utc)
    return [
        check_pipeline_staleness(conn, now),
        check_decision_write_freeze(conn),
        check_data_availability(conn),
    ]


def _send_telegram_alert(message: str) -> None:
    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "parse_mode": "HTML", "text": message},
            timeout=10,
        )
    except Exception as e:
        print(f"Telegram alert failed: {e}")


def main() -> int:
    if "--no-pull" not in sys.argv:
        from bot.monitor.sync_db import pull_ledger_db
        pull_ledger_db(force=True)

    conn = get_ledger_conn(DEFAULT_LEDGER_DB_PATH)
    try:
        results = run_checks(conn)
    finally:
        conn.close()

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name} -- {r.detail}")

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\n{len(failed)}/{len(results)} checks FAILED")
        alert_lines = "\n".join(f"- {r.name}: {r.detail}" for r in failed)
        _send_telegram_alert(f"\U0001F534 <b>Decision-freshness check FAILED</b>\n{alert_lines}")
        return 1

    print(f"\n{len(results)}/{len(results)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
