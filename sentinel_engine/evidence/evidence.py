"""Domain contract for evidence supporting an investment decision.

`polarity` is additive (Batch 2, per
docs/architecture/SENTINEL_ENGINE_PAPER_TRADING_BEHAVIORAL_CONTRACT_P0.md
Section 3): it defaults to None so every existing caller that constructs
Evidence without it keeps working unchanged. It is a plain str field here,
matching this module's existing no-validation-in-the-domain-object
convention -- see sentinel_engine.evidence.evidence_polarity.EvidencePolarity
for the vocabulary.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    evidence_type: str
    source: str
    data: Dict[str, Any]
    collected_at: datetime
    polarity: Optional[str] = None
