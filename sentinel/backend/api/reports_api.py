"""Reports API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "5. Reporting" (authoritative REST
contract). Added during scaffold expansion; not among
IMPLEMENTATION_HANDOFF.md's Phase 2A workflow-priority endpoints, but
report generation is in scope for Phase 2A audit trail requirements
(IMPLEMENTATION_HANDOFF.md Immutable Principle 7: Complete Auditability).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/decision-audit/{decision_id}")
def get_decision_audit_report(decision_id: str) -> dict:
    """Complete audit trail export (PDF-ready). UI pipes this to a PDF
    renderer; no PDF generation happens in this layer."""
    raise NotImplementedError


@router.get("/tax-efficiency")
def get_tax_efficiency_report() -> dict:
    """Tax reporting for a period (realized gains/losses, wash-sale
    analysis)."""
    raise NotImplementedError


@router.get("/governance-compliance")
def get_governance_compliance_report() -> dict:
    """Governance compliance report for a period (pass rate, escalations,
    per-rule performance)."""
    raise NotImplementedError
