from dataclasses import dataclass

from bot.decision_engine.evidence_aggregator import EvidenceSummary

# Number of directional evidence items after which volume no longer limits
# confidence — a fixed, explainable saturation point, not a tuned parameter.
_VOLUME_SATURATION = 5


@dataclass(frozen=True)
class ConfidenceScore:
    score: float
    evidence_count: int
    supporting_count: int
    conflicting_count: int
    rationale: str


class ConfidenceCalculator:
    def calculate(self, evidence_summary: EvidenceSummary) -> ConfidenceScore:
        evidence_count = evidence_summary.evidence_count
        supporting_count = len(evidence_summary.supporting_sources)
        conflicting_count = len(evidence_summary.conflicting_sources)

        if evidence_count == 0:
            return ConfidenceScore(
                score=0.0,
                evidence_count=0,
                supporting_count=0,
                conflicting_count=0,
                rationale="No evidence available; confidence defaults to zero.",
            )

        total_directional = supporting_count + conflicting_count

        if total_directional == 0:
            return ConfidenceScore(
                score=0.0,
                evidence_count=evidence_count,
                supporting_count=supporting_count,
                conflicting_count=conflicting_count,
                rationale=(
                    f"{evidence_count} evidence item(s) present but none were "
                    "directional; confidence defaults to zero."
                ),
            )

        # Consistency measures agreement strength only — not direction — so
        # confidence never represents a bullish/bearish prediction, only how
        # one-sided the available evidence is.
        consistency = abs(supporting_count - conflicting_count) / total_directional
        volume_factor = min(1.0, total_directional / _VOLUME_SATURATION)
        score = max(0.0, min(1.0, consistency * volume_factor))

        rationale = (
            f"{supporting_count} supporting vs {conflicting_count} conflicting "
            f"signal(s) across {evidence_count} evidence item(s); "
            f"consistency={consistency:.2f}, volume_factor={volume_factor:.2f}."
        )

        return ConfidenceScore(
            score=score,
            evidence_count=evidence_count,
            supporting_count=supporting_count,
            conflicting_count=conflicting_count,
            rationale=rationale,
        )
