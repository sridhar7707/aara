"""Checks every icon referenced in STATE_MAPPING.yaml exists under brand/icons."""
import os

from .types import ValidationResult

ICON_DIR = "brand/icons"
STATE_SECTIONS = ["decision_states", "risk_governor"]


def validate_icons(parsed_contracts):
    result = ValidationResult()
    state_data = parsed_contracts.get("brand/STATE_MAPPING.yaml")
    if not state_data:
        return result
    for section in STATE_SECTIONS:
        for state_key, state_meta in (state_data.get(section) or {}).items():
            if not isinstance(state_meta, dict):
                continue
            icon_file = state_meta.get("icon")
            if not icon_file:
                continue
            expected = os.path.join(ICON_DIR, icon_file)
            if not os.path.exists(expected):
                result.add(
                    "brand/STATE_MAPPING.yaml", 0, "ICON_MISSING",
                    f"Missing icon asset [{section}.{state_key}]: {expected}",
                )
    return result
