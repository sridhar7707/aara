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

Production note: identical limitation to legacy_capital_source.py -- the
deployed Trading Intelligence HF Space has no mechanism today to obtain
trades.db. Locally, where trades.db already exists from prior bot runs,
this adapter reads real data immediately. In production, until a separate
sync step is added, get_latest_regime() will consistently return None,
and callers fall back to the existing unavailable section -- this is the
intended, safe behavior, not a bug.
"""
import sqlite3
from typing import Optional

_DB_PATH = "trades.db"

# Duplicated from bot/_main_db.py's own signal_log schema -- not imported,
# per this module's own docstring.
_SELECT_LATEST_REGIME = "SELECT regime FROM signal_log ORDER BY id DESC LIMIT 1"


class LegacyRegimeSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_latest_regime(self) -> Optional[str]:
        """Returns the most recent regime label written by the trading
        loop, or None if the database file, the signal_log table, a row,
        or a non-empty regime value don't exist -- callers must treat
        None as "fall back to the existing unavailable section," never as
        an error."""
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return None
        try:
            row = conn.execute(_SELECT_LATEST_REGIME).fetchone()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        if row is None:
            return None
        regime = row[0]
        if not regime:
            return None
        return regime
