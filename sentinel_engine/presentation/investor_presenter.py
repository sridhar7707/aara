"""Presentation boundary for investor-facing UI-friendly view models: sits
between a future UI and InvestorWorkspaceFacade, converting application
read models (MorningBrief, DecisionCenterView) into flat, display-ready
shapes.

Formatting/mapping only: no repository, service, or event access, and no
business decisions -- the one non-trivial choice this layer makes is
picking the most recent governance evaluation/approval out of a list for a
single-row summary, which mirrors what a UI would show as "current status"
and involves no calculation or interpretation of the underlying data.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sentinel_engine.application.investor_workspace import InvestorWorkspaceFacade
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.queries.decision_center_query import DecisionCenterView
from sentinel_engine.queries.morning_brief_query import MorningBrief


@dataclass(frozen=True)
class RecentActivityRow:
    decision_id: str
    status: DecisionState
    last_activity_at: datetime


@dataclass(frozen=True)
class MorningBriefView:
    total_decisions: int
    status_summary: Dict[DecisionState, int]
    recent_activity_rows: List[RecentActivityRow]


@dataclass(frozen=True)
class EvidenceRow:
    evidence_id: str
    evidence_type: str
    source: str
    attached_at: datetime


@dataclass(frozen=True)
class GovernanceSummaryRow:
    policy_id: str
    enabled: bool
    evaluated_at: datetime


@dataclass(frozen=True)
class ApprovalSummaryRow:
    approval_id: str
    status: ApprovalStatus
    approved_by: str
    approved_at: datetime


@dataclass(frozen=True)
class TimelineRow:
    event_type: str
    created_at: datetime


@dataclass(frozen=True)
class DecisionCenterViewModel:
    decision_id: str
    lifecycle_status: DecisionState
    symbol: Optional[str]
    action: Optional[str]
    evidence_rows: List[EvidenceRow]
    governance_summary: Optional[GovernanceSummaryRow]
    approval_summary: Optional[ApprovalSummaryRow]
    timeline_rows: List[TimelineRow]


class InvestorPresenter:
    def __init__(self, workspace_facade: InvestorWorkspaceFacade):
        self._workspace_facade = workspace_facade

    def get_morning_brief_view(self) -> MorningBriefView:
        brief: MorningBrief = self._workspace_facade.get_morning_brief()

        recent_activity_rows = [
            RecentActivityRow(
                decision_id=item.decision_id,
                status=item.status,
                last_activity_at=item.last_activity_at,
            )
            for item in brief.recent_decisions
        ]

        return MorningBriefView(
            total_decisions=brief.total_decisions,
            status_summary=dict(brief.decisions_by_status),
            recent_activity_rows=recent_activity_rows,
        )

    def get_decision_center_view(self, decision_id: str) -> Optional[DecisionCenterViewModel]:
        view: Optional[DecisionCenterView] = self._workspace_facade.get_decision_center(decision_id)
        if view is None:
            return None

        evidence_rows = [
            EvidenceRow(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                source=item.source,
                attached_at=item.attached_at,
            )
            for item in view.evidence
        ]

        governance_summary = None
        if view.governance_evaluations:
            latest_governance = view.governance_evaluations[-1]
            governance_summary = GovernanceSummaryRow(
                policy_id=latest_governance.policy_id,
                enabled=latest_governance.enabled,
                evaluated_at=latest_governance.evaluated_at,
            )

        approval_summary = None
        if view.approvals:
            latest_approval = view.approvals[-1]
            approval_summary = ApprovalSummaryRow(
                approval_id=latest_approval.approval_id,
                status=latest_approval.status,
                approved_by=latest_approval.approved_by,
                approved_at=latest_approval.approved_at,
            )

        timeline_rows = [
            TimelineRow(event_type=event.event_type.value, created_at=event.created_at)
            for event in view.timeline
        ]

        return DecisionCenterViewModel(
            decision_id=view.decision_id,
            lifecycle_status=view.lifecycle_status,
            symbol=view.symbol,
            action=view.action,
            evidence_rows=evidence_rows,
            governance_summary=governance_summary,
            approval_summary=approval_summary,
            timeline_rows=timeline_rows,
        )
