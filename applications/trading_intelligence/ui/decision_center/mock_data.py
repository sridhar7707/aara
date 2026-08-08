"""Mock data provider for Decision Center V1.

No real service wiring, no sentinel_engine/bot/dashboard/database/ledger
import -- hardcoded DecisionView objects only, per
docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md Section 8,
Phase 1 ("Mock UI: hardcoded DecisionView objects, no real service wiring").
Not connected to DecisionQueryService or any Sentinel Engine data.

DecisionState is imported from applications.trading_intelligence.projections.
decision_view (which already depends on it for DecisionView.status), not
from sentinel_engine directly -- this file is forbidden from importing
sentinel_engine by applications/trading_intelligence/ui/tests/
test_ui_structure.py, and importing the enum through decision_view.py
respects that boundary while still using a real, valid lifecycle state
(mock statuses must be real DecisionState members; fictional/demo-only
states are not permitted).
"""
import datetime
from typing import List

from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
)

_MOCK_DECISIONS = [
    DecisionView(
        decision_id="mock-dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.82,
        updated_at=datetime.datetime(2026, 8, 4, 9, 35, 0),
    ),
    DecisionView(
        decision_id="mock-dec-002",
        symbol="MSFT",
        action="HOLD",
        status=DecisionState.GOVERNANCE_EVALUATED,
        confidence=0.54,
        updated_at=datetime.datetime(2026, 8, 4, 9, 40, 0),
    ),
    DecisionView(
        decision_id="mock-dec-003",
        symbol="NVDA",
        action="SELL",
        status=DecisionState.APPROVAL_RECORDED,
        confidence=0.91,
        updated_at=datetime.datetime(2026, 8, 4, 10, 15, 0),
    ),
]


def get_mock_decisions() -> List[DecisionView]:
    return list(_MOCK_DECISIONS)


def build_mock_screen() -> DecisionCenterScreen:
    decisions = get_mock_decisions()
    selected = decisions[0] if decisions else None
    return DecisionCenterScreen(
        list_area=DecisionListArea(decisions=decisions),
        detail_area=DecisionDetailArea(decision=selected),
    )
