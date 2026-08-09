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
"""
from typing import List, Optional

from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
)


class DecisionCenterController:
    def __init__(
        self,
        query_service: DecisionQueryService,
        evidence_query_service: DecisionEvidenceQueryService,
    ):
        self._query_service = query_service
        self._evidence_query_service = evidence_query_service

    def load_decisions(self, decision_ids: List[str]) -> DecisionListArea:
        views = self._query_service.list_decision_views(decision_ids)
        return DecisionListArea(decisions=views)

    def load_decision_detail(self, decision_id: str) -> DecisionDetailArea:
        view = self._query_service.get_decision_view(decision_id)
        if view is None:
            return DecisionDetailArea(decision=None)
        evidence = tuple(self._evidence_query_service.get_evidence(decision_id))
        return DecisionDetailArea(decision=view, evidence=evidence)

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
