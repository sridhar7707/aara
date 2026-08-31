"""Shared, purely-presentational rendering for a non-HEALTHY integration
(ADR-061 Section 3 Category A item 4).

One shared mechanism reused by every integration-dependent Trading
Intelligence section, instead of each screen hard-coding its own single
"unavailable" string. Strictly advisory / UI-only per ADR-061 Section 2.7:
this module turns an ``IntegrationHealth`` into display text and nothing
else. It never gates, blocks, vetoes, enforces, polls, retries, or reaches
any provider, and introduces no endpoint or credential.

Only ``IntegrationHealth.status`` (plus ``retry_after`` for
``RATE_LIMITED``) is consulted. ``IntegrationHealth.detail`` is NEVER
rendered -- it can carry operator free-text, and ADR-061 Section 2.9 keeps
credential-bearing strings away from the UI. The provider name is not
surfaced either. All dynamic content is HTML-escaped.

Not owned by any one screen package -- a sibling of ``ui/shell.py``, reused
by ``ui/morning_brief/``, ``ui/portfolio_intelligence/`` and
``ui/risk_intelligence/`` the same way ``ui/shell.py`` is.
"""
import html
from typing import Optional

from applications.platform.integrations import IntegrationHealth, IntegrationStatus

# Fixed, safe, operator-facing phrases -- keyed on status only. Deliberately
# never include the provider name or any adapter / exception detail.
_STATUS_PHRASES = {
    IntegrationStatus.NOT_CONFIGURED: "not configured for this environment",
    IntegrationStatus.AUTH_FAILED: "authentication failed",
    IntegrationStatus.RATE_LIMITED: "rate limited by the provider",
    IntegrationStatus.UNAVAILABLE: "provider could not be reached",
    IntegrationStatus.API_ERROR: "provider returned an unexpected response",
}

# Any unmapped / unexpected status renders as the generic provider-failure
# phrase rather than leaking a status name.
_DEFAULT_PHRASE = _STATUS_PHRASES[IntegrationStatus.API_ERROR]

# Rendered lead-in, matching the "-- " clause style the screens' own
# unavailable strings already use (e.g. portfolio_intelligence/gradio_view.py's
# _CAPITAL_UNAVAILABLE_MESSAGE).
_PREFIX = "Data unavailable -- "

_CSS_CLASS = "aara-integration-status"

# Small shared rule, same visual treatment as the per-screen
# .pi-unavailable / .mb-unavailable-message / .ri-empty-message rules
# (muted italic, left rule) -- plain literal color values, matching every
# screen theme.py's own no-token-import convention.
CSS = """
.aara-integration-status {
  font-size: 13px;
  font-style: italic;
  color: #666666;
  border-left: 2px solid #E2E8F0;
  padding: 8px 0 8px 12px;
  margin: 4px 0;
}
"""


def _phrase_for(health: IntegrationHealth) -> str:
    phrase = _STATUS_PHRASES.get(health.status, _DEFAULT_PHRASE)
    if health.status is IntegrationStatus.RATE_LIMITED:
        retry_after = health.retry_after
        if (
            isinstance(retry_after, int)
            and not isinstance(retry_after, bool)
            and retry_after >= 0
        ):
            phrase = f"{phrase} (retry after {retry_after}s)"
    return phrase


def render_unavailable(
    health: Optional[IntegrationHealth],
    *,
    fallback_message: str,
) -> str:
    """Return an HTML fragment for an integration-backed section that is
    not available.

    * ``health is None`` -> ``fallback_message`` verbatim (HTML-escaped).
      Used by a section whose composition root recorded no health on the
      unavailable path.
    * ``health.status`` is ``HEALTHY`` -> also ``fallback_message``; this
      helper only renders the non-HEALTHY case (a HEALTHY section renders
      its real content elsewhere).
    * otherwise -> a fixed phrase for that status, plus a ``retry after``
      hint when the status is ``RATE_LIMITED`` and one is set.

    Never includes ``health.detail`` or the provider name (ADR-061
    Section 2.9). Purely presentational -- no gating, polling, retry, or
    provider access.
    """
    if health is None or health.status is IntegrationStatus.HEALTHY:
        message = fallback_message
    else:
        message = _PREFIX + _phrase_for(health)
    return f'<div class="{_CSS_CLASS}">{html.escape(message)}</div>'
