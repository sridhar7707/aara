"""Read-only adapter over the legacy bot portfolio equity curve
(`trades.db`'s `portfolio_snapshots` table), backing Morning Brief's
Portfolio Snapshot section with the *freshest* real operational portfolio
value when available.

Boundary decision (recorded, extending the a825ca8/legacy_capital_source.py
precedent to another table in the same file -- explicitly NOT an
ADR-004/Q1 decision): `portfolio_snapshots` is a plain application-state
table the bot's trading loop appends one row to every cycle
(bot/_main_db.py's own DDL: `timestamp TEXT PRIMARY KEY, portfolio_value
REAL, available_cash REAL, open_positions INTEGER`), not one of the
newer, hash-chained "Sentinel Ledger" event tables
(candidate_evaluation_events, decision_events, decision_outcome_events,
risk_evaluation_events, approval_events, deployment_manifest_events,
constitution_enforcement_events, decision_confidence_events -- see
ledger/ledger.py's own _LEDGER_TABLES, none of which is
portfolio_snapshots). Same read-only boundary as legacy_capital_source.py,
legacy_regime_source.py, legacy_candidate_screening_source.py, and
legacy_position_source.py: a new, additive module here may open its own
SQLite connection to trades.db and SELECT from portfolio_snapshots,
provided it never imports bot.*/dashboard.*/database.*/scheduler.*/
ledger.*, never writes, and never touches any ADR-002-protected file. The
tiny read-only SELECT is duplicated here as a literal string rather than
imported from bot/monitor/dashboard_data.py (ADR-002-protected), matching
the established "duplicate the primitive, never import the protected
package" convention.

Why this, not legacy_capital_source.py's `capital_pools`: `capital_pools`
is the bot's internal capital-allocation accounting pool and only moves on
a capital event, so its `updated_at` can lag the live portfolio by weeks
when the bot is idle. `portfolio_snapshots` is written every cycle and is
the same source dashboard/'s overview/executive-summary components already
treat as the current portfolio value (bot/monitor/dashboard_data.py's
`ORDER BY timestamp DESC LIMIT 1`). Portfolio Intelligence still uses
LegacyCapitalSource/`capital_pools` unchanged -- this module does not
touch that adapter or that tab.

`WHERE portfolio_value > 0`: skips the fabricated `portfolio_value = 0`
rows a bad Alpaca reconcile read can leave behind, the same guard
dashboard/'s own portfolio_snapshots queries use.

Health contract (ADR-061 Category A): get_latest_portfolio_snapshot()
returns ReadResult[PortfolioSnapshotValue]. A HEALTHY result carries a
real snapshot OR, when the table exists but holds no usable row, a
HEALTHY result with value=None (a genuine "nothing recorded" state). A
non-HEALTHY result carries value=None plus an IntegrationHealth naming the
reason: UNAVAILABLE (the trades.db file is not present, or is locked),
API_ERROR (the portfolio_snapshots table is missing, or a row could not
be read).

Production note: identical limitation to the other legacy adapters -- the
deployed Trading Intelligence HF Space obtains trades.db only via the
ADR-055 runtime snapshot. Locally, where trades.db already exists from
prior bot runs, this reads real data immediately; without a snapshot it
reports UNAVAILABLE and the caller falls back to the existing unavailable
section -- the intended, safe behavior, not a bug.
"""
import os
import sqlite3
from dataclasses import dataclass

from applications.platform.integrations import IntegrationHealth, ReadResult

_PROVIDER = "trades_db_portfolio_snapshot"

_DB_PATH = "trades.db"

# Duplicated from bot/monitor/dashboard_data.py's own "latest portfolio
# value" SELECT -- not imported, per this module's own docstring. The
# `portfolio_value > 0` guard drops fabricated zero rows; timestamp is an
# ISO-8601 string so lexical DESC order is chronological order. `timestamp`
# is also returned so Morning Brief can show when this row was written.
_SELECT_LATEST_SNAPSHOT = (
    "SELECT portfolio_value, available_cash, timestamp FROM portfolio_snapshots "
    "WHERE portfolio_value > 0 ORDER BY timestamp DESC LIMIT 1"
)


@dataclass(frozen=True)
class PortfolioSnapshotValue:
    """Field names deliberately match the CapitalSummary attributes
    Morning Brief's Portfolio Snapshot formatter already reads
    (total_value / available_cash / invested_amount), so swapping the
    source needs no change to the presentation string. `as_of` is the
    `portfolio_snapshots.timestamp` of the row these figures came from."""

    total_value: float
    available_cash: float
    invested_amount: float
    as_of: str


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A trades.db file that exists but could not be read. "locked" /
    "unable to open" is a transient availability problem (UNAVAILABLE);
    every other sqlite error (a missing table, a corrupt file) is
    API_ERROR. Only the exception's class name is recorded as detail --
    never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyPortfolioSnapshotSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_latest_portfolio_snapshot(self) -> "ReadResult[PortfolioSnapshotValue]":
        """Returns a ReadResult over the most recent positive-value
        portfolio_snapshots row. HEALTHY with a real PortfolioSnapshotValue
        on success (invested_amount is derived as portfolio_value minus
        available_cash); HEALTHY with value=None when the table exists but
        holds no usable row (a genuine "nothing recorded" state);
        UNAVAILABLE when the database file is absent or locked; API_ERROR
        when the portfolio_snapshots table is missing or a row could not
        be read."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_LATEST_SNAPSHOT).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        if row is None or row[0] is None or row[1] is None:
            return ReadResult.empty(_PROVIDER)
        portfolio_value, available_cash = float(row[0]), float(row[1])
        return ReadResult.healthy(
            PortfolioSnapshotValue(
                total_value=portfolio_value,
                available_cash=available_cash,
                invested_amount=portfolio_value - available_cash,
                as_of=str(row[2]) if row[2] is not None else "",
            ),
            _PROVIDER,
        )
