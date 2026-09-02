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

Health contract (ADR-061 Category A): get_open_positions() returns
ReadResult[Tuple[OpenPosition, ...]]. A HEALTHY result carries the full
tuple -- an empty tuple ("the table exists but there are currently no
open positions") is a legitimate HEALTHY result. A non-HEALTHY result
carries value=None plus an IntegrationHealth naming the reason:
UNAVAILABLE (the trades.db file is not present, or is locked), API_ERROR
(the position_state table is missing, or a row is malformed).

Production note: identical limitation to legacy_capital_source.py and
legacy_regime_source.py -- the deployed Trading Intelligence HF Space has
no mechanism today to obtain trades.db. Locally, this adapter reads real
data immediately; in production, until a separate sync step is added,
get_open_positions() consistently reports UNAVAILABLE, and callers fall
back to the existing illustrative Holdings screen -- this is the
intended, safe behavior, not a bug.
"""
import logging
import os
import sqlite3
from dataclasses import dataclass

from applications.platform.integrations import IntegrationHealth, ReadResult

# TEMP-DIAG holdings-price: temporary tracing of position_state reads on the
# deployed HF Space. Remove once the Holdings root cause is confirmed.
_diag = logging.getLogger("aara.holdings_price_diag")

_PROVIDER = "trades_db_positions"

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


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A trades.db file that exists but could not be read. "locked" /
    "unable to open" is a transient availability problem (UNAVAILABLE);
    every other sqlite error is API_ERROR. Only the exception's class name
    is recorded as detail -- never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


class LegacyPositionSource:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def get_open_positions(self) -> "ReadResult[tuple]":
        """Returns a ReadResult over every open position (shares > 0.001)
        from position_state as an OpenPosition tuple. HEALTHY with the full
        tuple on success -- an empty tuple ("connected, currently no open
        positions") is a legitimate HEALTHY result. UNAVAILABLE when the
        database file is absent or locked; API_ERROR when the
        position_state table is missing or a row is malformed."""
        _diag.warning("TEMP-DIAG holdings-price: position_state read; db_path=%r exists=%s",
                      self._db_path, os.path.exists(self._db_path))
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            _diag.warning("TEMP-DIAG holdings-price: sqlite connect failed %s: %r",
                          type(exc).__name__, exc)
            return ReadResult.failed(_sqlite_health(exc))
        try:
            rows = conn.execute(_SELECT_OPEN_POSITIONS).fetchall()
        except sqlite3.Error as exc:
            _diag.warning("TEMP-DIAG holdings-price: position_state query failed %s: %r",
                          type(exc).__name__, exc)
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        _diag.warning("TEMP-DIAG holdings-price: position_state rows=%d sample=%r",
                      len(rows), rows[:5])
        try:
            parsed = tuple(
                OpenPosition(
                    symbol=symbol,
                    quantity=float(shares),
                    entry_price=float(entry_price or 0.0),
                )
                for symbol, shares, entry_price in rows
            )
        except (ValueError, TypeError) as exc:
            _diag.warning("TEMP-DIAG holdings-price: row parse failed %s: %r",
                          type(exc).__name__, exc)
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        _diag.warning("TEMP-DIAG holdings-price: parsed %d positions: %r",
                      len(parsed), [p.symbol for p in parsed])
        return ReadResult.healthy(parsed, _PROVIDER)
