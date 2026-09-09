"""Read-only DecisionSource implementation backed by a Sentinel Engine
ProjectionRepository.

Per TRADING_INTELLIGENCE_SENTINEL_READ_INTEGRATION_DESIGN.md's recommended
direction (Option A): wraps a ProjectionRepository directly rather than
introducing a new sentinel_engine-side read service. No database, no ledger,
no bot, no dashboard connection -- only sentinel_engine's own storage-agnostic
repository abstraction.

list_decisions() takes an explicit decision_ids list rather than enumerating
"all" projections -- ProjectionRepository only exposes get(decision_id)/save(),
with no enumeration method, and this adapter must not add one to Sentinel
Engine. See DecisionSource's own docstring for the same constraint stated at
the abstraction level.

get_decision() translates ProjectionRepository infrastructure exceptions into
TradingIntelligenceReadError (contracts/read_error.py) -- ProjectionRepository
is an ABC with no documented exception contract, so a future persistent
backend may raise anything. list_decisions() is deliberately left
untranslated in this slice (Decision List/top-table read semantics are a
separate, later design decision); see this module's own tests for the test
that locks that scope boundary in.

decision_query (sentinel_engine.queries.decision_query.DecisionQuery) is an
optional second collaborator, defaulting to None for full backward
compatibility with every existing single-argument construction of this
class. When provided, it is used to look up, per decision and read-only:
(1) the latest recorded approval verdict (the last entry in
DecisionTimeline.approvals) so DecisionContract.approval_status can be
populated -- the same query SentinelGovernanceSource already uses; and
(2) ADR-070 (Sprint 3): the DECISION_CREATED event's own action_source
value (from DecisionTimeline.events), carried verbatim into
DecisionContract.action_source. When absent, both approval_status and
action_source simply stay None, exactly as approval_status did before this
collaborator existed. This
deliberately does not route through DecisionCenterController's own
governance_query_service -- load_decisions()/load_screen()'s list-loading
path must not query governance/approvals via that service (see
controller.py's tests) -- so verdict lookup happens here, at the
DecisionContract source, entirely independent of that constraint.
"""
from typing import List, Optional

from sentinel_engine.events.event_types import EventType
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.projection_repository import ProjectionRepository

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.services.decision_query_service import DecisionSource


class SentinelProjectionDecisionSource(DecisionSource):
    def __init__(
        self,
        projection_repository: ProjectionRepository,
        decision_query: Optional[DecisionQuery] = None,
    ):
        self._projection_repository = projection_repository
        self._decision_query = decision_query

    def get_decision(self, decision_id: str) -> Optional[DecisionContract]:
        try:
            projection = self._projection_repository.get(decision_id)
        except Exception as exc:
            raise TradingIntelligenceReadError(
                f"Failed to read decision {decision_id!r}."
            ) from exc
        if projection is None:
            return None
        return self._to_contract(projection)

    def list_decisions(self, decision_ids: List[str]) -> List[DecisionContract]:
        contracts = []
        for decision_id in decision_ids:
            projection = self._projection_repository.get(decision_id)
            if projection is not None:
                contracts.append(self._to_contract(projection))
        return contracts

    def _to_contract(self, projection: DecisionProjection) -> DecisionContract:
        return DecisionContract(
            decision_id=projection.decision_id,
            symbol=projection.symbol,
            action=projection.action,
            status=projection.status,
            confidence=projection.confidence,
            evidence_reference=projection.evidence_reference,
            risk_reference=projection.risk_reference,
            updated_at=projection.updated_at,
            approval_status=self._latest_approval_status(projection.decision_id),
            action_source=self._action_source(projection.decision_id),
        )

    def _latest_approval_status(self, decision_id: str):
        if self._decision_query is None:
            return None
        timeline = self._decision_query.get_decision_timeline(decision_id)
        if timeline is None or not timeline.approvals:
            return None
        return timeline.approvals[-1].status

    def _action_source(self, decision_id: str) -> Optional[str]:
        """ADR-070 (Sprint 3): the DECISION_CREATED event's own action_source
        value, carried verbatim. Read through the same optional DecisionQuery
        collaborator _latest_approval_status() uses -- a separate
        get_decision_timeline() call, matching SentinelGovernanceSource's
        established "don't share one cached timeline" pattern. Returns None
        when the collaborator is absent (existing backward-compat behavior),
        when no DECISION_CREATED event is present, or when the payload has no
        action_source key (legacy / pre-B2 records). Never derived from
        action, confidence, status, or symbol."""
        if self._decision_query is None:
            return None
        timeline = self._decision_query.get_decision_timeline(decision_id)
        if timeline is None:
            return None
        for event in timeline.events:
            if event.event_type == EventType.DECISION_CREATED:
                return event.payload.get("action_source")
        return None
