"""Trading Intelligence's own decision contract -- the future Trading
Intelligence decision view.

Framework-independent: no bot, dashboard, scheduler, database, or ledger
import. Distinct from sentinel_engine.projections.DecisionProjection -- this
is Trading Intelligence's own contract, not a re-export of Sentinel's, per
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's ownership split
("Trading Intelligence owns: product views"). status is typed against the
shared DecisionState enum (sentinel_engine.domain.decision_state) since that
enum is the canonical vocabulary for "where a decision is in its lifecycle"
across every consumer -- duplicating it here would defeat the point of a
single typed source of truth for lifecycle state.
"""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.domain.decision_state import DecisionState


@dataclass(frozen=True)
class DecisionContract:
    decision_id: str
    symbol: str
    action: str
    status: DecisionState
    confidence: float
    evidence_reference: str
    risk_reference: str
    updated_at: datetime
