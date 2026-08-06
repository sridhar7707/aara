"""Test shells for domain/approval.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_approval_requires_explicit_approver():
    """Approval.approved_by must be present -- no implicit/auto-approval."""
