"""AARA-owned Principal abstraction and in-memory allocator.

Per ADR-030, Principal is exactly {principal_id: str} -- no User reference.
Per ADR-031, PrincipalRegistry is a process-local, non-durable in-memory
allocator: key is completely opaque (never inspected, derived from,
transformed, logged, or persisted beyond use as a lookup key). This module
must not import User/AuthenticationProvider -- deciding what key is, and
whether it is ever derived from a User, is a caller's decision this module
does not make.
"""
from dataclasses import dataclass
from typing import Dict
from uuid import uuid4


@dataclass(frozen=True)
class Principal:
    principal_id: str


class PrincipalRegistry:
    def __init__(self) -> None:
        self._principals: Dict[str, Principal] = {}

    def get_or_create(self, key: str) -> Principal:
        if key not in self._principals:
            self._principals[key] = Principal(principal_id=str(uuid4()))
        return self._principals[key]
