from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from bot.decision_engine.evidence import create_evidence_item
from bot.decision_engine.models import EvidenceItem


def test_create_evidence_item_returns_evidence_item():
    item = create_evidence_item(source="xgb", signal="directional", value=0.62, contribution=0.3)
    assert isinstance(item, EvidenceItem)
    assert item.source == "xgb"
    assert item.signal == "directional"
    assert item.value == 0.62
    assert item.contribution == 0.3


def test_create_evidence_item_defaults_timestamp_to_none():
    item = create_evidence_item(source="xgb", signal="directional", value=0.62, contribution=0.3)
    assert item.timestamp is None


def test_create_evidence_item_preserves_explicit_timestamp():
    ts = datetime(2026, 8, 5, tzinfo=timezone.utc)
    item = create_evidence_item(
        source="xgb", signal="directional", value=0.62, contribution=0.3, timestamp=ts
    )
    assert item.timestamp == ts


def test_evidence_item_is_immutable():
    item = create_evidence_item(source="xgb", signal="directional", value=0.62, contribution=0.3)
    with pytest.raises(FrozenInstanceError):
        item.value = 0.9
