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

Production note: identical limitation to legacy_regime_source.py -- the
deployed Trading Intelligence HF Space has no mechanism today to obtain
trades.db, so `get_risk_state()` consistently returns None there and the
UI renders its existing UNAVAILABLE state. Locally, where trades.db
already exists from prior bot runs, this adapter reads the real value
immediately. None is the safe, expected fallback, never an error.
"""
import sqlite3
from dataclasses import dataclass
from typing import Optional

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


class LegacyRiskStateSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_risk_state(self) -> Optional[LegacyRiskState]:
        """Return the real observed governor classification
        (NORMAL/WARNING/DEFENSIVE) and its `updated_at`, or None if the
        database file, the `risk_state` table, the `risk_governor_state`
        row, a non-empty value, a recognised state literal, or a
        non-empty `updated_at` are missing. Callers must treat None as
        "render the existing UNAVAILABLE state", never as an error."""
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return None
        try:
            row = conn.execute(_SELECT_RISK_GOVERNOR_STATE, (_STATE_KEY,)).fetchone()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        if row is None:
            return None
        value, updated_at = row
        if not value or value not in _VALID_STATES:
            return None
        if not updated_at:
            return None
        return LegacyRiskState(state=value, as_of=updated_at)
