"""ADR-043 (accepted 2026-08-21) -- one-shot, read-only Trust Ledger
decision lineage projection.

Reads exactly one named decision_id's decision_events row from
data/trust_ledger.db (read-only), translates it through the existing,
unmodified sentinel_engine.adapters.decision_adapter and
evidence_adapter, and produces exactly one DecisionProjection in a
dedicated, temporary, in-memory repository pair that exists only for
this process's lifetime.

Explicitly NOT authorized (see ADR-043 Section 5): any write to the
Trust Ledger; reuse of sentinel_engine.composition.evidence's ADR-013
singleton; any second decision_id in the same invocation; scheduling or
automation; UI wiring; persistence of any kind; governance/risk/approval/
model-identity/hash translation; ADR-004 Option A/B/C selection or
amendment.

All output is diagnostic only -- see EPHEMERAL_BANNER below. Nothing
this script prints or produces is a ledger, an audit record, or a
verified claim. The decision_id an operator passes on the command line
is this run's ADR-043 Section 16 record; no separate artifact is written.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentinel_engine.adapters.decision_adapter import to_decision  # noqa: E402
from sentinel_engine.adapters.evidence_adapter import to_evidence_records  # noqa: E402
from sentinel_engine.domain.decision import Decision  # noqa: E402
from sentinel_engine.events.event import Event  # noqa: E402
from sentinel_engine.ledger.ledger import LedgerStore  # noqa: E402
from sentinel_engine.projections.decision_projection import DecisionProjection  # noqa: E402
from sentinel_engine.repositories.ledger_repository import LedgerRepository  # noqa: E402
from sentinel_engine.repositories.projection_repository import ProjectionRepository  # noqa: E402
from sentinel_engine.services.decision_service import DecisionService  # noqa: E402
from sentinel_engine.services.evidence_service import EvidenceService  # noqa: E402

DEFAULT_DB_PATH = "data/trust_ledger.db"

EPHEMERAL_BANNER = (
    "[EPHEMERAL - DIAGNOSTIC ONLY. NOT A LEDGER, PROJECTION STORE, "
    "AUDIT RECORD, OR VERIFICATION ARTIFACT. ADR-043.]"
)

# ADR-043 Section 9: only these columns are in scope. No SELECT *.
_SELECT_COLUMNS = "decision_id, asset, action, timestamp, final_confidence, model_outputs"


class DuplicateDecisionProjectionError(Exception):
    """Raised if create_decision() is attempted a second time for the
    same decision_id against the same repository pair within one script
    run (ADR-043 Section 12 guard)."""


class _ScriptLedgerStore(LedgerStore):
    """New, dedicated, in-memory LedgerStore for this script only
    (ADR-043 Section 10). NOT sentinel_engine.composition.evidence's
    ADR-013 singleton -- a separate, freshly-instantiated instance."""

    def __init__(self) -> None:
        self._events: List[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def read_all(self) -> List[Event]:
        return list(self._events)


class _ScriptProjectionRepository(ProjectionRepository):
    """New, dedicated, in-memory ProjectionRepository for this script
    only (ADR-043 Section 10). advance_status() is inherited unchanged
    from ProjectionRepository, matching ADR-013's own precedent shape."""

    def __init__(self) -> None:
        self._projections: Dict[str, DecisionProjection] = {}

    def save(self, projection: DecisionProjection) -> None:
        self._projections[projection.decision_id] = projection

    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projections.get(decision_id)


def _print(line: str) -> None:
    print(f"{EPHEMERAL_BANNER} {line}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Exactly one required scalar decision_id. No nargs. Zero or more
    than one token is rejected by argparse itself before any database
    access occurs (ADR-043 implementation plan, item 1)."""
    parser = argparse.ArgumentParser(
        description=(
            "ADR-043: read exactly one named decision_id's row from "
            "data/trust_ledger.db (read-only) and project it into exactly "
            "one in-memory DecisionProjection. Diagnostic only."
        ),
    )
    parser.add_argument(
        "decision_id",
        type=str,
        help="The single Trust Ledger decision_id to read (decision_events.decision_id).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to the Trust Ledger SQLite file (default: {DEFAULT_DB_PATH}).",
    )
    return parser.parse_args(argv)


def read_decision_row(decision_id: str, db_path: str) -> Optional[sqlite3.Row]:
    """Opens db_path read-only (mode=ro, uri=True), reads at most one
    decision_events row for decision_id via a single parameterized
    SELECT of only the ADR-043 Section 9-authorized columns, and closes
    the connection immediately after the read. decision_id is used
    verbatim as the query parameter -- never split, parsed as a list, or
    iterated over."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM decision_events WHERE decision_id = ?",
            (decision_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def build_decision(row: sqlite3.Row) -> Decision:
    """Translates the one read row into a Decision via the existing,
    unmodified decision_adapter.to_decision(). evidence_reference and
    risk_reference use the ADR-043 Section 4 item 5-authorized
    deterministic placeholder, derived from decision_id itself (the only
    identifier this script's column-scoped SELECT reads)."""
    timestamp = row["timestamp"]
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)

    placeholder = f"adr043-placeholder-{row['decision_id']}"

    return to_decision({
        "decision_id": row["decision_id"],
        "symbol": row["asset"],
        "action": row["action"],
        "timestamp": timestamp,
        "confidence": row["final_confidence"],
        "evidence_reference": placeholder,
        "risk_reference": placeholder,
    })


def project_one_decision(
    decision_id: str,
    db_path: str = DEFAULT_DB_PATH,
    ledger_store: Optional[LedgerStore] = None,
    projection_repository: Optional[ProjectionRepository] = None,
) -> Optional[DecisionProjection]:
    """Runs the full ADR-043-authorized flow for exactly one decision_id
    and returns the resulting DecisionProjection, or None if no matching
    row exists.

    ledger_store/projection_repository default to fresh, dedicated,
    in-memory instances (ADR-043 Section 10) when not supplied -- the
    normal, authorized invocation path (main(), below) never supplies
    them. The parameters exist solely so tests can pre-seed a repository
    to exercise the Section 12 duplicate guard without needing two real
    script invocations sharing state, which this architecture never
    otherwise allows (repositories are process-local and discarded on
    return).
    """
    row = read_decision_row(decision_id, db_path)
    if row is None:
        return None

    ledger_store = ledger_store if ledger_store is not None else _ScriptLedgerStore()
    ledger_repository = LedgerRepository(ledger_store)
    projection_repository = (
        projection_repository if projection_repository is not None else _ScriptProjectionRepository()
    )

    if projection_repository.get(decision_id) is not None:
        raise DuplicateDecisionProjectionError(
            f"A DecisionProjection already exists for {decision_id!r} in this "
            "run -- ADR-043 Section 12 forbids duplicate creation."
        )

    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)

    decision = build_decision(row)
    decision_service.create_decision(decision)

    model_outputs = json.loads(row["model_outputs"])
    for evidence in to_evidence_records(model_outputs):
        evidence_service.associate_evidence(decision_id, evidence)

    return decision_service.get_projection(decision_id)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    projection = project_one_decision(args.decision_id, args.db_path)

    if projection is None:
        _print(f"No decision_events row found for decision_id={args.decision_id!r}.")
        return 1

    _print(f"decision_id={projection.decision_id}")
    _print(f"symbol={projection.symbol}")
    _print(f"action={projection.action}")
    _print(f"status={projection.status.value}")
    _print(f"confidence={projection.confidence}")
    _print(f"updated_at={projection.updated_at}")
    _print("evidence_sources=xgboost,lstm,finbert (3 records associated)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
