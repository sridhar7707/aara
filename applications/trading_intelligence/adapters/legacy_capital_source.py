"""Read-only adapter over the legacy bot capital pool (`trades.db`'s
`capital_pools` table), backing Portfolio Intelligence's Capital Summary/
Allocation with real data when available.

Boundary decision (recorded, not an ADR-004/Q1 decision -- `capital_pools`
is a plain application-state table owned by bot/capital/pool.py, not one
of the newer, hash-chained "Sentinel Ledger" event tables ADR-004
governs): a new, additive, read-only module inside
applications/trading_intelligence/ may open its own SQLite connection to
the existing `trades.db` and SELECT from `capital_pools`, provided it:
  - never imports bot.*, dashboard.*, database.*, or scheduler.*;
  - never writes to trades.db;
  - never moves, refactors, or otherwise changes any ADR-002-protected
    package or file.
ADR-002 (Accepted) protects those packages/files from "moves, import
changes, refactors, file changes of any kind" -- a passive SELECT from a
brand-new file in an unprotected package is none of those, and ADR-002's
own text states it "does not restrict work inside ... other packages with
zero coupling to the above." This module intentionally does NOT import
bot.capital.pool -- the tiny read-only SELECT it needs is duplicated here
as a literal string instead, the same "duplicate the primitive, never
import the protected package" convention already used elsewhere in this
product (e.g. each screen's own theme.py duplicating shared color tokens
rather than importing them).

Health contract (ADR-061 Category A): get_capital_summary() returns
ReadResult[CapitalSummary]. A HEALTHY result carries a real CapitalSummary
OR, when the table exists but holds no active pool row, a HEALTHY result
with value=None (a genuine "nothing recorded" state). A non-HEALTHY
result carries value=None plus an IntegrationHealth naming the reason:
UNAVAILABLE (the trades.db file is not present, or is locked), API_ERROR
(the capital_pools table is missing, or a row is malformed).

Production note: the deployed Trading Intelligence HF Space has no
mechanism today to obtain trades.db (unlike dashboard/app.py, which pulls
it from a Hugging Face dataset repo via dashboard.data's own HF_REPO_ID
logic -- deliberately not reused here, since dashboard/ is protected).
Locally, where trades.db already exists from prior bot runs, this adapter
reads real data immediately. In production, until a separate sync step is
added, get_capital_summary() consistently reports UNAVAILABLE, and callers
fall back to the existing illustrative screen -- this is the intended,
safe behavior, not a bug.
"""
import os
import sqlite3

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence.ui.portfolio_intelligence.screen import CapitalSummary

_PROVIDER = "trades_db_capital"

_DB_PATH = "trades.db"

# Duplicated from bot/capital/pool.py's own _SELECT_POOL -- not imported,
# per this module's own docstring.
_SELECT_ACTIVE_POOL = (
    "SELECT allocated_amount, available_cash, invested_amount, reserve, "
    "realized_profit FROM capital_pools WHERE status = 'active' "
    "ORDER BY id ASC LIMIT 1"
)


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A trades.db file that exists but could not be read. "locked" /
    "unable to open" is a transient availability problem (UNAVAILABLE);
    every other sqlite error (a missing table, a corrupt file) is
    API_ERROR. The exception's class name is the only detail recorded --
    never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyCapitalSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_capital_summary(self) -> "ReadResult[CapitalSummary]":
        """Returns a ReadResult over the active capital pool row. HEALTHY
        with a real CapitalSummary on success; HEALTHY with value=None when
        the table exists but has no active pool row (a genuine "nothing
        recorded" state); UNAVAILABLE when the database file is absent or
        locked; API_ERROR when the capital_pools table is missing or a row
        is malformed."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_ACTIVE_POOL).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        if row is None:
            return ReadResult.empty(_PROVIDER)
        try:
            allocated_amount, available_cash, invested_amount, reserve, realized_profit = row
            summary = CapitalSummary(
                allocated_amount=allocated_amount,
                available_cash=available_cash,
                invested_amount=invested_amount,
                reserve=reserve,
                realized_profit=realized_profit,
            )
        except (ValueError, TypeError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        return ReadResult.healthy(summary, _PROVIDER)
