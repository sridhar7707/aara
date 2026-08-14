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

approval_status carries the decision's latest governance verdict
(sentinel_engine.governance.approval_status.ApprovalStatus), independent of
status/DecisionState -- a decision can be status=APPROVAL_RECORDED whether
its verdict was APPROVED or REJECTED; DecisionState answers "where is this
decision in its lifecycle", approval_status answers "what was decided",
mirroring ApprovalStatus's own docstring distinction. Optional, defaulting
to None, since no approval has necessarily been recorded yet -- not every
producer of a DecisionContract has approval data available.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus


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
    approval_status: Optional[ApprovalStatus] = None
