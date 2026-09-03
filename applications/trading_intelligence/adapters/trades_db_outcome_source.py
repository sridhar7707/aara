"""Read-only data-access adapter over the bot's ``trades`` table for the
Wave 2A trades-only Decision Outcome read model.

Same boundary as the Wave 1 ``trades_db_decision_source.py`` and the five
``legacy_*_source.py`` adapters: this module opens its own ``mode=ro``
SQLite connection to the ADR-055 ``trades.db`` snapshot and issues one
``SELECT`` against the ``trades`` table only. It imports nothing under
bot / dashboard / scheduler / database / ledger / sentinel_engine,
performs no writes, and reads no other table. The ``SELECT`` is
duplicated here, not imported from the bot's own writer.

Scope (Wave 2A):
  * ``trades`` table only -- BUY rows plus every ``SELL*`` row, so the
    downstream pure derivation can pair them. Columns are enumerated
    explicitly; never ``SELECT *``.
  * No derivation. Rows pass through as :class:`TradeOutcomeRow`, columns
    verbatim. Pairing BUYs to SELLs is
    ``adapters/trade_outcome_derivation.py``'s job.

Health contract (ADR-061): :meth:`read_trade_rows` returns a
``ReadResult``. HEALTHY carries the row list -- an empty list is a
legitimate HEALTHY result ("connected, no trade history"). UNAVAILABLE
when the snapshot file is absent or locked; API_ERROR when the
``trades`` table is missing or a row is malformed.

Production note: identical limitation to the Wave 1 adapters -- with no
ADR-055 snapshot (local dev without a local ``trades.db``, CI) this
reports UNAVAILABLE and the outcome layer yields an empty lineage.
"""
import os
import sqlite3
from typing import List, Optional, Sequence

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence.projections.trade_outcome_row import (
    TradeOutcomeRow,
)
from applications.trading_intelligence.services.decision_outcome_query_service import (
    TradeRowSource,
)

_PROVIDER = "trades_db_outcomes"

_DB_PATH = "trades.db"

_COLUMNS = (
    "id", "timestamp", "symbol", "action", "shares", "price", "notional",
    "realized_pnl", "pnl_pct", "holding_days", "order_id", "ensemble_score",
    "regime",
)
_SELECT_TRADES = (
    "SELECT id, timestamp, symbol, action, shares, price, notional, "
    "realized_pnl, pnl_pct, holding_days, order_id, ensemble_score, regime "
    "FROM trades WHERE action = 'BUY' OR action LIKE 'SELL%' "
    "ORDER BY timestamp, id"
)


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A ``trades.db`` that exists but could not be read. "locked" /
    "unable to open" / "disk i/o" is a transient availability problem
    (UNAVAILABLE); every other sqlite error -- notably "no such table" --
    is API_ERROR. Only the exception class name is recorded as detail,
    never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _to_int(value) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _to_str(value) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_row(raw: Sequence) -> TradeOutcomeRow:
    """Positional parse of one ``_COLUMNS`` tuple. Raises ``ValueError`` /
    ``TypeError`` on a malformed row (non-numeric text in a numeric
    column, or a NULL id); callers map that to API_ERROR."""
    (
        trade_id, timestamp, symbol, action, shares, price, notional,
        realized_pnl, pnl_pct, holding_days, order_id, ensemble_score, regime,
    ) = raw
    return TradeOutcomeRow(
        id=int(trade_id),
        timestamp=str(timestamp),
        symbol=str(symbol),
        action=str(action),
        shares=_to_float(shares),
        price=_to_float(price),
        notional=_to_float(notional),
        realized_pnl=_to_float(realized_pnl),
        pnl_pct=_to_float(pnl_pct),
        holding_days=_to_int(holding_days),
        order_id=_to_str(order_id),
        ensemble_score=_to_float(ensemble_score),
        regime=_to_str(regime),
    )


class TradesDbOutcomeReader(TradeRowSource):
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def _open_ro(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def read_trade_rows(self) -> "ReadResult[List[TradeOutcomeRow]]":
        """Every BUY row plus every ``SELL*`` row, oldest first
        (``ORDER BY timestamp, id``). HEALTHY with a (possibly empty) list
        on success; UNAVAILABLE when the file is absent/locked; API_ERROR
        when the ``trades`` table is missing or a row is malformed."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(
                    _PROVIDER, detail="trades snapshot is not present"
                )
            )
        try:
            conn = self._open_ro()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            raw_rows = conn.execute(_SELECT_TRADES).fetchall()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        try:
            rows = [_parse_row(raw) for raw in raw_rows]
        except (ValueError, TypeError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        return ReadResult.healthy(rows, _PROVIDER)
