from dataclasses import dataclass
from typing import List, Tuple

from bot.decision_engine.models import EvidenceItem


@dataclass(frozen=True)
class EvidenceSummary:
    total_positive_contribution: float
    total_negative_contribution: float
    supporting_sources: Tuple[str, ...]
    conflicting_sources: Tuple[str, ...]
    evidence_count: int


def aggregate_evidence(evidence_items: List[EvidenceItem]) -> EvidenceSummary:
    total_positive = 0.0
    total_negative = 0.0
    supporting = []
    conflicting = []

    for item in evidence_items:
        if item.contribution > 0:
            total_positive += item.contribution
            supporting.append(item.source)
        elif item.contribution < 0:
            total_negative += item.contribution
            conflicting.append(item.source)

    return EvidenceSummary(
        total_positive_contribution=total_positive,
        total_negative_contribution=total_negative,
        supporting_sources=tuple(supporting),
        conflicting_sources=tuple(conflicting),
        evidence_count=len(evidence_items),
    )
