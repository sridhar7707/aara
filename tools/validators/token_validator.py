"""Checks brand/design_system/tokens.css exists and defines every required
CSS custom property."""
import os

from .types import ValidationResult

TOKENS_PATH = "brand/design_system/tokens.css"

REQUIRED_TOKENS = [
    "--color-navy-primary",
    "--color-emerald-secondary",
    "--color-gold-accent",
    "--color-background-warm",
    "--color-surface-white",
    "--status-pending",
    "--status-approved",
    "--status-deferred",
    "--status-declined",
    "--status-escalated",
    "--font-primary",
    "--font-data",
    "--breakpoint-mobile",
    "--breakpoint-tablet",
    "--breakpoint-desktop",
]


def validate_tokens():
    result = ValidationResult()
    if not os.path.exists(TOKENS_PATH):
        result.add(TOKENS_PATH, 0, "TOKENS_FILE_MISSING", f"Critical: {TOKENS_PATH} missing!", "BLOCK")
        return result
    with open(TOKENS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    for token in REQUIRED_TOKENS:
        if token not in content:
            result.add(TOKENS_PATH, 0, "TOKEN_MISSING", f"Missing required design token in tokens.css: {token}")
    return result
