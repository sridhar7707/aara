"""Immutable base event model for the Sentinel event system."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    created_at: datetime
    payload: Dict[str, Any]
