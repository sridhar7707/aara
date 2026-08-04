"""Trading Intelligence's own decision contract — the future Trading
Intelligence decision view.

Framework-independent: no bot, dashboard, scheduler, database, or ledger
import. Distinct from sentinel_engine.projections.DecisionProjection — this is
Trading Intelligence's own contract, not a re-export of Sentinel's, per
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's ownership split
("Trading Intelligence owns: product views").
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DecisionContract:
    decision_id: str
    symbol: str
    action: str
    status: str
    confidence: float
    evidence_reference: str
    risk_reference: str
    updated_at: datetime
