"""Top-level config entry point.

IMPLEMENTATION_HANDOFF.md's repository tree lists both this file and
backend/config/settings.py. Rather than duplicate settings definitions
in two places, this module re-exports backend/config/settings.py --
that package is the actual source of truth for configuration.
"""

from sentinel.backend.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
