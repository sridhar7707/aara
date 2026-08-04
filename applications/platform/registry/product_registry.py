"""Product registration interface.

Registry-level knowledge only (product id, name) -- not a product's
internals, per docs/platform/AARA_PLATFORM_SHELL_ARCHITECTURE.md Section 4
("Products... a registry-level knowledge, not their internals").
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str


class ProductRegistry(ABC):
    @abstractmethod
    def register(self, product: Product) -> None:
        ...

    @abstractmethod
    def list_products(self) -> List[Product]:
        ...
