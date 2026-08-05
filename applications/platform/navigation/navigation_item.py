"""A single composed navigation entry.

Per docs/platform/AARA_NAVIGATION_MODEL_ARCHITECTURE.md Section 4 -- the
shell's intended output, built from Product + Workspace data. No builder
exists to actually produce one from those sources yet; this is the shape
only.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationItem:
    product_id: str
    workspace_id: str
    label: str
    order: int
    visibility: str
