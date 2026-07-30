"""Tests for analytics/improvement_proposals.py (Phase 2 scaffolding)."""
from __future__ import annotations

import pytest

import analytics.improvement_proposals as improvement_proposals
from analytics.improvement_proposals import approve_proposal, create_proposal


@pytest.fixture(autouse=True)
def _isolated_proposals_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(improvement_proposals, "PROPOSALS_DIR", tmp_path / "improvement_proposals")


def test_create_proposal_writes_artifact_file():
    proposal = create_proposal(
        what_changes="Reduce FinBERT weight 15%",
        evidence="Phase 1B calibration flagged FinBERT overconfidence in RANGING regime",
        risk="Lower sentiment sensitivity may miss genuine news-driven moves",
    )
    artifact = improvement_proposals.PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    assert artifact.exists()
    assert proposal.approved_by is None


def test_approve_proposal_records_signoff():
    proposal = create_proposal(what_changes="x", evidence="y", risk="z")
    approved = approve_proposal(proposal.proposal_id, approved_by="ksri77")
    assert approved.approved_by == "ksri77"
    assert approved.approved_at is not None


def test_approve_proposal_missing_id_raises():
    with pytest.raises(FileNotFoundError):
        approve_proposal("PROP-does-not-exist", approved_by="ksri77")
