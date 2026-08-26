"""Read-only adapter over the legacy bot open-position state (`trades.db`'s
`position_state` table), backing Portfolio Intelligence's Holdings table
with real symbol/quantity/entry-price data when available.

Boundary decision (recorded, extending the a825ca8/legacy_capital_source.py
precedent to a third table -- not an ADR-004/Q1 decision): `position_state`
is a plain application-state table written by the bot's trading loop to
track currently-open positions (kept in sync with live Alpaca state every
cycle -- see bot/_main_db.py's own DDL), not one of the newer, hash-chained
"Sentinel Ledger" event tables (candidate_evaluation_events, decision_events,
decision_outcome_events, risk_evaluation_events, approval_events,
deployment_manifest_events, constitution_enforcement_events,
decision_confidence_events -- see ledger/ledger.py's own _LEDGER_TABLES,
confirmed absent by direct inspection). Same read-only boundary as
legacy_capital_source.py and legacy_regime_source.py: a new, additive
module here may open its own SQLite connection to trades.db and SELECT
from position_state, provided it never imports bot.*/dashboard.*/
database.*/scheduler.*/ledger.*, never writes, and never touches any
ADR-002-protected file.

position_state (not the trades table) is used for open positions,
matching dashboard/data.py's own choice -- a SELL_RECONCILE row in the
trades ledger can't be "undone" by a later event, so summing BUY/SELL
shares over trade history would silently lose or undercount positions
once a single reconcile has ever fired for a symbol.

entry_price is returned here for completeness but must NEVER be displayed
or treated as current price -- see adapters/live_price_source.py for the
separate, network-only, real current-price fetch this must be composed
with (in bootstrap.py) before any market value or weight is computed.

Production note: identical limitation to legacy_capital_source.py and
legacy_regime_source.py -- the deployed Trading Intelligence HF Space has
no mechanism today to obtain trades.db. Locally, this adapter reads real
data immediately; in production, until a separate sync step is added,
get_open_positions() will consistently return None, and callers fall back
to the existing illustrative Holdings screen -- this is the intended,
safe behavior, not a bug.
"""
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

_DB_PATH = "trades.db"

# Duplicated from bot/_main_db.py's own position_state schema -- not
# imported, per this module's own docstring.
_SELECT_OPEN_POSITIONS = (
    "SELECT symbol, shares, entry_price FROM position_state "
    "WHERE shares > 0.001 ORDER BY symbol ASC"
)


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    quantity: float
    entry_price: float


class LegacyPositionSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_open_positions(self) -> Optional[Tuple[OpenPosition, ...]]:
        """Returns every open position (shares > 0.001) from position_state
        as an OpenPosition tuple -- an empty tuple is a legitimate real
        result (the table exists but there are currently no open
        positions). Returns None only when the database file or the
        position_state table itself don't exist -- callers must treat
        None as "fall back to the existing illustrative Holdings path,"
        never as an error."""
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error:
            return None
        try:
            rows = conn.execute(_SELECT_OPEN_POSITIONS).fetchall()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        return tuple(
            OpenPosition(
                symbol=symbol,
                quantity=float(shares),
                entry_price=float(entry_price or 0.0),
            )
            for symbol, shares, entry_price in rows
        )
