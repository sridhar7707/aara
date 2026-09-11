"""Sprint 4 additive slice -- decision_action_source_events writer.

Records the ADR-069 (B2) action-source provenance authored in
EntryDecisionRecorder.__init__ ("SENTINEL" when the three-model unanimity
rule concurs, "STRATEGY" on the B2 fallback) as an immutable sibling
Group-A event: one row per entry decision, referencing the authoritative
decision_events row's decision_id.

Strictly additive / sibling-only, exactly like bot/trust_ledger/constitution.py:
this module writes nothing to decision_events, modifies no existing payload,
and its caller (bot/_main_trust_decisions.record_decision_safe) failure-
isolates it so a write error here never blocks or alters the primary
pipeline. Its own independent hash chain; decision_events hashing and
verification are untouched.

Absence of a row means action-source provenance was not recorded -- exit
decisions have none (B2 provenance is entry-only) and historical decisions
have none. Nothing is fabricated or backfilled: the caller only invokes
this writer when a real value ("SENTINEL" / "STRATEGY") is present.
"""
from __future__ import annotations

import sqlite3

import ledger.ledger as ledger_svc
from bot.trust_ledger.ids import new_action_source_event_id


def write_action_source_event(
    conn: sqlite3.Connection,
    decision_id: str,
    action_source: str,
    recorded_at: str,
) -> dict:
    """Append one decision_action_source_events row for an already-written
    decision_events row. `action_source` must be the live ActionSource
    vocabulary ("SENTINEL" / "STRATEGY"); the DB CHECK constraint rejects
    anything else. Returns the append_ledger_row() result dict, matching
    the other bot/trust_ledger/*.py writers."""
    return ledger_svc.append_ledger_row(conn, "decision_action_source_events", {
        "event_id": new_action_source_event_id(),
        "decision_id": decision_id,
        "action_source": action_source,
        "recorded_at": recorded_at,
    })
