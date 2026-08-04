"""Decision query service boundary.

Accepts a future decision source abstraction (DecisionSource) via constructor
injection. No concrete source is implemented here -- per
TRADING_INTELLIGENCE_READ_MODEL_CONTRACTS.md, wiring a real source (a Sentinel
Engine reader) is deferred until ADR-004's backend/read-model strategy is
approved.

list_decisions()/list_decision_views() take an explicit decision_ids list
rather than enumerating "all" decisions -- sentinel_engine.repositories.
ProjectionRepository only exposes get(decision_id)/save(), with no
enumeration method, and this layer must not add one (would require modifying
Sentinel Engine, out of scope here). A caller must already know which
decisions it wants; this is a real, current limitation, not a design
preference.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.projections.decision_view import DecisionView


class DecisionSource(ABC):
    @abstractmethod
    def get_decision(self, decision_id: str) -> Optional[DecisionContract]:
        ...

    @abstractmethod
    def list_decisions(self, decision_ids: List[str]) -> List[DecisionContract]:
        ...


class DecisionQueryService:
    def __init__(self, source: DecisionSource):
        self._source = source

    def get_decision_view(self, decision_id: str) -> Optional[DecisionView]:
        contract = self._source.get_decision(decision_id)
        if contract is None:
            return None
        return DecisionView.from_contract(contract)

    def list_decision_views(self, decision_ids: List[str]) -> List[DecisionView]:
        contracts = self._source.list_decisions(decision_ids)
        return [DecisionView.from_contract(contract) for contract in contracts]
