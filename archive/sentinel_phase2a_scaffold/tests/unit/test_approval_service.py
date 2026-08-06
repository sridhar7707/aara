"""Test shells for services/approval_service.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_approve_requires_reason():
    """ApprovalService.approve() should require a non-empty reason."""


def test_defer_does_not_close_the_decision():
    """ApprovalService.defer() should leave the decision open for later review."""


def test_decline_is_terminal():
    """ApprovalService.decline() should move the decision to a terminal state."""


def test_escalate_routes_to_governance_review():
    """ApprovalService.escalate() should be usable from any non-terminal state."""
