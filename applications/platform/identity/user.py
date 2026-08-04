"""The current-user abstraction.

Framework-independent: no auth provider, database, or session mechanism
implied by this shape. See docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md
Section 1.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    user_id: str
    display_name: str
