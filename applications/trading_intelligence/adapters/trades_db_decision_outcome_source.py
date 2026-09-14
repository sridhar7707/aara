"""Decision -> Outcome linkage -- read-only collaborator backing Decision
Center's "Decision Outcome" section.

Translates DecisionOutcomeQueryService's ADR-061 ReadResult-based health
(read via get_lineage()) into the TradingIntelligenceReadError contract
DecisionCenterController's existing per-concern try/except pattern expects
-- mirroring trades_db_news_cache_diff_source.py's own "Error translation"
rule exactly: a genuinely non-HEALTHY read becomes a
TradingIntelligenceReadError; a HEALTHY read is then delegated to
DecisionOutcomeQueryService.get_outcome(decision_id) verbatim, returning
None for a real "no outcome for this id" result (never an error for that
case).

Wave 2A's derive_outcomes() (reached via DecisionOutcomeQueryService /
TradesDbOutcomeReader, both already frozen and already exercised by
Performance & Learning) remains the ONLY outcome-derivation path in this
product -- this adapter adds no second one. It does not modify
DecisionOutcomeQueryService, TradesDbOutcomeReader, derive_outcomes(), or
DecisionOutcome; every field returned is reused verbatim.
"""
from __future__ import annotations

from typing import Optional

from applications.trading_intelligence.contracts.decision_outcome_contract import (
    DecisionOutcome,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.services.decision_outcome_query_service import (
    DecisionOutcomeQueryService,
)


class TradesDbDecisionOutcomeSource:
    def __init__(self, outcome_query_service: DecisionOutcomeQueryService):
        self._outcome_query_service = outcome_query_service

    def get_outcome(self, decision_id: str) -> Optional[DecisionOutcome]:
        """The real DecisionOutcome for `decision_id`, or None when the
        underlying read is HEALTHY but no outcome exists for that id (a
        real "not derivable" result, never an error). Raises
        TradingIntelligenceReadError only for a genuinely non-HEALTHY read
        (e.g. trades.db locked or malformed) -- checked via get_lineage()'s
        own ReadResult.health, since the service's own get_outcome()/
        list_outcomes() convenience methods already degrade a non-HEALTHY
        read to None and would otherwise be indistinguishable here from a
        real "no outcome yet" result."""
        lineage_result = self._outcome_query_service.get_lineage()
        if not lineage_result.health.is_healthy:
            raise TradingIntelligenceReadError(
                f"decision outcome read failed for {decision_id!r}: "
                f"{lineage_result.health.status.name}"
            )
        return self._outcome_query_service.get_outcome(decision_id)
