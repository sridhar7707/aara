"""Read-only adapter over the legacy bot pre-market screener log
(`trades.db`'s `screener_log` table), backing Morning Brief's Candidate
Screening Summary section with real data when available.

Boundary decision (recorded, extending the a825ca8/legacy_capital_source.py
precedent to a fourth table -- explicitly NOT an ADR-004/Q1 decision):
`screener_log` is a plain application-state table written once per
screening session by bot/_main_market.py's own
`_import_screener_picks()` from that day's `data/universe_today.json`
payload, not one of the newer, hash-chained "Sentinel Ledger" event
tables (candidate_evaluation_events, decision_events,
decision_outcome_events, risk_evaluation_events, approval_events,
deployment_manifest_events, constitution_enforcement_events,
decision_confidence_events -- see ledger/ledger.py's own _LEDGER_TABLES
and ledger/schema.sql, both confirmed to have no reference to
screener_log). Candidate screening is *also* separately duplicated into
the Trust Ledger's `candidate_evaluation_events` table -- this module
intentionally does NOT read that table; it is out of scope for this
authorization and remains gated behind ADR-004/Q1.

Same read-only boundary as legacy_capital_source.py, legacy_regime_
source.py, and legacy_position_source.py: a new, additive module here
may open its own SQLite connection to trades.db and SELECT from
screener_log, provided it never imports bot.*/dashboard.*/database.*/
scheduler.*/ledger.*, never writes, and never touches any ADR-002-
protected file.

screened_at is returned verbatim, never compared against "today" or
otherwise reinterpreted -- callers must render the literal persisted
date so stale local data (the screener may not have run recently) is
never presented as a fresh, current-day result.

Production note: identical limitation to the other three legacy
adapters -- the deployed Trading Intelligence HF Space has no mechanism
today to obtain trades.db. Locally, this adapter reads real data
immediately; in production, until a separate sync step is added,
get_latest_screening() will consistently return None, and callers fall
back to the existing unavailable section -- this is the intended, safe
behavior, not a bug.
"""
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

_DB_PATH = "trades.db"

# Duplicated from bot/_main_market.py's own screener_log schema -- not
# imported, per this module's own docstring.
_SELECT_LATEST_SCREENED_AT = "SELECT MAX(screened_at) FROM screener_log"
_SELECT_BATCH_CANDIDATES = (
    "SELECT symbol, rank, composite_score, sector FROM screener_log "
    "WHERE screened_at = ? ORDER BY (rank IS NULL), rank ASC, symbol ASC"
)


@dataclass(frozen=True)
class CandidateScreeningPick:
    symbol: str
    rank: Optional[int]
    composite_score: Optional[float]
    sector: Optional[str]


@dataclass(frozen=True)
class CandidateScreeningSnapshot:
    screened_at: str
    picks: Tuple[CandidateScreeningPick, ...]


class LegacyCandidateScreeningSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_latest_screening(self) -> Optional[CandidateScreeningSnapshot]:
        """Returns the most recent screening batch (every row sharing the
        latest screened_at value, ordered by rank -- nulls last), or None
        if the database file, the screener_log table, or any usable batch
        don't exist -- callers must treat None as "fall back to the
        existing unavailable section," never as an error."""
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return None
        try:
            latest_row = conn.execute(_SELECT_LATEST_SCREENED_AT).fetchone()
            screened_at = latest_row[0] if latest_row else None
            if not screened_at:
                return None
            rows = conn.execute(_SELECT_BATCH_CANDIDATES, (screened_at,)).fetchall()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        if not rows:
            return None
        picks = tuple(
            CandidateScreeningPick(
                symbol=symbol,
                rank=int(rank) if rank is not None else None,
                composite_score=float(composite_score) if composite_score is not None else None,
                sector=sector,
            )
            for symbol, rank, composite_score, sector in rows
        )
        return CandidateScreeningSnapshot(screened_at=screened_at, picks=picks)
