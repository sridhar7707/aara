"""Read-only data-access adapter over the two authorized Trust Ledger
tables for the Wave 3 Decision Ledger Inspection surface (ADR-064).

Boundary (ADR-064 Section 2.2 / 2.3 / 2.14): this module opens its own
``mode=ro`` SQLite connection to the product-owned ``trust_ledger.db``
snapshot fetched by ``adapters/trust_ledger_snapshot.py`` and issues two
enumerated ``SELECT`` statements -- one against
``candidate_evaluation_events`` and one against ``decision_events`` -- and
nothing else. It imports nothing under ``bot/``, top-level ``ledger/``,
``scheduler/``, ``dashboard/``, ``database/``, or ``sentinel_engine/``; it
performs no write of any kind; and it reads no other Trust Ledger table.

Column allowlist (ADR-064 Section 2.4): the two ``SELECT`` lists below are
the positive, exhaustive statement of what may be read. No ``SELECT *``.
The columns ADR-064 excludes are never named in a ``SELECT``. The nested
JSON sub-fields ADR-064 excludes are stripped at the parse boundary,
before a contract record is built (see the ``_redact_*`` helpers).

Only permitted relationship (ADR-064 Section 2.5): the source forms no SQL
join and no cross-table correlation. It returns the two tables' rows as
separate ``sequence_number``-ordered tuples;
``decision_events.candidate_event_id`` is carried verbatim so a later
layer can group by the DB-enforced foreign key. No correlation by symbol,
date, timestamp proximity, score, model output, row position, sequence
adjacency, or any other store is possible from what this source returns.

Health (ADR-061 / ADR-064 Section 2.11): :meth:`read_inspection` returns a
``ReadResult[LedgerInspection]``.

* HEALTHY + data  -- both tables present, at least one candidate row.
* HEALTHY + empty -- both tables present, zero candidate rows
  (``LedgerInspection.is_empty``); still a HEALTHY ``ReadResult``.
* UNAVAILABLE     -- snapshot absent / unreadable, an authorized table
  missing, or an authorized column missing.

A malformed individual JSON value degrades only that field to ``None``
("not recorded"); the row and the surface survive (ADR-064 Section 2.9).
This source performs no HTML escaping -- that is a presentation concern
for the later slice.
"""
import json
import os
import sqlite3
from collections.abc import Mapping as _AbcMapping
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence.adapters.trust_ledger_snapshot import (
    _snapshot_path,
)
from applications.trading_intelligence.contracts.candidate_decision_contract import (
    CandidateEvaluationRecord,
    DecisionInspectionRecord,
    JsonField,
    LedgerInspection,
)

_PROVIDER = "trust_ledger_inspection"

_CANDIDATE_TABLE = "candidate_evaluation_events"
_DECISION_TABLE = "decision_events"

# ADR-064 Section 2.4 -- the positive, exhaustive column allowlists.
_CANDIDATE_COLUMNS = (
    "candidate_event_id",
    "timestamp",
    "asset",
    "screening_version",
    "screening_results",
    "data_available",
    "required_models_available",
    "evaluation_requested",
    "evaluation_completed",
    "sequence_number",
)
_DECISION_COLUMNS = (
    "decision_id",
    "candidate_event_id",
    "timestamp",
    "asset",
    "action",
    "event_type",
    "final_confidence",
    "model_outputs",
    "risk_checks",
    "intent",
    "market_context",
    "data_completeness",
    "sequence_number",
)

_SELECT_CANDIDATES = (
    "SELECT " + ", ".join(_CANDIDATE_COLUMNS) + " FROM " + _CANDIDATE_TABLE
    + " ORDER BY sequence_number"
)
_SELECT_DECISIONS = (
    "SELECT " + ", ".join(_DECISION_COLUMNS) + " FROM " + _DECISION_TABLE
    + " ORDER BY sequence_number"
)

_REQUIRED = {
    _CANDIDATE_TABLE: _CANDIDATE_COLUMNS,
    _DECISION_TABLE: _DECISION_COLUMNS,
}

# Nested sub-fields ADR-064 Section 2.4 excludes from the JSON columns.
_MODEL_KEYS = ("xgboost", "lstm", "finbert")
_MODEL_ALLOWED_SUBFIELDS = ("signal", "confidence")
_RISK_CHECKS_EXCLUDED = ("fill_price", "fill_shares", "notional")
_INTENT_EXCLUDED = ("expected_return_basis_points",)
_MARKET_CONTEXT_EXCLUDED = ("macro_score",)


def _sqlite_health(exc: sqlite3.Error) -> IntegrationHealth:
    """A snapshot file that exists but could not be read. "locked" /
    "unable to open" / "disk i/o" is a transient availability problem
    (UNAVAILABLE); any other sqlite error is API_ERROR. Only the exception
    class name is recorded as detail, never its message (ADR-061 Section
    2.9)."""
    message = str(exc).lower()
    if "locked" in message or "unable to open" in message or "disk i/o" in message:
        return IntegrationHealth.unavailable(_PROVIDER, detail=type(exc).__name__)
    return IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)


def _parse_json(raw: Any) -> JsonField:
    """Parse one recorded JSON column value. Returns the parsed mapping, or
    ``None`` when the value is absent, is not valid JSON, or does not parse
    to an object -- "not recorded" (ADR-064 Section 2.9). Never raises."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(parsed, _AbcMapping):
        return None
    return parsed


def _redact_model_outputs(parsed: JsonField) -> JsonField:
    """ADR-064 Section 2.4: surface only per-model ``signal`` / ``confidence``
    for xgboost / lstm / finbert. Model ``metadata`` and any other key are
    dropped."""
    if parsed is None:
        return None
    out = {}
    for key in _MODEL_KEYS:
        value = parsed.get(key)
        if isinstance(value, _AbcMapping):
            out[key] = {
                sub: value[sub]
                for sub in _MODEL_ALLOWED_SUBFIELDS
                if sub in value
            }
    return out


def _redact_drop_keys(parsed: JsonField, excluded: Sequence[str]) -> JsonField:
    """ADR-064 Section 2.4: return the recorded mapping with the named
    excluded sub-fields removed; every other recorded key is kept
    verbatim."""
    if parsed is None:
        return None
    return {k: v for k, v in parsed.items() if k not in excluded}


def _to_bool(value: Any) -> bool:
    return bool(int(value))


def _to_opt_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _parse_candidate_row(raw: Sequence) -> CandidateEvaluationRecord:
    (
        candidate_event_id, timestamp, asset, screening_version,
        screening_results, data_available, required_models_available,
        evaluation_requested, evaluation_completed, sequence_number,
    ) = raw
    if candidate_event_id is None:
        raise ValueError("candidate_evaluation_events row has NULL candidate_event_id")
    return CandidateEvaluationRecord(
        candidate_event_id=str(candidate_event_id),
        timestamp=str(timestamp),
        asset=str(asset),
        screening_version=str(screening_version),
        screening_results=_parse_json(screening_results),
        data_available=_to_bool(data_available),
        required_models_available=_to_bool(required_models_available),
        evaluation_requested=_to_bool(evaluation_requested),
        evaluation_completed=_to_bool(evaluation_completed),
        sequence_number=int(sequence_number),
    )


def _parse_decision_row(raw: Sequence) -> DecisionInspectionRecord:
    (
        decision_id, candidate_event_id, timestamp, asset, action, event_type,
        final_confidence, model_outputs, risk_checks, intent, market_context,
        data_completeness, sequence_number,
    ) = raw
    if decision_id is None or candidate_event_id is None:
        raise ValueError("decision_events row has a NULL identity column")
    return DecisionInspectionRecord(
        decision_id=str(decision_id),
        candidate_event_id=str(candidate_event_id),
        timestamp=str(timestamp),
        asset=str(asset),
        action=str(action),
        event_type=str(event_type),
        final_confidence=_to_opt_float(final_confidence),
        model_outputs=_redact_model_outputs(_parse_json(model_outputs)),
        risk_checks=_redact_drop_keys(_parse_json(risk_checks), _RISK_CHECKS_EXCLUDED),
        intent=_redact_drop_keys(_parse_json(intent), _INTENT_EXCLUDED),
        market_context=_redact_drop_keys(
            _parse_json(market_context), _MARKET_CONTEXT_EXCLUDED
        ),
        data_completeness=_parse_json(data_completeness),
        sequence_number=int(sequence_number),
    )


def _max_timestamp(conn: sqlite3.Connection) -> Optional[str]:
    """``MAX(timestamp)`` across the two authorized tables only (ADR-064
    Section 2.12). ``None`` when both tables are empty."""
    values = []
    for table in (_CANDIDATE_TABLE, _DECISION_TABLE):
        row = conn.execute("SELECT MAX(timestamp) FROM " + table).fetchone()
        if row and row[0] is not None:
            values.append(str(row[0]))
    return max(values) if values else None


def _snapshot_mtime(db_path: str) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(os.path.getmtime(db_path), timezone.utc)
    except OSError:
        return None


class TrustLedgerInspectionReader:
    """Reads the two authorized Trust Ledger tables from the fetched
    snapshot into :class:`LedgerInspection`. ``db_path`` defaults to the
    product-owned snapshot path written by
    ``trust_ledger_snapshot.fetch_trust_ledger_db_snapshot()``."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path if db_path is not None else _snapshot_path()

    def _open_ro(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def _check_schema(self, conn: sqlite3.Connection) -> Optional[IntegrationHealth]:
        """ADR-064 Section 2.9 / Section 10: a missing authorized table or a
        missing authorized column makes the whole surface UNAVAILABLE.
        Returns an ``IntegrationHealth`` to fail with, or ``None`` when the
        schema satisfies both allowlists."""
        for table, columns in _REQUIRED.items():
            present = {
                row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")
            }
            if not present:
                return IntegrationHealth.unavailable(
                    _PROVIDER, detail="required table '" + table + "' is absent"
                )
            missing = [c for c in columns if c not in present]
            if missing:
                return IntegrationHealth.unavailable(
                    _PROVIDER,
                    detail="required column '" + missing[0] + "' is absent from '"
                    + table + "'",
                )
        return None

    def read_inspection(self) -> "ReadResult[LedgerInspection]":
        """Read both authorized tables. HEALTHY with a populated or empty
        :class:`LedgerInspection` on success; UNAVAILABLE when the snapshot
        is absent / unreadable / structurally short of an authorized table
        or column; API_ERROR when a row is structurally malformed in a
        non-JSON column."""
        if not os.path.exists(self._db_path):
            return ReadResult.failed(
                IntegrationHealth.unavailable(
                    _PROVIDER, detail="trust ledger snapshot is not present"
                )
            )
        try:
            conn = self._open_ro()
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        try:
            schema_failure = self._check_schema(conn)
            if schema_failure is not None:
                return ReadResult.failed(schema_failure)
            raw_candidates = conn.execute(_SELECT_CANDIDATES).fetchall()
            raw_decisions = conn.execute(_SELECT_DECISIONS).fetchall()
            data_through = _max_timestamp(conn)
        except sqlite3.Error as exc:
            return ReadResult.failed(_sqlite_health(exc))
        finally:
            conn.close()

        try:
            candidates = tuple(_parse_candidate_row(r) for r in raw_candidates)
            decisions = tuple(_parse_decision_row(r) for r in raw_decisions)
        except (ValueError, TypeError) as exc:
            return ReadResult.failed(
                IntegrationHealth.api_error(_PROVIDER, detail=type(exc).__name__)
            )

        inspection = LedgerInspection(
            candidates=candidates,
            decisions=decisions,
            snapshot_mtime=_snapshot_mtime(self._db_path),
            data_through=data_through,
        )
        return ReadResult.healthy(inspection, _PROVIDER)
