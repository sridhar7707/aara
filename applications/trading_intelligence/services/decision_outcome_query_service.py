"""Query boundary for the Wave 2A trades-only Decision Outcome read model.

Mirrors ``DecisionQueryService``'s shape: a source abstraction
(:class:`TradeRowSource`) is injected via the constructor; this service
adds the pure pairing derivation
(adapters/trade_outcome_derivation.derive_outcomes) on top of the raw
``trades`` rows the source returns.

Health-aware: :meth:`get_lineage` returns an ADR-061 ``ReadResult`` --
HEALTHY with an :class:`OutcomeLineage` (possibly all-empty), or the
source's own non-HEALTHY health verbatim. The list / get convenience
methods degrade a non-HEALTHY read to an empty result, matching the
Wave 1 list-path "fall back to the empty state" posture.

Wave 2A ends here. No controller, no Gradio view, and no bootstrap
wiring in this wave.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from applications.platform.integrations import ReadResult
from applications.trading_intelligence.adapters.trade_outcome_derivation import (
    derive_outcomes,
)
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    DecisionOutcome,
    ExcludedSell,
    OutcomeLineage,
)
from applications.trading_intelligence.projections.trade_outcome_row import (
    TradeOutcomeRow,
    trade_id_from_decision_id,
)

_PROVIDER = "trades_db_outcomes"


class TradeRowSource(ABC):
    """Raw ``trades`` BUY/SELL rows, health-wrapped. Implemented by
    adapters/trades_db_outcome_source.py."""

    @abstractmethod
    def read_trade_rows(self) -> "ReadResult[List[TradeOutcomeRow]]":
        ...


class DecisionOutcomeQueryService:
    def __init__(self, source: TradeRowSource):
        self._source = source

    def get_lineage(self) -> "ReadResult[OutcomeLineage]":
        result = self._source.read_trade_rows()
        if not result.health.is_healthy:
            return ReadResult.failed(result.health)
        rows = result.value or []
        return ReadResult.healthy(derive_outcomes(rows), _PROVIDER)

    def list_outcomes(self) -> List[DecisionOutcome]:
        lineage = self.get_lineage()
        if not lineage.is_healthy or lineage.value is None:
            return []
        return list(lineage.value.decisions)

    def get_outcome(self, decision_id: str) -> Optional[DecisionOutcome]:
        if trade_id_from_decision_id(decision_id) is None:
            return None
        for outcome in self.list_outcomes():
            if outcome.decision_id == decision_id:
                return outcome
        return None

    def list_excluded_sells(self) -> List[ExcludedSell]:
        lineage = self.get_lineage()
        if not lineage.is_healthy or lineage.value is None:
            return []
        return list(lineage.value.excluded_sells)
