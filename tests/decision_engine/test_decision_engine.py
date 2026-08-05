import copy
from datetime import datetime, timezone

from bot.decision_engine.decision_engine import DecisionEngine, DecisionResult
from bot.decision_engine.decision_context import DecisionContext
from bot.decision_engine.decision_state import DecisionState
from bot.decision_engine.models import EvidenceItem


def _context(symbol="AAPL"):
    return DecisionContext(
        symbol=symbol,
        timestamp=datetime(2026, 8, 5, tzinfo=timezone.utc),
        strategy_signals={"xgb": 0.7},
        portfolio_context={"cash": 10000.0},
        market_regime="neutral",
        risk_state="normal",
    )


def _item(source, contribution, signal="directional", value=0.5):
    return EvidenceItem(source=source, signal=signal, value=value, contribution=contribution)


def test_complete_evaluation_pipeline_produces_populated_result():
    engine = DecisionEngine()
    context = _context()
    evidence = [_item("xgb", 0.3), _item("sentiment", 0.2)]

    result = engine.evaluate(context, evidence)

    assert isinstance(result, DecisionResult)
    assert result.recommendation == "BUY"
    assert result.confidence_score.supporting_count == 2
    assert result.confidence_score.conflicting_count == 0
    assert result.evidence_summary.evidence_count == 2
    assert result.evidence_summary.supporting_sources == ("xgb", "sentiment")
    assert "xgb" in result.explanation.summary
    assert result.state == DecisionState.RECOMMENDED


def test_empty_evidence_yields_rejected_state_and_no_confidence():
    engine = DecisionEngine()
    context = _context()

    result = engine.evaluate(context, [])

    assert result.evidence_summary.evidence_count == 0
    assert result.confidence_score.score == 0.0
    assert result.recommendation == "HOLD"
    assert result.state == DecisionState.REJECTED


def test_conflicting_evidence_outweighing_support_yields_sell_recommendation():
    engine = DecisionEngine()
    context = _context()
    evidence = [_item("xgb", 0.3), _item("lstm", -0.4), _item("macro", -0.2)]

    result = engine.evaluate(context, evidence)

    assert result.recommendation == "SELL"
    assert result.evidence_summary.supporting_sources == ("xgb",)
    assert result.evidence_summary.conflicting_sources == ("lstm", "macro")
    assert result.state == DecisionState.RECOMMENDED


def test_balanced_conflicting_evidence_yields_hold_recommendation():
    engine = DecisionEngine()
    context = _context()
    evidence = [_item("xgb", 0.3), _item("lstm", -0.3)]

    result = engine.evaluate(context, evidence)

    assert result.recommendation == "HOLD"
    assert result.state == DecisionState.RECOMMENDED


def test_deterministic_result_for_same_input():
    engine = DecisionEngine()
    context = _context()
    evidence = [_item("xgb", 0.3), _item("lstm", -0.1)]

    first = engine.evaluate(context, evidence)
    second = engine.evaluate(context, evidence)

    assert first == second


def test_state_never_reaches_execution_states():
    engine = DecisionEngine()
    context = _context()
    cases = [
        [],
        [_item("xgb", 0.3)],
        [_item("xgb", 0.3), _item("lstm", -0.4)],
        [_item("xgb", 0.3), _item("lstm", 0.2), _item("sentiment", 0.1)],
    ]
    for evidence in cases:
        result = engine.evaluate(context, evidence)
        assert result.state in (DecisionState.RECOMMENDED, DecisionState.REJECTED)
        assert result.state != DecisionState.EXECUTED
        assert result.state != DecisionState.APPROVED


def test_evaluate_does_not_mutate_context_or_evidence_list():
    engine = DecisionEngine()
    context = _context()
    context_snapshot = copy.deepcopy(context)
    evidence = [_item("xgb", 0.3), _item("lstm", -0.2)]
    evidence_snapshot = copy.deepcopy(evidence)

    engine.evaluate(context, evidence)

    assert context == context_snapshot
    assert evidence == evidence_snapshot
