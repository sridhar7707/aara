"""Repository facade around a LedgerStore backend.

Storage-backend independent: any LedgerStore implementation can be
injected, so swapping the backend never requires changing this class.
"""
from typing import List

from sentinel_engine.events.event import Event
from sentinel_engine.ledger.ledger import LedgerStore


class LedgerRepository:
    def __init__(self, store: LedgerStore):
        self._store = store

    def save_event(self, event: Event) -> None:
        self._store.append(event)

    def get_events(self) -> List[Event]:
        return list(self._store.read_all())
