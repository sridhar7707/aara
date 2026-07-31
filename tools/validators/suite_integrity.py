"""Validates the governance validator suite's own self-declaration
(tools/validators/VERSION.yaml) -- a 'frozen' governance suite that
silently drifts its own status or strict-mode flag would be worse than no
self-check at all, since every other check in this package implicitly
trusts strict_mode to decide BLOCK vs WARN severity.
"""
import os

from .types import ValidationResult
from .yaml_contracts import load_yaml_strict

VERSION_PATH = "tools/validators/VERSION.yaml"
REQUIRED_FIELDS = ["name", "version", "compatible_brand_version", "status", "strict_mode"]


def load_validator_suite():
    """Returns (validator_suite: dict | None, ValidationResult)."""
    result = ValidationResult()
    if not os.path.exists(VERSION_PATH):
        result.add(VERSION_PATH, 0, "VALIDATOR_VERSION_MISSING",
                    f"Missing validator self-integrity file: {VERSION_PATH}", "BLOCK")
        return None, result
    try:
        data = load_yaml_strict(VERSION_PATH)
    except Exception as e:
        result.add(VERSION_PATH, 0, "VALIDATOR_VERSION_INVALID", f"Invalid YAML: {e}", "BLOCK")
        return None, result

    suite = (data or {}).get("validator_suite")
    if not suite:
        result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_MISSING",
                    "Missing top-level validator_suite: section", "BLOCK")
        return None, result

    for field in REQUIRED_FIELDS:
        if field not in suite:
            result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_FIELD_MISSING",
                        f"validator_suite: missing required field: {field}", "BLOCK")

    status = suite.get("status")
    if "status" in suite and status != "frozen":
        result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_NOT_FROZEN",
                    f"validator_suite.status must be 'frozen', got {status!r}", "BLOCK")

    strict_mode = suite.get("strict_mode")
    # isinstance(True, int) is True in Python (bool subclasses int), but
    # isinstance(1, bool) is False -- checking isinstance(..., bool) first
    # correctly accepts real YAML booleans and rejects "true"/"false"
    # strings and 1/0 ints.
    if "strict_mode" in suite and not isinstance(strict_mode, bool):
        result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_STRICT_MODE_TYPE",
                    f"validator_suite.strict_mode must be a YAML boolean (true/false), "
                    f"got {strict_mode!r} ({type(strict_mode).__name__})", "BLOCK")

    return suite, result
