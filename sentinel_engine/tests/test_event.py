"""Tests for sentinel_engine.events.event.Event."""
import datetime
import dataclasses

import pytest

from sentinel_engine.events.event import Event


def _make_event(**overrides):
    defaults = dict(
        event_id="evt-001",
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
        payload={"decision_id": "dec-001"},
    )
    defaults.update(overrides)
    return Event(**defaults)


def test_event_can_be_created_with_required_fields():
    event = _make_event()
    assert event.event_id == "evt-001"
    assert event.event_type == "DECISION_CREATED"
    assert event.created_at == datetime.datetime(2026, 8, 4, 12, 0, 0)
    assert event.payload == {"decision_id": "dec-001"}


def test_event_is_a_dataclass():
    assert dataclasses.is_dataclass(Event)


def test_event_is_immutable():
    event = _make_event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.event_type = "OTHER"


def test_event_requires_all_fields():
    with pytest.raises(TypeError):
        Event(event_id="evt-001", event_type="DECISION_CREATED")
