"""Read side of the Sentinel CQRS boundary: assembles an investor-facing
daily summary across all decisions from the write side's own repositories,
without duplicating storage or routing through DecisionService,
EvidenceService, or GovernanceService.

Read-only: never appends events, never saves or advances a projection.

ProjectionRepository exposes no "list all projections" primitive, so the
set of known decision_ids is discovered from the ledger's event payloads
(the only enumerable source) and each one's current projection is then
fetched individually via ProjectionRepository.get() -- mirroring the
per-decision-id lookup pattern already established in
sentinel_engine.queries.decision_query.DecisionQuery.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository

_STATUSES_PAST_GOVERNANCE = (
    DecisionState.GOVERNANCE_EVALUATED,
    DecisionState.APPROVAL_RECORDED,
)


@dataclass(frozen=True)
class RecentDecisionActivity:
    decision_id: str
    status: DecisionState
    last_activity_at: datetime


@dataclass(frozen=True)
class MorningBrief:
    total_decisions: int
    decisions_by_status: Dict[DecisionState, int]
    recent_decisions: List[RecentDecisionActivity]
    pending_governance_count: int
    pending_approval_count: int
    latest_activity_timestamp: Optional[datetime]


class MorningBriefQuery:
    _RECENT_ACTIVITY_LIMIT = 5

    def __init__(
        self,
        ledger_repository: LedgerRepository,
        projection_repository: ProjectionRepository,
    ):
        self._ledger_repository = ledger_repository
        self._projection_repository = projection_repository

    def get_brief(self) -> MorningBrief:
        events = self._ledger_repository.get_events()

        ordered_decision_ids: List[str] = []
        seen_decision_ids = set()
        latest_activity_by_decision: Dict[str, datetime] = {}
        latest_activity_timestamp: Optional[datetime] = None

        for event in events:
            decision_id = event.payload.get("decision_id")
            if decision_id is None:
                continue

            if decision_id not in seen_decision_ids:
                seen_decision_ids.add(decision_id)
                ordered_decision_ids.append(decision_id)

            current_latest = latest_activity_by_decision.get(decision_id)
            if current_latest is None or event.created_at > current_latest:
                latest_activity_by_decision[decision_id] = event.created_at

            if latest_activity_timestamp is None or event.created_at > latest_activity_timestamp:
                latest_activity_timestamp = event.created_at

        total_decisions = 0
        decisions_by_status: Dict[DecisionState, int] = {}
        pending_governance_count = 0
        pending_approval_count = 0
        recent_candidates: List[RecentDecisionActivity] = []

        for decision_id in ordered_decision_ids:
            projection = self._projection_repository.get(decision_id)
            if projection is None:
                continue

            total_decisions += 1
            status = projection.status
            decisions_by_status[status] = decisions_by_status.get(status, 0) + 1

            if status not in _STATUSES_PAST_GOVERNANCE:
                pending_governance_count += 1
            if status != DecisionState.APPROVAL_RECORDED:
                pending_approval_count += 1

            recent_candidates.append(
                RecentDecisionActivity(
                    decision_id=decision_id,
                    status=status,
                    last_activity_at=latest_activity_by_decision[decision_id],
                )
            )

        recent_decisions = sorted(
            recent_candidates, key=lambda item: item.last_activity_at, reverse=True,
        )[: self._RECENT_ACTIVITY_LIMIT]

        return MorningBrief(
            total_decisions=total_decisions,
            decisions_by_status=decisions_by_status,
            recent_decisions=recent_decisions,
            pending_governance_count=pending_governance_count,
            pending_approval_count=pending_approval_count,
            latest_activity_timestamp=latest_activity_timestamp,
        )
