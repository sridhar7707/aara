"""Product registration interface.

Registry-level knowledge only -- not a product's internals, per
docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md Section 4 ("Products... a
registry-level knowledge, not their internals").

Minimal extension of the descriptor model from
docs/platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md Section 2 --
`workspace_routes` deliberately not included here (UI routing is explicitly
out of scope for this step). `status` defaults to None rather than an
invented value like "ACTIVE": that document left the status vocabulary as an
open decision, and this dataclass should not silently resolve it.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    entitlement_required: str
    description: str = ""
    status: Optional[str] = None


class ProductRegistry(ABC):
    @abstractmethod
    def register(self, product: Product) -> None:
        ...

    @abstractmethod
    def list_products(self) -> List[Product]:
        ...
