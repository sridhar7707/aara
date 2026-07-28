"""Canonical serialization and SHA-256 hash-chaining for the Immutable Trust
Ledger (FR-0.3, FR-0.4, NFR-1). See docs/architecture/phase0_data_model.md
Section 4.

record_hash = SHA256(canonical_json(payload) + previous_record_hash)

payload is the *logical* row -- JSON-typed columns stay as native dicts/lists
here; flattening to per-column JSON TEXT for storage happens in ledger.py,
after hashing. Hashing the nested structure directly (rather than the
already-stringified column values) means the hash is independent of column
storage order or a later change to how a specific JSON column gets
serialized for storage.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key, whitespace-free JSON serialization -- the same
    logical payload always hashes identically regardless of code path or
    dict insertion order."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_record_hash(payload: dict[str, Any], previous_record_hash: str) -> str:
    """SHA-256 hex digest of canonical_json(payload) + previous_record_hash."""
    material = canonical_json(payload) + previous_record_hash
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
