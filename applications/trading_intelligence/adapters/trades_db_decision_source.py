"""Read-only data-access adapter over the bot's ``trades`` table, backing
the Decision Center's trades.db-snapshot path.

Boundary decision (recorded, extending the legacy_capital_source.py /
legacy_position_source.py precedent to the ``trades`` table -- NOT an
ADR-004/Q1 decision): ``trades`` is a plain application-state table the
bot's trading loop appends one row to per executed trade (see
bot/_main_db.py's own DDL), not one of the hash-chained "Sentinel Ledger"
event tables. Same read-only boundary as the five ``legacy_*_source.py``
adapters: this additive module may open its own SQLite connection to
trades.db in ``mode=ro`` and SELECT from ``trades``, provided it never
imports bot.*/dashboard.*/scheduler.*/database.*/ledger.*/sentinel_engine.*,
never writes, and never touches any ADR-002-protected file. The SELECT is
duplicated here, not imported from the bot's own writer.

Scope, deliberately narrow (Wave 1):
  * BUY rows only -- ``WHERE action = 'BUY'`` -- so every SELL / SELL_STOP /
    SELL_TIME_EXIT / SELL_RECONCILE row is excluded. SELL-side decision
    intelligence is out of scope.
  * Newest first, capped -- ``ORDER BY id DESC LIMIT 50``.
  * No derivation. The raw ``feature_drivers`` JSON string and
    ``ai_reasoning`` text pass through untouched; model scores are copied
    verbatim or left ``None``. Mapping to the read model is
    adapters/trade_decision_derivation.py's job.

Health contract (ADR-061 Category A): every method returns a
``ReadResult``. A HEALTHY result carries the value (an empty tuple/list is
a legitimate HEALTHY result -- "connected, no BUY history"). A non-HEALTHY
result carries ``value=None`` plus an ``IntegrationHealth`` naming the
reason: UNAVAILABLE (the trades.db file is absent or locked), API_ERROR
(the ``trades`` table is missing, or a row is malformed). An unknown or
ill-formed decision id is NOT an error -- ``get_row`` returns HEALTHY with
``value=None``.

Production note: identical limitation to the ``legacy_*_source.py``
adapters -- the deployed Trading Intelligence HF Space obtains trades.db
only via the ADR-055 runtime snapshot; with no snapshot (local dev without
a local trades.db, CI) every method reports UNAVAILABLE and the Decision
Center falls back to its existing "No decisions recorded yet." empty state.
"""
import os
import sqlite3
from typing import List, Optional, Sequence, Tuple

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence.projections.trade_decision_row import (
    TradeDecisionRow,
    decision_id_for,
    trade_id_from_decision_id,
)

_PROVIDER = "trades_db_decisions"

_DB_PATH = "trades.db"

_BUY_LIST_LIMIT = 50

# Column order this module parses positionally in _parse_row(). Duplicated
# from bot/_main_db.py's ``trades`` DDL -- not imported, per this module's
# own docstring.
_COLUMNS = (
    "id", "timestamp", "symbol", "action", "ensemble_score", "xgb_prob",
    "lstm_prob", "sentiment_score", "macro_score", "regime", "stop_loss",
    "take_profit", "risk_reward_ratio", "feature_drivers", "ai_reasoning",
)
_COLUMN_SQL = ", ".join(_COLUMNS)

_SELECT_BUY_IDS = (
    "SELECT id FROM trades WHERE action = 'BUY' ORDER BY id DESC "
    f"LIMIT {_BUY_LIST_LIMIT}"
)
_SELECT_BY_ID = (
    f"SELECT {_COLUMN_SQL} FROM trades WHERE id = ? AND action = 'BUY'"
)


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A trades.db file that exists but could not be read. "locked" /
    "unable to open" / "disk i/o" is a transient availability problem
    (UNAVAILABLE); every other sqlite error -- notably "no such table" --
    is API_ERROR. Only the exception's class name is recorded as detail,
    never its message (ADR-061 Section 2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _to_str(value) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_row(raw: Sequence) -> TradeDecisionRow:
    """Positional parse of one ``_COLUMNS`` tuple. Raises ``ValueError`` /
    ``TypeError`` on a malformed row (non-numeric text in a score column);
    callers map that to API_ERROR."""
    (
        trade_id, timestamp, symbol, action, ensemble_score, xgb_prob,
        lstm_prob, sentiment_score, macro_score, regime, stop_loss,
        take_profit, risk_reward_ratio, feature_drivers, ai_reasoning,
    ) = raw
    return TradeDecisionRow(
        trade_id=int(trade_id),
        timestamp=str(timestamp),
        symbol=str(symbol),
        action=str(action),
        ensemble_score=_to_float(ensemble_score),
        xgb_prob=_to_float(xgb_prob),
        lstm_prob=_to_float(lstm_prob),
        sentiment_score=_to_float(sentiment_score),
        macro_score=_to_float(macro_score),
        regime=_to_str(regime),
        stop_loss=_to_float(stop_loss),
        take_profit=_to_float(take_profit),
        risk_reward_ratio=_to_float(risk_reward_ratio),
        feature_drivers_raw=_to_str(feature_drivers),
        ai_reasoning=_to_str(ai_reasoning),
    )


class TradesDbDecisionReader:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    def _open_ro(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def list_decision_ids(self) -> "ReadResult[Tuple[str, ...]]":
        """Every BUY decision id, newest ``trades.id`` first, capped at
        ``_BUY_LIST_LIMIT``. HEALTHY with a (possibly empty) tuple on
        success; UNAVAILABLE when the file is absent/locked; API_ERROR when
        the ``trades`` table is missing."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = self._open_ro()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            rows = conn.execute(_SELECT_BUY_IDS).fetchall()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        try:
            ids = tuple(decision_id_for(int(row[0])) for row in rows)
        except (ValueError, TypeError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        return ReadResult.healthy(ids, _PROVIDER)

    def get_row(self, decision_id: str) -> "ReadResult[Optional[TradeDecisionRow]]":
        """One BUY row by decision id. An unknown or ill-formed id is a
        HEALTHY, empty read (``value=None``), never an error. UNAVAILABLE
        when the file is absent/locked; API_ERROR when the ``trades`` table
        is missing or the row is malformed."""
        trade_id = trade_id_from_decision_id(decision_id)
        if trade_id is None:
            return ReadResult.healthy(None, _PROVIDER)
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = self._open_ro()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            raw = conn.execute(_SELECT_BY_ID, (trade_id,)).fetchone()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()
        if raw is None:
            return ReadResult.healthy(None, _PROVIDER)
        try:
            return ReadResult.healthy(_parse_row(raw), _PROVIDER)
        except (ValueError, TypeError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )

    def list_rows(
        self, decision_ids: Sequence[str]
    ) -> "ReadResult[List[TradeDecisionRow]]":
        """The BUY rows for ``decision_ids``, in the given order, silently
        skipping ids that are ill-formed or not present. HEALTHY with a
        (possibly empty) list on success; UNAVAILABLE when the file is
        absent/locked; API_ERROR when the ``trades`` table is missing or a
        row is malformed."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(_PROVIDER, detail="trades.db is not present")
            )
        try:
            conn = self._open_ro()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        rows: List[TradeDecisionRow] = []
        try:
            for decision_id in decision_ids:
                trade_id = trade_id_from_decision_id(decision_id)
                if trade_id is None:
                    continue
                raw = conn.execute(_SELECT_BY_ID, (trade_id,)).fetchone()
                if raw is not None:
                    rows.append(_parse_row(raw))
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        except (ValueError, TypeError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )
        finally:
            conn.close()
        return ReadResult.healthy(rows, _PROVIDER)
