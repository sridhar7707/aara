"""Tests for sentinel_engine.repositories.ledger_repository.LedgerRepository."""
import datetime

from sentinel_engine.repositories.ledger_repository import LedgerRepository
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
    """Minimal conforming LedgerStore used only to exercise the repository."""

    def __init__(self):
        self._events = []

    def append(self, event):
        self._events.append(event)

    def read_all(self):
        return list(self._events)


def test_get_events_returns_empty_list_when_nothing_saved():
    repository = LedgerRepository(_InMemoryLedgerStore())

    assert repository.get_events() == []


def test_save_event_then_get_events_returns_saved_event():
    repository = LedgerRepository(_InMemoryLedgerStore())
    event = _make_event()

    repository.save_event(event)

    assert repository.get_events() == [event]


def test_save_event_preserves_order_across_multiple_saves():
    repository = LedgerRepository(_InMemoryLedgerStore())
    first = _make_event("evt-001")
    second = _make_event("evt-002")

    repository.save_event(first)
    repository.save_event(second)

    assert repository.get_events() == [first, second]


def test_repository_delegates_to_the_injected_store_not_a_shared_default():
    store_a = _InMemoryLedgerStore()
    store_b = _InMemoryLedgerStore()
    repository_a = LedgerRepository(store_a)
    repository_b = LedgerRepository(store_b)

    repository_a.save_event(_make_event())

    assert repository_a.get_events() == [_make_event()]
    assert repository_b.get_events() == []
