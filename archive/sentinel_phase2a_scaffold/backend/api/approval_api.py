"""Approval API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "Decision Governance Commands"
(authoritative REST contract). These are the only endpoints in that
document under the /api/v1/ prefix -- decision reads and portfolio/
governance reads are unversioned; approval commands are versioned
because they write immutable ledger events.

POST /api/v1/decisions/{id}/approve (approval only; does not execute)
POST /api/v1/decisions/{id}/defer
POST /api/v1/decisions/{id}/decline
POST /api/v1/decisions/{id}/escalate

Lifecycle: Decision -> Approved -> Dispatch Intent -> Execution Event
are separate flows. Dispatch/execution are out of scope for Phase 2A.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/decisions", tags=["approval"])


@router.post("/{decision_id}/approve")
def approve_decision(decision_id: str) -> dict:
    raise NotImplementedError


@router.post("/{decision_id}/defer")
def defer_decision(decision_id: str) -> dict:
    raise NotImplementedError


@router.post("/{decision_id}/decline")
def decline_decision(decision_id: str) -> dict:
    raise NotImplementedError


@router.post("/{decision_id}/escalate")
def escalate_decision(decision_id: str) -> dict:
    raise NotImplementedError
