"""Domain contract for a governance rule."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    policy_id: str
    name: str
    description: str
    enabled: bool
