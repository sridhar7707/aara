"""Trading Intelligence's own governance evaluation read model for the
Decision Detail panel.

Mirrors sentinel_engine.queries.decision_query.GovernanceEvaluationSummary's
fields exactly -- there is no internal id field to drop here the way
EvidenceEntry drops evidence_id -- but is kept as its own Trading
Intelligence-owned type so the UI never depends on Sentinel Engine's
query-layer dataclass directly.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GovernanceEntry:
    policy_id: str
    enabled: bool
    evaluated_at: datetime
