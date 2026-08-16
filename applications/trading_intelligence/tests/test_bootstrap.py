"""Tests for applications.trading_intelligence.bootstrap.build_application().

Uses monkeypatch to track how many times each collaborator class is
constructed and what arguments it receives, mirroring
applications.wealth_intelligence.tests.test_bootstrap's pattern -- the
returned DecisionCenterUI never exposes its repositories/services directly,
so verifying "exactly one shared instance" requires observing construction
itself rather than introspecting the final graph.
"""
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.services.sentinel_engine import SentinelEngine

from applications.trading_intelligence.adapters.sentinel_audit_source import SentinelAuditSource
from applications.trading_intelligence.adapters.sentinel_evidence_source import SentinelEvidenceSource
from applications.trading_intelligence.adapters.sentinel_governance_source import (
    SentinelGovernanceSource,
)
from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.bootstrap import (
    _InMemoryProjectionRepository,
    build_application,
)
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI


def _track_constructor_calls(monkeypatch, cls):
    calls = []
    original_init = cls.__init__

    def wrapped_init(self, *args, **kwargs):
        calls.append({"self": self, "args": args, "kwargs": kwargs})
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(cls, "__init__", wrapped_init)
    return calls


def test_build_application_returns_decision_center_ui():
    ui = build_application()

    assert isinstance(ui, DecisionCenterUI)


def test_build_application_constructs_exactly_one_ledger_repository(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, LedgerRepository)

    build_application()

    assert len(calls) == 1


def test_build_application_constructs_exactly_one_projection_repository(monkeypatch):
    calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)

    build_application()

    assert len(calls) == 1


def test_build_application_services_share_the_same_repositories(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)

    build_application()

    ledger_repository = ledger_calls[0]["self"]
    projection_repository = projection_calls[0]["self"]

    for calls in (decision_service_calls, evidence_service_calls, governance_service_calls):
        assert len(calls) == 1
        assert calls[0]["args"][0] is ledger_repository
        assert calls[0]["args"][1] is projection_repository


def test_build_application_constructs_sentinel_engine_once_with_shared_services(monkeypatch):
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)
    sentinel_engine_calls = _track_constructor_calls(monkeypatch, SentinelEngine)

    build_application()

    assert len(sentinel_engine_calls) == 1
    call = sentinel_engine_calls[0]
    assert call["args"][0] is decision_service_calls[0]["self"]
    assert call["args"][1] is evidence_service_calls[0]["self"]
    assert call["args"][2] is governance_service_calls[0]["self"]


def test_build_application_read_chain_shares_the_same_projection_repository(monkeypatch):
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    source_calls = _track_constructor_calls(monkeypatch, SentinelProjectionDecisionSource)

    build_application()

    projection_repository = projection_calls[0]["self"]
    assert len(source_calls) == 1
    assert source_calls[0]["args"][0] is projection_repository


def test_build_application_wires_query_service_and_controller_once(monkeypatch):
    query_service_calls = _track_constructor_calls(monkeypatch, DecisionQueryService)
    evidence_query_service_calls = _track_constructor_calls(monkeypatch, DecisionEvidenceQueryService)
    governance_query_service_calls = _track_constructor_calls(
        monkeypatch, DecisionGovernanceQueryService
    )
    audit_source_calls = _track_constructor_calls(monkeypatch, SentinelAuditSource)
    controller_calls = _track_constructor_calls(monkeypatch, DecisionCenterController)

    build_application()

    assert len(query_service_calls) == 1
    assert len(evidence_query_service_calls) == 1
    assert len(governance_query_service_calls) == 1
    assert len(audit_source_calls) == 1
    assert len(controller_calls) == 1
    assert controller_calls[0]["args"][0] is query_service_calls[0]["self"]
    assert controller_calls[0]["args"][1] is evidence_query_service_calls[0]["self"]
    assert controller_calls[0]["args"][2] is governance_query_service_calls[0]["self"]
    assert controller_calls[0]["args"][3] is audit_source_calls[0]["self"]


def test_build_application_wires_evidence_read_chain_off_the_same_repositories(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_query_calls = _track_constructor_calls(monkeypatch, DecisionQuery)
    evidence_source_calls = _track_constructor_calls(monkeypatch, SentinelEvidenceSource)

    build_application()

    ledger_repository = ledger_calls[0]["self"]
    projection_repository = projection_calls[0]["self"]

    assert len(decision_query_calls) == 1
    assert decision_query_calls[0]["args"][0] is ledger_repository
    assert decision_query_calls[0]["args"][1] is projection_repository

    assert len(evidence_source_calls) == 1
    assert evidence_source_calls[0]["args"][0] is decision_query_calls[0]["self"]


def test_build_application_wires_evidence_and_governance_read_chains_off_the_same_decision_query(
    monkeypatch,
):
    decision_query_calls = _track_constructor_calls(monkeypatch, DecisionQuery)
    evidence_source_calls = _track_constructor_calls(monkeypatch, SentinelEvidenceSource)
    governance_source_calls = _track_constructor_calls(monkeypatch, SentinelGovernanceSource)

    build_application()

    assert len(decision_query_calls) == 1
    decision_query = decision_query_calls[0]["self"]

    assert len(evidence_source_calls) == 1
    assert evidence_source_calls[0]["args"][0] is decision_query

    assert len(governance_source_calls) == 1
    assert governance_source_calls[0]["args"][0] is decision_query


def test_build_application_wires_audit_read_chain_off_the_same_decision_query(monkeypatch):
    decision_query_calls = _track_constructor_calls(monkeypatch, DecisionQuery)
    audit_source_calls = _track_constructor_calls(monkeypatch, SentinelAuditSource)

    build_application()

    assert len(decision_query_calls) == 1
    decision_query = decision_query_calls[0]["self"]

    assert len(audit_source_calls) == 1
    assert audit_source_calls[0]["args"][0] is decision_query


def test_build_application_does_not_duplicate_the_object_graph(monkeypatch):
    ledger_calls = _track_constructor_calls(monkeypatch, LedgerRepository)
    projection_calls = _track_constructor_calls(monkeypatch, _InMemoryProjectionRepository)
    decision_service_calls = _track_constructor_calls(monkeypatch, DecisionService)
    evidence_service_calls = _track_constructor_calls(monkeypatch, EvidenceService)
    governance_service_calls = _track_constructor_calls(monkeypatch, GovernanceService)
    sentinel_engine_calls = _track_constructor_calls(monkeypatch, SentinelEngine)
    source_calls = _track_constructor_calls(monkeypatch, SentinelProjectionDecisionSource)
    query_service_calls = _track_constructor_calls(monkeypatch, DecisionQueryService)
    decision_query_calls = _track_constructor_calls(monkeypatch, DecisionQuery)
    evidence_source_calls = _track_constructor_calls(monkeypatch, SentinelEvidenceSource)
    evidence_query_service_calls = _track_constructor_calls(monkeypatch, DecisionEvidenceQueryService)
    governance_source_calls = _track_constructor_calls(monkeypatch, SentinelGovernanceSource)
    governance_query_service_calls = _track_constructor_calls(
        monkeypatch, DecisionGovernanceQueryService
    )
    audit_source_calls = _track_constructor_calls(monkeypatch, SentinelAuditSource)
    controller_calls = _track_constructor_calls(monkeypatch, DecisionCenterController)

    build_application()

    assert len(ledger_calls) == 1
    assert len(projection_calls) == 1
    assert len(decision_service_calls) == 1
    assert len(evidence_service_calls) == 1
    assert len(governance_service_calls) == 1
    assert len(sentinel_engine_calls) == 1
    assert len(source_calls) == 1
    assert len(query_service_calls) == 1
    assert len(decision_query_calls) == 1
    assert len(evidence_source_calls) == 1
    assert len(evidence_query_service_calls) == 1
    assert len(governance_source_calls) == 1
    assert len(governance_query_service_calls) == 1
    assert len(audit_source_calls) == 1
    assert len(controller_calls) == 1

    repository_instances = {ledger_calls[0]["self"], projection_calls[0]["self"]}
    assert len(repository_instances) == 2  # exactly one of each, never duplicated


def test_build_application_seeds_five_decisions_across_the_full_decision_state_range():
    ui = build_application()

    list_rows, *_detail = ui._render_screen()

    assert len(list_rows) == 5
    statuses = {row[0]: row[3] for row in list_rows}
    assert statuses["dec-seed-001"] == "Decision Created"
    assert statuses["dec-seed-002"] == "Evidence Attached"
    assert statuses["dec-seed-003"] == "Approval Recorded"
    assert statuses["dec-seed-004"] == "Governance Evaluated"
    assert statuses["dec-seed-005"] == "Approval Recorded"


def test_build_application_seeds_both_approval_verdicts_in_the_decision_list():
    """dec-seed-003 (APPROVED) and dec-seed-005 (REJECTED) are the only two
    seeds carrying a recorded approval, so the Decision List's Verdict
    column demonstrates both real verdicts -- not just one -- alongside the
    "no verdict yet" state the other three seeds show."""
    ui = build_application()

    list_rows, *_detail = ui._render_screen()
    verdicts = {row[0]: row[6] for row in list_rows}

    assert verdicts["dec-seed-003"] == (
        '<span class="aara-list-verdict-badge verdict-approved">Approved</span>'
    )
    assert verdicts["dec-seed-005"] == (
        '<span class="aara-list-verdict-badge verdict-rejected">Rejected</span>'
    )
    assert verdicts["dec-seed-001"] == "-"
    assert verdicts["dec-seed-002"] == "-"
    assert verdicts["dec-seed-004"] == "-"


def test_build_application_seeded_decisions_are_reachable_by_id():
    """The seed data is produced entirely through the real Sentinel Engine
    write path (DecisionService/EvidenceService/GovernanceService), then
    read back through Trading Intelligence's own read-only chain -- proving
    the vertical slice actually renders Sentinel Engine data, not
    hand-built projections standing in for it."""
    ui = build_application()

    (
        header, lifecycle, confidence, _updated, _status, _why_html,
        _evidence_html, _governance_html, _approval_html, _audit_html,
    ) = ui._render_detail("dec-seed-003")

    assert "NVDA" in header
    assert "SELL" in header
    assert confidence == "91%"
    assert (
        'class="stage active"><span class="dot"></span>'
        '<a class="label" href="#approval-section">Approval</a>'
    ) in lifecycle


def test_build_application_seeds_evidence_for_decisions_that_had_it_attached():
    """dec-seed-002/003 have evidence attached via engine.attach_evidence()
    in _seed_decisions(); dec-seed-001 deliberately does not, so both the
    "has evidence" and "no evidence" states are demonstrated by the existing
    seed path without any change to it. dec-seed-002/003 each attach
    evidence at their own distinct timestamp (staggered seed data), so each
    is asserted against its own value rather than one shared literal."""
    ui = build_application()

    *_, evidence_002, _governance_002, _approval_002, _audit_002 = ui._render_detail("dec-seed-002")
    *_, evidence_003, _governance_003, _approval_003, _audit_003 = ui._render_detail("dec-seed-003")

    assert "NEWS_SENTIMENT" in evidence_002
    assert "newsapi" in evidence_002
    assert "2026-08-08 08:52 UTC" in evidence_002

    assert "NEWS_SENTIMENT" in evidence_003
    assert "newsapi" in evidence_003
    assert "2026-08-08 09:11 UTC" in evidence_003


def test_build_application_seeded_decision_without_attached_evidence_has_none():
    ui = build_application()

    *_, evidence_html, _governance_html, _approval_html, _audit_html = ui._render_detail(
        "dec-seed-001"
    )

    assert evidence_html == '<div class="aara-empty-message">No evidence attached yet.</div>'


def test_build_application_seeds_governance_and_approval_for_the_fully_approved_decision():
    """dec-seed-003 is the only seed decision driven through
    record_approval() in bootstrap.py's _seed_decisions() -- dec-seed-004
    also reaches evaluate_policy() but deliberately stops before
    record_approval(), and dec-seed-001/002 reach neither -- so "has
    governance and approval", "has governance but not approval", and "has
    neither" are all demonstrated by the existing seed path."""
    ui = build_application()

    *_, _evidence_html, governance_html, approval_html, audit_html = ui._render_detail(
        "dec-seed-003"
    )

    # evaluate_policy() timestamps with datetime.utcnow() (unlike
    # record_approval(), which uses the seed's own fixed approval
    # timestamp), so only policy_id/enabled are asserted precisely here;
    # evaluated_at is only checked for well-formed presence.
    assert "pol-seed-001" in governance_html
    assert "Yes" in governance_html
    assert "UTC" in governance_html
    assert "Approved" in approval_html
    assert "risk_officer" in approval_html
    assert "2026-08-08 09:34 UTC" in approval_html

    # dec-seed-003 runs the full lifecycle (create -> evidence -> governance
    # -> approval), so its audit trail carries all four event types.
    # evaluate_policy() stamps GOVERNANCE_EVALUATED with real-clock
    # datetime.utcnow() (unlike the other three, which use the seed's own
    # fixed timestamps -- see _seed_decisions()'s own docstring), so its
    # sort position relative to APPROVAL_RECORDED's fixed 2026-08-08
    # timestamp depends on wall-clock time and is not asserted here; only
    # the two fixed-timestamp events' relative order is deterministic.
    assert "Decision Created" in audit_html
    assert "Evidence Attached" in audit_html
    assert "Governance Evaluated" in audit_html
    assert "Approval Recorded" in audit_html
    assert audit_html.index("Decision Created") < audit_html.index("Evidence Attached")


def test_build_application_seeded_decisions_without_governance_or_approval_have_none():
    ui = build_application()

    *_, _evidence_html_1, governance_html_1, approval_html_1, _audit_html_1 = ui._render_detail(
        "dec-seed-001"
    )
    *_, _evidence_html_2, governance_html_2, approval_html_2, _audit_html_2 = ui._render_detail(
        "dec-seed-002"
    )

    assert governance_html_1 == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html_1 == '<div class="aara-empty-message">No approval recorded.</div>'
    assert governance_html_2 == (
        '<div class="aara-empty-message">No governance evaluation recorded.</div>'
    )
    assert approval_html_2 == '<div class="aara-empty-message">No approval recorded.</div>'


def test_build_application_seeds_a_rejected_decision_end_to_end():
    """dec-seed-005 exercises the REJECTED approval path through the full
    lifecycle (create -> evidence -> governance -> approval) -- the one
    path no prior seed demonstrated, since dec-seed-003 is the only other
    seed reaching record_approval(), and always with APPROVED."""
    ui = build_application()

    (
        header, lifecycle, confidence, _updated, _status, _why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_detail("dec-seed-005")

    assert "TSLA" in header
    assert "BUY" in header
    assert confidence == "61%"
    assert (
        'class="stage active"><span class="dot"></span>'
        '<a class="label" href="#approval-section">Approval</a>'
    ) in lifecycle
    assert "NEWS_SENTIMENT" in evidence_html
    assert "pol-seed-001" in governance_html
    assert "Rejected" in approval_html
    assert "risk_officer" in approval_html
    assert "2026-08-08 10:04 UTC" in approval_html
    assert "Approval Recorded" in audit_html


def test_build_application_seeds_a_decision_awaiting_approval_after_governance():
    """dec-seed-004 stops at GOVERNANCE_EVALUATED -- governance passed, no
    record_approval() call -- the one DecisionState terminal-status gap
    the original three seeds left uncovered (see _seed_decisions()'s own
    docstring)."""
    ui = build_application()

    (
        header, lifecycle, confidence, _updated, _status, _why_html,
        evidence_html, governance_html, approval_html, audit_html,
    ) = ui._render_detail("dec-seed-004")

    assert "GOOGL" in header
    assert "BUY" in header
    assert confidence == "83%"
    assert (
        'class="stage active"><span class="dot"></span>'
        '<a class="label" href="#governance-section">Governance</a>'
    ) in lifecycle
    assert "NEWS_SENTIMENT" in evidence_html
    assert "pol-seed-001" in governance_html
    assert "Yes" in governance_html
    assert approval_html == '<div class="aara-empty-message">No approval recorded.</div>'
    assert "Governance Evaluated" in audit_html
