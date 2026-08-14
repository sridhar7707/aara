"""Application boundary for investor-facing read access: gives a future UI
one entry point that hides which query classes exist behind it, mirroring
the role sentinel_engine.services.sentinel_engine.SentinelEngine plays for
the write side.

Pure delegation only: no repository access, no event processing, no
calculations. Depends only on already-constructed query objects
(dependency injection) -- never constructs a repository, a service, or a
query itself.
"""
from typing import Optional

from sentinel_engine.queries.decision_center_query import (
    DecisionCenterQuery,
    DecisionCenterView,
)
from sentinel_engine.queries.decision_query import DecisionQuery, DecisionTimeline
from sentinel_engine.queries.morning_brief_query import MorningBrief, MorningBriefQuery


class InvestorWorkspaceFacade:
    def __init__(
        self,
        morning_brief_query: MorningBriefQuery,
        decision_query: DecisionQuery,
        decision_center_query: DecisionCenterQuery,
    ):
        self._morning_brief_query = morning_brief_query
        self._decision_query = decision_query
        self._decision_center_query = decision_center_query

    def get_morning_brief(self) -> MorningBrief:
        return self._morning_brief_query.get_brief()

    def get_decision_history(self, decision_id: str) -> Optional[DecisionTimeline]:
        return self._decision_query.get_decision_timeline(decision_id)

    def get_decision_center(self, decision_id: str) -> Optional[DecisionCenterView]:
        return self._decision_center_query.get_decision_center(decision_id)
