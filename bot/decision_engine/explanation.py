from dataclasses import dataclass
from typing import List, Tuple

from bot.decision_engine.confidence import ConfidenceScore
from bot.decision_engine.decision_context import DecisionContext
from bot.decision_engine.evidence_aggregator import EvidenceSummary

# Fixed, explainable score bands — not tuned parameters — used only to
# choose a qualitative confidence label and to decide when a low-confidence
# warning is warranted.
_LOW_CONFIDENCE_THRESHOLD = 0.34
_MODERATE_CONFIDENCE_THRESHOLD = 0.67


@dataclass(frozen=True)
class DecisionExplanation:
    summary: str
    evidence_reasons: Tuple[str, ...]
    confidence_reason: str
    warnings: Tuple[str, ...]


class ExplanationGenerator:
    def generate(
        self,
        context: DecisionContext,
        evidence_summary: EvidenceSummary,
        confidence_score: ConfidenceScore,
    ) -> DecisionExplanation:
        return DecisionExplanation(
            summary=self._build_summary(context, evidence_summary),
            evidence_reasons=tuple(self._build_evidence_reasons(evidence_summary)),
            confidence_reason=self._build_confidence_reason(confidence_score),
            warnings=tuple(self._build_warnings(evidence_summary, confidence_score)),
        )

    def _confidence_label(self, score: float) -> str:
        if score < _LOW_CONFIDENCE_THRESHOLD:
            return "low"
        if score < _MODERATE_CONFIDENCE_THRESHOLD:
            return "moderate"
        return "high"

    def _build_summary(self, context: DecisionContext, evidence_summary: EvidenceSummary) -> str:
        supporting = evidence_summary.supporting_sources
        conflicting = evidence_summary.conflicting_sources

        if not supporting and not conflicting:
            return f"No evidence is available to support a recommendation for {context.symbol}."

        lines = [f"Recommendation for {context.symbol} supported by:"]
        lines.extend(f"- {source}" for source in supporting)
        if conflicting:
            lines.append("Conflicting signals from:")
            lines.extend(f"- {source}" for source in conflicting)
        return "\n".join(lines)

    def _build_evidence_reasons(self, evidence_summary: EvidenceSummary) -> List[str]:
        reasons = [
            f"{source} signal contribution (supporting)"
            for source in evidence_summary.supporting_sources
        ]
        reasons.extend(
            f"{source} signal contribution (conflicting)"
            for source in evidence_summary.conflicting_sources
        )
        if not reasons:
            reasons.append("No evidence available for this decision.")
        return reasons

    def _build_confidence_reason(self, confidence_score: ConfidenceScore) -> str:
        label = self._confidence_label(confidence_score.score)
        rationale = confidence_score.rationale
        if rationale:
            rationale = rationale[0].lower() + rationale[1:]
        return f"Confidence is {label} because {rationale}"

    def _build_warnings(
        self, evidence_summary: EvidenceSummary, confidence_score: ConfidenceScore
    ) -> List[str]:
        warnings = []
        if evidence_summary.evidence_count == 0:
            warnings.append(
                "No evidence is available; this decision has no supporting basis."
            )
        if confidence_score.conflicting_count > 0:
            warnings.append(
                f"{confidence_score.conflicting_count} conflicting signal(s) detected; "
                "interpret this recommendation with added caution."
            )
        if confidence_score.score < _LOW_CONFIDENCE_THRESHOLD:
            warnings.append("Confidence is low; supporting evidence is limited.")
        return warnings
