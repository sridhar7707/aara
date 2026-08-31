"""Unit tests for the shared IntegrationHealth unavailable-state renderer
(ADR-061 Section 3 Category A item 4).

Covers: every IntegrationStatus, the None / HEALTHY fallback, the
RATE_LIMITED retry_after hint, HTML escaping, and the ADR-061 Section 2.9
rule that health.detail (and the provider name) are never rendered.
"""
import html as _html
from datetime import datetime, timezone

import pytest

from applications.platform.integrations import IntegrationHealth, IntegrationStatus
from applications.trading_intelligence.ui.integration_health_view import (
    CSS,
    render_unavailable,
)

_FALLBACK = "This section has no wired data source."


@pytest.mark.parametrize(
    "health, expected_phrase",
    [
        (IntegrationHealth.not_configured("p"), "not configured for this environment"),
        (IntegrationHealth.auth_failed("p"), "authentication failed"),
        (IntegrationHealth.rate_limited("p"), "rate limited by the provider"),
        (IntegrationHealth.unavailable("p"), "provider could not be reached"),
        (IntegrationHealth.api_error("p"), "provider returned an unexpected response"),
    ],
)
def test_every_non_healthy_status_maps_to_its_fixed_phrase(health, expected_phrase):
    out = render_unavailable(health, fallback_message=_FALLBACK)

    assert expected_phrase in out
    assert out.startswith('<div class="aara-integration-status">')
    assert out.rstrip().endswith("</div>")
    # a known reason replaces, never appends, the generic fallback sentence
    assert _FALLBACK not in out


def test_healthy_status_uses_the_supplied_fallback_message():
    out = render_unavailable(IntegrationHealth.healthy("p"), fallback_message=_FALLBACK)

    assert out == f'<div class="aara-integration-status">{_html.escape(_FALLBACK)}</div>'


def test_none_health_renders_the_fallback_message_verbatim():
    out = render_unavailable(None, fallback_message=_FALLBACK)

    assert out == f'<div class="aara-integration-status">{_html.escape(_FALLBACK)}</div>'
    assert _FALLBACK in out


def test_rate_limited_includes_retry_after_when_present():
    out = render_unavailable(
        IntegrationHealth.rate_limited("p", retry_after=42),
        fallback_message=_FALLBACK,
    )

    assert "rate limited by the provider" in out
    assert "retry after 42s" in out


def test_rate_limited_omits_retry_after_when_absent():
    out = render_unavailable(
        IntegrationHealth.rate_limited("p"), fallback_message=_FALLBACK
    )

    assert "rate limited by the provider" in out
    assert "retry after" not in out


def test_retry_after_hint_only_applies_to_rate_limited():
    unavailable_with_retry = IntegrationHealth(
        provider="p",
        status=IntegrationStatus.UNAVAILABLE,
        checked_at=datetime.now(timezone.utc),
        retry_after=15,
    )
    out = render_unavailable(unavailable_with_retry, fallback_message=_FALLBACK)

    assert "provider could not be reached" in out
    assert "retry after" not in out


def test_dynamic_content_is_html_escaped():
    out = render_unavailable(
        None, fallback_message='<script>alert("x")</script> & <b>hi</b>'
    )

    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&amp;" in out


@pytest.mark.parametrize(
    "factory",
    [
        IntegrationHealth.not_configured,
        IntegrationHealth.auth_failed,
        IntegrationHealth.unavailable,
        IntegrationHealth.api_error,
    ],
)
def test_health_detail_and_provider_name_are_never_rendered(factory):
    detail = "token=sk-live-SHOULD-NOT-APPEAR raw exception text"
    health = factory("secret-provider-name", detail=detail)

    out = render_unavailable(health, fallback_message=_FALLBACK)

    assert "sk-live-SHOULD-NOT-APPEAR" not in out
    assert "raw exception text" not in out
    assert detail not in out
    assert "secret-provider-name" not in out


def test_rate_limited_detail_is_also_never_rendered():
    health = IntegrationHealth.rate_limited(
        "p", retry_after=5, detail="X-Api-Key: abcd1234"
    )

    out = render_unavailable(health, fallback_message=_FALLBACK)

    assert "abcd1234" not in out
    assert "X-Api-Key" not in out
    assert "retry after 5s" in out


def test_output_is_a_single_wrapped_div():
    out = render_unavailable(
        IntegrationHealth.auth_failed("p"), fallback_message=_FALLBACK
    )

    assert out.count("<div") == 1
    assert out.count("</div>") == 1


def test_css_constant_defines_the_shared_class_rule():
    assert ".aara-integration-status {" in CSS
    assert "}" in CSS
