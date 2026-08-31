"""Read-only adapter over the legacy bot signal log (`trades.db`'s
`signal_log` table), backing Morning Brief's Market Mood/Regime section
with real data when available.

Boundary decision (recorded, extending the a825ca8/legacy_capital_source.py
precedent to a second table in the same file -- not an ADR-004/Q1
decision): `signal_log` is a plain application-state table written by
bot/main.py's own trading loop every cycle, not one of the newer,
hash-chained "Sentinel Ledger" event tables (candidate_evaluation_events,
decision_events, decision_outcome_events, risk_evaluation_events,
approval_events, deployment_manifest_events, constitution_enforcement_events,
decision_confidence_events -- see ledger/ledger.py's own _LEDGER_TABLES,
none of which is signal_log). A new, additive, read-only module inside
applications/trading_intelligence/ may open its own SQLite connection to
the existing `trades.db` and SELECT from `signal_log`, provided it:
  - never imports bot.*, dashboard.*, database.*, or scheduler.*;
  - never writes to trades.db;
  - never moves, refactors, or otherwise changes any ADR-002-protected
    package or file.
Same ADR-002 reasoning as legacy_capital_source.py's own docstring: a
passive SELECT from a brand-new file in an unprotected package is not a
"move, import change, refactor, or file change" to any protected package,
and ADR-002's own text states it "does not restrict work inside ... other
packages with zero coupling to the above." This module intentionally does
NOT import bot.main or bot._main_db -- the tiny read-only SELECT it needs
is duplicated here as a literal string instead, the same convention
legacy_capital_source.py already established.

Health contract (ADR-061 Category A): get_latest_regime() returns
ReadResult[str]. A HEALTHY result carries a real regime label OR, when
the table exists but has no usable regime, a HEALTHY result with
value=None (a genuine "nothing recorded" state). A non-HEALTHY result
carries value=None plus an IntegrationHealth naming the reason:
UNAVAILABLE (the trades.db file is not present, or is locked), API_ERROR
(the signal_log table is missing, or a row could not be read).

Production note: identical limitation to legacy_capital_source.py -- the
deployed Trading Intelligence HF Space has no mechanism today to obtain
trades.db. Locally, where trades.db already exists from prior bot runs,
this adapter reads real data immediately. In production, until a separate
sync step is added, get_latest_regime() consistently reports UNAVAILABLE,
and callers fall back to the existing unavailable section -- this is the
intended, safe behavior, not a bug.
"""
import os
import sqlite3

from applications.platform.integrations import IntegrationHealth, ReadResult

_PROVIDER = "trades_db_regime"

_DB_PATH = "trades.db"

# Duplicated from bot/_main_db.py's own signal_log schema -- not imported,
# per this module's own docstring.
_SELECT_LATEST_REGIME = "SELECT regime FROM signal_log ORDER BY id DESC LIMIT 1"


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A trades.db file that exists but could not be read. "locked" /
    "unable to open" is a transient availability problem (UNAVAILABLE);
    every other sqlite error is API_ERROR. Only the exception's class name
    is recorded as detail -- never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyRegimeSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_latest_regime(self) -> "ReadResult[str]":
        """Returns a ReadResult over the most recent regime label written
        by the trading loop. HEALTHY with a real label on success; HEALTHY
        with value=None when the table exists but has no usable regime (a
        genuine "nothing recorded" state); UNAVAILABLE when the database
        file is absent or locked; API_ERROR when the signal_log table is
        missing or a row could not be read."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_LATEST_REGIME).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        if row is None or not row[0]:
            return ReadResult.empty(_PROVIDER)
        return ReadResult.healthy(row[0], _PROVIDER)
