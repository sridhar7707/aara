"""Phase 2 scaffolding (phase2_requirements.md Section 4): Controlled
Improvement Loop proposal artifacts (OBSERVE -> MEASURE -> RECOMMEND ->
APPROVE steps). Writes a JSON proposal file per candidate model change --
deliberately NOT a production ledger table, matching Section 6's mapping
("writes proposal artifacts, not production tables").

DEPLOY (step 5) is intentionally not implemented here: an approved proposal
is carried out through the existing deployment-manifest promotion path
(ledger.ledger.transition_manifest), the same mechanism that already gates
production model swaps today. This module never calls it -- reimplementing
deploy here would create a second path to production, which is exactly what
the frozen "single write path" decision (REQUIREMENTS_MATRIX.md Frozen
Decision #6) rules out.

Not wired into any pipeline -- see analytics/regime_views.py's module
docstring for the same gating note.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger("tradegenie.analytics.improvement_proposals")

PROPOSALS_DIR = Path("data/improvement_proposals")


@dataclass
class ImprovementProposal:
    proposal_id: str
    created_at: str
    what_changes: str
    evidence: str
    risk: str
    approved_by: str | None = None
    approved_at: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _proposal_path(proposal_id: str) -> Path:
    return PROPOSALS_DIR / f"{proposal_id}.json"


def _write(proposal: ImprovementProposal) -> None:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    _proposal_path(proposal.proposal_id).write_text(json.dumps(asdict(proposal), indent=2))


def _read(proposal_id: str) -> ImprovementProposal:
    data = json.loads(_proposal_path(proposal_id).read_text())
    return ImprovementProposal(**data)


def list_proposals() -> list[ImprovementProposal]:
    """Every proposal artifact on disk, newest first. Empty list (not an
    error) if PROPOSALS_DIR doesn't exist yet -- no proposal has ever
    been created."""
    if not PROPOSALS_DIR.is_dir():
        return []
    proposals = [
        ImprovementProposal(**json.loads(p.read_text()))
        for p in PROPOSALS_DIR.glob("*.json")
    ]
    return sorted(proposals, key=lambda p: p.created_at, reverse=True)


def create_proposal(what_changes: str, evidence: str, risk: str) -> ImprovementProposal:
    """OBSERVE/MEASURE/RECOMMEND steps: write a proposal artifact to disk.
    Does not touch any ledger table."""
    proposal = ImprovementProposal(
        proposal_id=f"PROP-{uuid.uuid4().hex[:12]}",
        created_at=_utc_now(),
        what_changes=what_changes,
        evidence=evidence,
        risk=risk,
    )
    _write(proposal)
    _log.info("Improvement proposal created: %s", proposal.proposal_id)
    return proposal


def approve_proposal(proposal_id: str, approved_by: str) -> ImprovementProposal:
    """APPROVE step: explicit human sign-off, recorded on the existing
    proposal artifact. Raises FileNotFoundError if proposal_id doesn't
    exist -- callers must create before approving."""
    proposal = _read(proposal_id)
    proposal.approved_by = approved_by
    proposal.approved_at = _utc_now()
    _write(proposal)
    _log.info("Improvement proposal approved: %s by %s", proposal_id, approved_by)
    return proposal
