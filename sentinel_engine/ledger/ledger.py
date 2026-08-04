"""Storage abstraction contract for the Sentinel event ledger.

No concrete backend lives here. Adapters (SQLite, in-memory, etc.)
implement this interface in a later migration phase.
"""
from abc import ABC, abstractmethod
from typing import Iterable

from sentinel_engine.events.event import Event


class LedgerStore(ABC):
    @abstractmethod
    def append(self, event: Event) -> None:
        ...

    @abstractmethod
    def read_all(self) -> Iterable[Event]:
        ...
