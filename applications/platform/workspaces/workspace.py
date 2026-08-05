"""Workspace descriptor.

Six fields, deliberately fewer than the seven-field model sketched in
docs/platform/AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md Section 3 --
`route`/`key` is omitted here, per this task's "Do not add: frontend routes"
constraint. That document already flagged route/key as a placeholder pending
a routing decision that hasn't been made; adding it now would be inventing
routing ahead of that decision, not implementing what was asked.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    product_id: str
    display_name: str
    visibility: str
    description: str = ""
    order: int = 0
