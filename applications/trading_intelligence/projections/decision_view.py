"""Trading Intelligence's decision read model — no persistence, no database.

Represents the "Trading Intelligence Projection" stage in
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's read flow (Sentinel
Projection -> Reader Contract -> Trading Intelligence Projection -> UI).

Deliberately narrower than DecisionContract: evidence_reference/risk_reference
are internal pointers a decision-list view doesn't display directly (per
AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md, evidence and risk are shown by
separate evidence panels/risk indicators, not embedded in the decision card).
"""
from dataclasses import dataclass
from datetime import datetime

from applications.trading_intelligence.contracts.decision_contract import DecisionContract


@dataclass(frozen=True)
class DecisionView:
    decision_id: str
    symbol: str
    action: str
    status: str
    confidence: float
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: DecisionContract) -> "DecisionView":
        return cls(
            decision_id=contract.decision_id,
            symbol=contract.symbol,
            action=contract.action,
            status=contract.status,
            confidence=contract.confidence,
            updated_at=contract.updated_at,
        )
