"""Test shells for api/reports_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_decision_audit_report_includes_all_sections():
    """GET /api/reports/decision-audit/{id} should include evidence, governance, approval, and outcome sections."""


def test_get_tax_efficiency_report_scopes_to_period():
    """GET /api/reports/tax-efficiency should only include lots sold within the requested period."""


def test_get_governance_compliance_report_computes_pass_rate():
    """GET /api/reports/governance-compliance should compute governance_pass_rate from the period's evaluations."""
