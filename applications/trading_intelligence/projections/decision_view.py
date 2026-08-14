"""Trading Intelligence's decision read model -- no persistence, no database.

Represents the "Trading Intelligence Projection" stage in
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's read flow (Sentinel
Projection -> Reader Contract -> Trading Intelligence Projection -> UI).

Deliberately narrower than DecisionContract: evidence_reference/risk_reference
are internal pointers a decision-list view doesn't display directly (per
AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md, evidence and risk are shown by
separate evidence panels/risk indicators, not embedded in the decision card).

DecisionState is imported (and therefore re-exported) here so that
ui/decision_center/mock_data.py -- which is forbidden from importing
sentinel_engine directly (see applications/trading_intelligence/ui/tests/
test_ui_structure.py) -- can obtain it via this module instead.

approval_status (sentinel_engine.governance.approval_status.ApprovalStatus,
also re-exported here for the same ui/ import-boundary reason) carries the
decision's latest governance verdict, independent of status -- see
DecisionContract's own docstring for why the two are distinct. Optional,
defaulting to None.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus

from applications.trading_intelligence.contracts.decision_contract import DecisionContract


@dataclass(frozen=True)
class DecisionView:
    decision_id: str
    symbol: str
    action: str
    status: DecisionState
    confidence: float
    updated_at: datetime
    approval_status: Optional[ApprovalStatus] = None

    @classmethod
    def from_contract(cls, contract: DecisionContract) -> "DecisionView":
        return cls(
            decision_id=contract.decision_id,
            symbol=contract.symbol,
            action=contract.action,
            status=contract.status,
            confidence=contract.confidence,
            updated_at=contract.updated_at,
            approval_status=contract.approval_status,
        )
