"""Test shells for api/approval_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_approve_endpoint_does_not_execute():
    """POST .../approve should only record approval, never dispatch/execute."""


def test_defer_endpoint_requires_reason():
    """POST .../defer should reject an empty reason."""


def test_decline_endpoint_is_terminal():
    """POST .../decline should move the decision to a terminal state."""
