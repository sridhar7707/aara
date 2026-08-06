"""Read side of the Sentinel CQRS boundary: assembles a single decision's
investor-facing "Decision Center" view -- what was decided, what evidence
was attached, whether governance was evaluated, and whether it was
approved -- from the write side's own repositories.

Read-only: never appends events, never saves or advances a projection.

Builds on sentinel_engine.queries.decision_query.DecisionQuery rather than
re-reading LedgerRepository/ProjectionRepository from scratch: that query
already implements the filter-by-decision_id, sort-by-created_at, and
per-event-type summarization logic this view needs, so reusing it avoids a
second, divergence-prone copy of the same read-side logic. DecisionQuery is
itself a query (not a service), so this stays within the read side of the
CQRS boundary.
"""
from dataclasses import dataclass
from typing import List, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.queries.decision_query import (
    ApprovalSummary,
    DecisionQuery,
    EvidenceSummary,
    GovernanceEvaluationSummary,
)
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


@dataclass(frozen=True)
class DecisionCenterView:
    decision_id: str
    lifecycle_status: str
    symbol: Optional[str]
    action: Optional[str]
    evidence: List[EvidenceSummary]
    governance_evaluations: List[GovernanceEvaluationSummary]
    approvals: List[ApprovalSummary]
    timeline: List[Event]


class DecisionCenterQuery:
    def __init__(
        self,
        ledger_repository: LedgerRepository,
        projection_repository: ProjectionRepository,
    ):
        self._decision_query = DecisionQuery(ledger_repository, projection_repository)

    def get_decision_center(self, decision_id: str) -> Optional[DecisionCenterView]:
        timeline = self._decision_query.get_decision_timeline(decision_id)
        if timeline is None:
            return None

        decision_created_event = next(
            (
                event
                for event in timeline.events
                if event.event_type == EventType.DECISION_CREATED
            ),
            None,
        )
        symbol = (
            decision_created_event.payload.get("symbol")
            if decision_created_event is not None
            else None
        )
        action = (
            decision_created_event.payload.get("action")
            if decision_created_event is not None
            else None
        )

        return DecisionCenterView(
            decision_id=timeline.decision_id,
            lifecycle_status=timeline.status,
            symbol=symbol,
            action=action,
            evidence=timeline.evidence,
            governance_evaluations=timeline.governance_evaluations,
            approvals=timeline.approvals,
            timeline=timeline.events,
        )
