from bot.decision_engine.models import EvidenceItem


def test_evidence_item_creation():
    item = EvidenceItem(source="xgb", signal="directional", value=0.62, contribution=0.3)
    assert item.source == "xgb"
    assert item.signal == "directional"
    assert item.value == 0.62
    assert item.contribution == 0.3
