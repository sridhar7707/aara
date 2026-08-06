"""Test shells for services/decision_service.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_create_returns_decision_in_identified_state():
    """DecisionService.create() should return a Decision with status IDENTIFIED."""


def test_get_raises_for_unknown_decision_id():
    """DecisionService.get() should raise when the decision does not exist."""


def test_get_pending_excludes_closed_decisions():
    """DecisionService.get_pending() should only return decisions awaiting action."""
