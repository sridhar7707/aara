from bot.decision_engine.decision_state import DecisionState
from bot.decision_engine.models import DecisionResult, EvidenceItem


def test_evidence_item_creation():
    item = EvidenceItem(source="xgb", signal="directional", value=0.62, contribution=0.3)
    assert item.source == "xgb"
    assert item.signal == "directional"
    assert item.value == 0.62
    assert item.contribution == 0.3


def test_decision_result_creation():
    evidence = [EvidenceItem(source="xgb", signal="directional", value=0.62, contribution=0.3)]
    result = DecisionResult(
        recommendation="BUY",
        confidence=0.73,
        evidence=evidence,
        explanation="3 of 3 available signals agree",
        state=DecisionState.RECOMMENDED,
    )
    assert result.recommendation == "BUY"
    assert result.confidence == 0.73
    assert result.evidence == evidence
    assert result.explanation == "3 of 3 available signals agree"
    assert result.state == DecisionState.RECOMMENDED
