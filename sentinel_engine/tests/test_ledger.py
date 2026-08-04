"""Tests for sentinel_engine.ledger.ledger.LedgerStore."""
import datetime

import pytest

from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType


def _make_event(event_id="evt-001"):
    return Event(
        event_id=event_id,
        event_type=EventType.DECISION_CREATED,
        created_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
        payload={"decision_id": "dec-001"},
    )


class _InMemoryLedgerStore(LedgerStore):
    """Minimal conforming implementation used only to exercise the contract."""

    def __init__(self):
        self._events = []

    def append(self, event):
        self._events.append(event)

    def read_all(self):
        return list(self._events)


def test_ledger_store_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        LedgerStore()


def test_conforming_ledger_store_can_append_and_read_events():
    store = _InMemoryLedgerStore()
    event = _make_event()

    store.append(event)

    assert store.read_all() == [event]


def test_ledger_store_preserves_append_order():
    store = _InMemoryLedgerStore()
    first = _make_event("evt-001")
    second = _make_event("evt-002")

    store.append(first)
    store.append(second)

    assert store.read_all() == [first, second]


def test_incomplete_ledger_store_subclass_cannot_be_instantiated():
    class _Incomplete(LedgerStore):
        def append(self, event):
            pass
        # read_all deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
