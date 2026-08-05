from dataclasses import dataclass
from typing import List

from bot.decision_engine.confidence import ConfidenceCalculator, ConfidenceScore
from bot.decision_engine.decision_context import DecisionContext
from bot.decision_engine.decision_state import DecisionState, transition
from bot.decision_engine.evidence_aggregator import EvidenceSummary, aggregate_evidence
from bot.decision_engine.explanation import DecisionExplanation, ExplanationGenerator
from bot.decision_engine.models import EvidenceItem


@dataclass(frozen=True)
class DecisionResult:
    recommendation: str
    confidence_score: ConfidenceScore
    evidence_summary: EvidenceSummary
    explanation: DecisionExplanation
    state: DecisionState


class DecisionEngine:
    def __init__(self) -> None:
        self._confidence_calculator = ConfidenceCalculator()
        self._explanation_generator = ExplanationGenerator()

    def evaluate(
        self, context: DecisionContext, evidence: List[EvidenceItem]
    ) -> DecisionResult:
        evidence_summary = aggregate_evidence(list(evidence))
        confidence_score = self._confidence_calculator.calculate(evidence_summary)
        explanation = self._explanation_generator.generate(
            context, evidence_summary, confidence_score
        )
        recommendation = self._derive_recommendation(evidence_summary)

        state = transition(DecisionState.OBSERVED, DecisionState.EVALUATING)
        if evidence_summary.evidence_count == 0:
            state = transition(state, DecisionState.REJECTED)
        else:
            state = transition(state, DecisionState.RECOMMENDED)

        return DecisionResult(
            recommendation=recommendation,
            confidence_score=confidence_score,
            evidence_summary=evidence_summary,
            explanation=explanation,
            state=state,
        )

    @staticmethod
    def _derive_recommendation(evidence_summary: EvidenceSummary) -> str:
        supporting = len(evidence_summary.supporting_sources)
        conflicting = len(evidence_summary.conflicting_sources)
        if supporting > conflicting:
            return "BUY"
        if conflicting > supporting:
            return "SELL"
        return "HOLD"
