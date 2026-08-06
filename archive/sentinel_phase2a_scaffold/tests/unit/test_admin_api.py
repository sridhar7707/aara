"""Test shells for api/admin_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_governance_rules_returns_active_rules_only():
    """GET /api/admin/governance/rules should list rules with their enabled state."""


def test_get_ledger_health_reports_chain_status_per_table():
    """GET /api/admin/ledger-health should report chain_status and issues per ledger table."""
