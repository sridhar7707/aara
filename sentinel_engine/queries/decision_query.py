"""Read side of the Sentinel CQRS boundary: assembles investor-facing decision
timelines from the write side's own repositories, without duplicating storage
or routing through DecisionService, EvidenceService, or GovernanceService.

Read-only: never appends events, never saves or advances a projection. Reads
LedgerRepository and ProjectionRepository directly, since those repository
abstractions already are the query-side's supported entry point -- the
service layer is write-side only and is deliberately not called here.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


@dataclass(frozen=True)
class EvidenceSummary:
    evidence_id: str
    evidence_type: str
    source: str
    attached_at: datetime


@dataclass(frozen=True)
class GovernanceEvaluationSummary:
    policy_id: str
    enabled: bool
    evaluated_at: datetime


@dataclass(frozen=True)
class ApprovalSummary:
    approval_id: str
    status: ApprovalStatus
    approved_by: str
    approved_at: datetime


@dataclass(frozen=True)
class DecisionTimeline:
    decision_id: str
    status: DecisionState
    events: List[Event]
    evidence: List[EvidenceSummary]
    governance_evaluations: List[GovernanceEvaluationSummary]
    approvals: List[ApprovalSummary]


class DecisionQuery:
    def __init__(
        self,
        ledger_repository: LedgerRepository,
        projection_repository: ProjectionRepository,
    ):
        self._ledger_repository = ledger_repository
        self._projection_repository = projection_repository

    def get_decision_timeline(self, decision_id: str) -> Optional[DecisionTimeline]:
        projection = self._projection_repository.get(decision_id)
        if projection is None:
            return None

        events = sorted(
            (
                event
                for event in self._ledger_repository.get_events()
                if event.payload.get("decision_id") == decision_id
            ),
            key=lambda event: event.created_at,
        )

        evidence = [
            EvidenceSummary(
                evidence_id=event.payload["evidence_id"],
                evidence_type=event.payload["evidence_type"],
                source=event.payload["source"],
                attached_at=event.created_at,
            )
            for event in events
            if event.event_type == EventType.EVIDENCE_ATTACHED
        ]

        governance_evaluations = [
            GovernanceEvaluationSummary(
                policy_id=event.payload["policy_id"],
                enabled=event.payload["enabled"],
                evaluated_at=event.created_at,
            )
            for event in events
            if event.event_type == EventType.GOVERNANCE_EVALUATED
        ]

        approvals = [
            ApprovalSummary(
                approval_id=event.payload["approval_id"],
                status=event.payload["status"],
                approved_by=event.payload["approved_by"],
                approved_at=event.created_at,
            )
            for event in events
            if event.event_type == EventType.APPROVAL_RECORDED
        ]

        return DecisionTimeline(
            decision_id=decision_id,
            status=projection.status,
            events=events,
            evidence=evidence,
            governance_evaluations=governance_evaluations,
            approvals=approvals,
        )
