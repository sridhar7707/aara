"""Read-only adapter over the legacy bot risk-state table (`trades.db`'s
`risk_state` table), backing Risk Intelligence's current-state section with
the real *observed* governor classification when available.

Boundary decision (recorded, extending the legacy_regime_source.py /
legacy_capital_source.py precedent -- not an ADR-004/Q1 decision):
`risk_state` is a plain Group C **operational / mutable** table declared by
bot/_main_db.py (`CREATE TABLE IF NOT EXISTS risk_state (key TEXT PRIMARY
KEY, value TEXT, updated_at TEXT)`), written by bot/db/risk_state.py and
bot/trust_ledger/risk.py's own `_set_last_state`. It is explicitly **not**
one of the newer hash-chained "Sentinel Ledger" event tables
(candidate_evaluation_events, decision_events, decision_outcome_events,
risk_evaluation_events, approval_events, deployment_manifest_events,
constitution_enforcement_events, decision_confidence_events). This module
reads **only** the single row `key = 'risk_governor_state'` from
`risk_state`; it never opens `data/trust_ledger.db` and never reads
`risk_evaluation_events` or any other ledger table.

Same read-only rules as the sibling legacy_*_source.py adapters:
  - never imports bot.*, dashboard.*, database.*, or scheduler.*;
  - never writes to trades.db;
  - never moves, refactors, or otherwise changes any protected package;
  - duplicates the tiny SELECT it needs as a literal string rather than
    importing bot's own writer.

Observed, not enforced: the value persisted under `risk_governor_state`
is written by bot/trust_ledger/risk.py's Phase 1A Observation-Mode
classifier, which has "zero enforcement authority (FR-1.10a)". Callers
must present it as an *observed governor classification*, never as proof
that the system enforced a risk state or blocked execution.

Health contract (ADR-061 Category A): get_risk_state() returns
ReadResult[LegacyRiskState]. A HEALTHY result carries a real
LegacyRiskState OR, when the table exists but has no `risk_governor_state`
row, a HEALTHY result with value=None (a genuine "nothing recorded"
state). A non-HEALTHY result carries value=None plus an IntegrationHealth
naming the reason: UNAVAILABLE (the trades.db file is not present, or is
locked), API_ERROR (the risk_state table is missing, the persisted value
is not one of NORMAL/WARNING/DEFENSIVE, or the row is otherwise
malformed).

Production note: identical limitation to legacy_regime_source.py -- the
deployed Trading Intelligence HF Space has no mechanism today to obtain
trades.db, so get_risk_state() consistently reports UNAVAILABLE there and
the UI renders its existing UNAVAILABLE state. Locally, where trades.db
already exists from prior bot runs, this adapter reads the real value
immediately. A non-HEALTHY result is the safe, expected fallback, never
an error.
"""
import os
import sqlite3
from dataclasses import dataclass

from applications.platform.integrations import IntegrationHealth, ReadResult

_PROVIDER = "trades_db_risk_state"

_DB_PATH = "trades.db"

# The three valid observed governor states -- kept as a plain literal
# tuple here, not imported from bot/trust_ledger/risk.py, per this
# module's own no-coupling docstring.
_VALID_STATES = ("NORMAL", "WARNING", "DEFENSIVE")

# The single key this adapter reads. Duplicated from bot/trust_ledger/
# risk.py's own `_STATE_KEY` -- not imported.
_STATE_KEY = "risk_governor_state"
_SELECT_RISK_GOVERNOR_STATE = "SELECT value, updated_at FROM risk_state WHERE key = ?"


@dataclass(frozen=True)
class LegacyRiskState:
    """The minimum the Risk Intelligence UI needs from `risk_state`: the
    observed governor classification and the moment it was written. No
    trigger reason and no recommended/actual sizing -- those are never
    persisted in `risk_state` (they live only in the hash-chained
    `risk_evaluation_events` ledger table, which this slice does not
    read)."""

    state: str
    as_of: str


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A trades.db file that exists but could not be read. "locked" /
    "unable to open" is a transient availability problem (UNAVAILABLE);
    every other sqlite error is API_ERROR. Only the exception's class name
    is recorded as detail -- never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyRiskStateSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_risk_state(self) -> "ReadResult[LegacyRiskState]":
        """Returns a ReadResult over the real observed governor
        classification (NORMAL/WARNING/DEFENSIVE) and its `updated_at`.
        HEALTHY with a real LegacyRiskState on success; HEALTHY with
        value=None when the table exists but has no `risk_governor_state`
        row (a genuine "nothing recorded" state); UNAVAILABLE when the
        database file is absent or locked; API_ERROR when the risk_state
        table is missing, the persisted value is not a recognised state
        literal, or the row is otherwise malformed."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            row = conn.execute(_SELECT_RISK_GOVERNOR_STATE, (_STATE_KEY,)).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        if row is None:
            return ReadResult.empty(_PROVIDER)
        value, updated_at = row
        if not value or value not in _VALID_STATES:
            return ReadResult.failed(
                IntegrationHealth.api_error(
                    _PROVIDER, detail="persisted risk-governor value is not a recognised state"
                )
            )
        if not updated_at:
            return ReadResult.failed(
                IntegrationHealth.api_error(
                    _PROVIDER, detail="risk-governor row is missing its updated_at timestamp"
                )
            )
        return ReadResult.healthy(LegacyRiskState(state=value, as_of=updated_at), _PROVIDER)
