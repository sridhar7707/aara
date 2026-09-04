"""Frozen read-side inspection contracts for the Wave 3 Trust Ledger
Candidate -> Decision inspection surface (ADR-064).

Framework-independent, stdlib-only: no bot, dashboard, scheduler,
database, ledger, sentinel_engine, or sentinel import. These types are
what ``adapters/trust_ledger_inspection_source.py`` returns; nothing here
reads a database or computes any derived metric.

Scope: decision-time inspection only (ADR-064 Section 2.8, Section 8).
Records carry candidate-evaluation facts and decision facts exactly as
recorded in the two authorized Trust Ledger tables
(``candidate_evaluation_events``, ``decision_events``), with the ADR-064
column allowlist (Section 2.4) and nested sub-field redaction already
applied by the source. No later-phase / post-decision result of any kind
is modelled, computed, or linked here.

Identity (ADR-064 Section 2.6): ``candidate_event_id`` and ``decision_id``
(the ADR-059 canonical production decision identity) are carried verbatim;
no replacement identity is synthesised and no cross-store identity map is
formed.

JSON fields (ADR-064 Section 2.4 / 2.9): ``screening_results``,
``model_outputs``, ``risk_checks``, ``intent``, and ``market_context`` are
the already-parsed, already-redacted mapping, or ``None`` when the
recorded JSON could not be parsed (render that as "not recorded" -- a
malformed value degrades only that field, never the row or the surface).
The four ``decision_events`` JSON fields are verbatim recorded facts only
and must not be translated into any ``sentinel_engine`` contract,
governance rule, decision logic, or persistent projection.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

# A parsed-or-unavailable JSON payload: the parsed mapping, or ``None``
# meaning "the recorded value could not be parsed" (ADR-064 Section 2.9).
JsonField = Optional[Mapping[str, Any]]


@dataclass(frozen=True)
class CandidateEvaluationRecord:
    """One ``candidate_evaluation_events`` row, ADR-064 column allowlist
    only. ``sequence_number`` is retained for deterministic ordering and
    is never displayed."""

    candidate_event_id: str
    timestamp: str
    asset: str
    screening_version: str
    screening_results: JsonField
    data_available: bool
    required_models_available: bool
    evaluation_requested: bool
    evaluation_completed: bool
    sequence_number: int


@dataclass(frozen=True)
class DecisionInspectionRecord:
    """One ``decision_events`` row, ADR-064 column allowlist only.

    ``candidate_event_id`` is carried verbatim as the sole permitted link
    back to a :class:`CandidateEvaluationRecord` (ADR-064 Section 2.5); the
    source forms no other correlation. ``sequence_number`` is retained for
    deterministic ordering / latest-decision selection and is never
    displayed.

    Redaction already applied by the source (ADR-064 Section 2.4):
    ``model_outputs`` keeps only per-model ``signal`` / ``confidence`` for
    ``xgboost`` / ``lstm`` / ``finbert`` (no model ``metadata``);
    ``risk_checks`` has ``fill_price`` / ``fill_shares`` / ``notional``
    removed; ``intent`` has ``expected_return_basis_points`` removed;
    ``market_context`` has ``macro_score`` removed.
    """

    decision_id: str
    candidate_event_id: str
    timestamp: str
    asset: str
    action: str
    event_type: str
    final_confidence: Optional[float]
    model_outputs: JsonField
    risk_checks: JsonField
    intent: JsonField
    market_context: JsonField
    data_completeness: JsonField
    sequence_number: int


@dataclass(frozen=True)
class LedgerInspection:
    """The full read-side result of one Trust Ledger snapshot inspection.

    ``candidates`` / ``decisions`` are the two authorized tables' rows as
    contract records, ordered by ``sequence_number`` ascending. An empty
    ``candidates`` tuple is the honest "HEALTHY + empty" state (ADR-064
    Section 2.11); it is still returned inside a HEALTHY ``ReadResult``.

    Freshness (ADR-064 Section 2.12): ``snapshot_mtime`` is the local
    snapshot file's mtime; ``data_through`` is ``MAX(timestamp)`` across
    the two authorized tables (``None`` when both are empty). No other
    table is consulted for freshness, and no other timestamp is invented.
    """

    candidates: Tuple[CandidateEvaluationRecord, ...]
    decisions: Tuple[DecisionInspectionRecord, ...]
    snapshot_mtime: Optional[datetime]
    data_through: Optional[str]

    @property
    def is_empty(self) -> bool:
        """True when the snapshot read cleanly but held no candidate
        rows (ADR-064 Section 2.11 "HEALTHY + empty")."""
        return len(self.candidates) == 0
