"""Decision Center controller -- the only place in ui/ allowed to call
Trading Intelligence services.

UI components (screen.py, mock_data.py) must never call DecisionQueryService
directly -- this isolates them from service-layer changes, per
docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md Section 6's
data flow (Sentinel -> Projection -> Adapter -> Query Service -> UI) and
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's query/read boundary.

Not connected to production data: whatever DecisionQueryService/DecisionSource
is injected here determines the data source, and no concrete real source is
wired anywhere in this codebase yet.

load_decision_detail() catches TradingIntelligenceReadError (contracts/
read_error.py) independently around each of its three sequential calls --
decision, evidence, governance, approvals -- so a failure in one concern
never prevents the others from being read, and never escapes as a raw
exception into the UI. Each failure is reported as an explicit
ReadStatus.ERROR on the returned DecisionDetailArea rather than being
conflated with "no data" (empty tuple/None). load_decisions()/load_screen()'s
list-loading path is unchanged -- list_decisions() failure semantics are
deliberately out of scope for this slice.
"""
from typing import List, Optional

from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
    ReadStatus,
)


class DecisionCenterController:
    def __init__(
        self,
        query_service: DecisionQueryService,
        evidence_query_service: DecisionEvidenceQueryService,
        governance_query_service: DecisionGovernanceQueryService,
    ):
        self._query_service = query_service
        self._evidence_query_service = evidence_query_service
        self._governance_query_service = governance_query_service

    def load_decisions(self, decision_ids: List[str]) -> DecisionListArea:
        views = self._query_service.list_decision_views(decision_ids)
        return DecisionListArea(decisions=views)

    def load_decision_detail(self, decision_id: str) -> DecisionDetailArea:
        try:
            view = self._query_service.get_decision_view(decision_id)
        except TradingIntelligenceReadError:
            return DecisionDetailArea(decision=None, decision_status=ReadStatus.ERROR)
        if view is None:
            return DecisionDetailArea(decision=None)

        try:
            evidence = tuple(self._evidence_query_service.get_evidence(decision_id))
            evidence_status = ReadStatus.OK
        except TradingIntelligenceReadError:
            evidence = ()
            evidence_status = ReadStatus.ERROR

        try:
            governance = tuple(self._governance_query_service.get_governance(decision_id))
            governance_status = ReadStatus.OK
        except TradingIntelligenceReadError:
            governance = ()
            governance_status = ReadStatus.ERROR

        try:
            approvals = tuple(self._governance_query_service.get_approvals(decision_id))
            approvals_status = ReadStatus.OK
        except TradingIntelligenceReadError:
            approvals = ()
            approvals_status = ReadStatus.ERROR

        return DecisionDetailArea(
            decision=view,
            evidence=evidence, evidence_status=evidence_status,
            governance=governance, governance_status=governance_status,
            approvals=approvals, approvals_status=approvals_status,
        )

    def load_screen(
        self, decision_ids: List[str], selected_id: Optional[str] = None
    ) -> DecisionCenterScreen:
        list_area = self.load_decisions(decision_ids)
        if selected_id is not None:
            detail_area = self.load_decision_detail(selected_id)
        elif list_area.decisions:
            detail_area = self.load_decision_detail(list_area.decisions[0].decision_id)
        else:
            detail_area = DecisionDetailArea(decision=None)
        return DecisionCenterScreen(list_area=list_area, detail_area=detail_area)
