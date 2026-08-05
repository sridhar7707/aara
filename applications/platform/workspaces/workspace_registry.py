"""Workspace registration interface.

Analogous to ProductRegistry (Phase 4D) but at workspace granularity --
list_workspaces() is scoped to one product_id, not a global enumeration.
No database, no concrete implementation.
"""
from abc import ABC, abstractmethod
from typing import List

from applications.platform.workspaces.workspace import Workspace


class WorkspaceRegistry(ABC):
    @abstractmethod
    def register_workspace(self, workspace: Workspace) -> None:
        ...

    @abstractmethod
    def list_workspaces(self, product_id: str) -> List[Workspace]:
        ...
