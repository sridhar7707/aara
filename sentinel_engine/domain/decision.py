"""Domain contract for an investment decision, owned by Sentinel governance/audit.

The six fields below `risk_reference` are additive (Batch 2, per
docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md):
each defaults to None so every existing caller that constructs a Decision
without them keeps working unchanged. `action` and `horizon` are plain
str fields here, matching this module's existing no-validation-in-the-
domain-object convention -- see sentinel_engine.domain.decision_action.DecisionAction
and sentinel_engine.domain.horizon.Horizon for the vocabulary, and
sentinel_engine.adapters.decision_adapter.to_decision() for where those
vocabularies are actually enforced, at the system boundary.

`uncertainty` is a bare float, deliberately mirroring `confidence`'s own
representation -- no bounds enforcement or distributional model is
introduced here; see the P0 contract Section 12/15 for why that stays
deferred.

`action_source` is additive per ADR-069 (B2): it records whether `action`
was authored by the upstream strategy ("STRATEGY"), by Sentinel's B2
recommendation rule ("SENTINEL"), or is unspecified (None -- legacy /
unknown, never rewritten). Plain str here, matching the no-validation-in-
the-domain-object convention; the vocabulary lives in
sentinel_engine.domain.action_source.ActionSource and is enforced at the
adapter boundary.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Decision:
    decision_id: str
    symbol: str
    action: str
    timestamp: datetime
    confidence: float
    evidence_reference: str
    risk_reference: str
    horizon: Optional[str] = None
    desired_allocation: Optional[float] = None
    minimum_viable_allocation: Optional[float] = None
    uncertainty: Optional[float] = None
    thesis: Optional[str] = None
    counterfactual: Optional[str] = None
    action_source: Optional[str] = None
