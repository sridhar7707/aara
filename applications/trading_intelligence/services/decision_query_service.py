"""Decision query service boundary.

Accepts a future decision source abstraction (DecisionSource) via constructor
injection. No concrete source is implemented here -- per
TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md, wiring a real source (a Sentinel
Engine reader) is deferred until ADR-004's backend/read-model strategy is
approved.
"""
from abc import ABC, abstractmethod
from typing import Optional

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.projections.decision_view import DecisionView


class DecisionSource(ABC):
    @abstractmethod
    def get_decision(self, decision_id: str) -> Optional[DecisionContract]:
        ...


class DecisionQueryService:
    def __init__(self, source: DecisionSource):
        self._source = source

    def get_decision_view(self, decision_id: str) -> Optional[DecisionView]:
        contract = self._source.get_decision(decision_id)
        if contract is None:
            return None
        return DecisionView.from_contract(contract)
