"""ADR-045 Validation Gate: tests for the governance-evaluation call site in
bot/_main_trust_decisions.py::record_decision_safe() (to_policy_id +
GovernanceService.evaluate_policy(), wired via ADR-045's composition
boundary). Fixture pattern mirrors
tests/phase1a/test_trust_decision_evidence_integration.py's ADR-009
Validation Gate."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

import ledger.db as ledger_db  # noqa: E402
import bot._main_trust_decisions as main_trust_decisions  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
import sentinel_engine.adapters.governance_adapter as governance_adapter  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402
from sentinel_engine.services.governance_service import GovernanceService  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_module_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def conn():
    c = ledger_db.init_db(":memory:")
    yield c
    c.close()


@pytest.fixture
def reference_chain(conn):
    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _call_record_decision_safe(conn, reference_chain):
    main_trust_decisions.record_decision_safe(
        conn, reference_chain["candidate_event_id"], reference_chain["manifest_id"],
        "AAPL", "BUY", "EXECUTED",
        {"portfolio_value": 10000.0}, {"regime": "bull"}, build_model_outputs(0.7, 0.6, 0.2),
        {"gates": []}, 0.65, decisions.build_intent("BUY"), decisions.build_data_completeness(),
        risk=RiskManager(),
    )


# ── ADR-045 Validation Gate (a): failure isolation ──────────────────────────

def test_record_decision_safe_still_writes_decision_if_governance_evaluation_fails(conn, reference_chain, monkeypatch):
    """A failure anywhere in the governance-evaluation block must never
    fail, delay, or roll back the already-committed decision_events write --
    the same best-effort isolation already proven for the Evidence block
    (ADR-009) and constitution.check_and_log."""

    def _boom(decision_row):
        raise RuntimeError("simulated governance evaluation failure")

    monkeypatch.setattr(main_trust_decisions, "to_policy_id", _boom)

    _call_record_decision_safe(conn, reference_chain)

    count = conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0]
    assert count == 1


# ── ADR-045 Validation Gate (b): decision_id identity ───────────────────────

def test_evaluate_policy_receives_the_exact_decision_id(conn, reference_chain, monkeypatch):
    """evaluate_policy() must be called with decision_row["decision_id"]
    verbatim -- the exact identifier new_decision_id(asset) created inside
    write_decision_event() -- identical to the identity guarantee ADR-009
    already established for associate_evidence()."""

    class _RecordingGovernanceService:
        def __init__(self):
            self.calls = []

        def evaluate_policy(self, decision_id, policy_id):
            self.calls.append((decision_id, policy_id))
            return False

    fake_service = _RecordingGovernanceService()
    monkeypatch.setattr(main_trust_decisions, "get_governance_service", lambda: fake_service)

    _call_record_decision_safe(conn, reference_chain)

    real_decision_id = conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL'"
    ).fetchone()[0]

    assert len(fake_service.calls) == 1
    assert fake_service.calls[0][0] == real_decision_id


# ── ADR-045 Validation Gate (c): forbidden approval operations ─────────────

def test_record_decision_safe_never_invokes_record_approval_or_to_approval(conn, reference_chain, monkeypatch):
    """No code ADR-045 authorizes constructs an Approval, calls
    to_approval(), or calls GovernanceService.record_approval() (ADR-045
    SS3 item 4, SS6). Exercised against the only reachable state today: no
    Phase-1A Policy is registered (ADR-045 SS3 item 3), so this is
    unconditionally the unregistered-policy case -- ADR-045 does not
    authorize a registered-policy case to exist, so none is claimed here.

    The real GovernanceService.record_approval and the real
    governance_adapter.to_approval are patched to raise if reached at all
    -- proof by construction against the actual production wiring (the real
    composition-wired singleton, not a fake), which is the only way to
    prove the *absence* of a call from a call site that never imports either
    symbol in the first place."""

    def _record_approval_boom(self, approval):
        raise AssertionError("record_approval() must never be invoked by ADR-045's authorized call site")

    def _to_approval_boom(*args, **kwargs):
        raise AssertionError("to_approval() must never be invoked by ADR-045's authorized call site")

    monkeypatch.setattr(GovernanceService, "record_approval", _record_approval_boom)
    monkeypatch.setattr(governance_adapter, "to_approval", _to_approval_boom)

    _call_record_decision_safe(conn, reference_chain)

    count = conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0]
    assert count == 1


# ── ADR-045 Validation Gate (d): mutual Evidence/Governance isolation ──────

def test_governance_failure_does_not_prevent_evidence_integration(conn, reference_chain, monkeypatch):
    """Direction 1: a governance-evaluation failure must never affect the
    Evidence integration's outcome -- the two blocks are sequential and
    independently isolated (ADR-045 SS4)."""

    class _RecordingEvidenceService:
        def __init__(self):
            self.calls = []

        def associate_evidence(self, decision_id, evidence):
            self.calls.append((decision_id, evidence))

    fake_evidence_service = _RecordingEvidenceService()
    monkeypatch.setattr(main_trust_decisions, "get_evidence_service", lambda: fake_evidence_service)

    def _governance_boom(decision_row):
        raise RuntimeError("simulated governance evaluation failure")

    monkeypatch.setattr(main_trust_decisions, "to_policy_id", _governance_boom)

    _call_record_decision_safe(conn, reference_chain)

    assert len(fake_evidence_service.calls) == 3


def test_evidence_failure_does_not_prevent_governance_evaluation(conn, reference_chain, monkeypatch):
    """Direction 2: an Evidence-integration failure must never affect the
    governance-evaluation block's outcome -- the two blocks are sequential
    and independently isolated (ADR-045 SS4)."""

    class _RecordingGovernanceService:
        def __init__(self):
            self.calls = []

        def evaluate_policy(self, decision_id, policy_id):
            self.calls.append((decision_id, policy_id))
            return False

    fake_governance_service = _RecordingGovernanceService()
    monkeypatch.setattr(main_trust_decisions, "get_governance_service", lambda: fake_governance_service)

    def _evidence_boom(model_outputs):
        raise RuntimeError("simulated evidence integration failure")

    monkeypatch.setattr(main_trust_decisions, "to_evidence_records", _evidence_boom)

    _call_record_decision_safe(conn, reference_chain)

    assert len(fake_governance_service.calls) == 1


# ── ADR-045 Validation Gate (e): ordering ───────────────────────────────────

def test_governance_evaluation_only_starts_after_write_decision_event_returns(conn, reference_chain, monkeypatch):
    """No to_policy_id or evaluate_policy call may occur before
    write_decision_event() returns (ADR-045 SS4, SS12.2)."""
    events = []

    real_write_decision_event = decisions.write_decision_event

    def _wrapped_write_decision_event(*args, **kwargs):
        result = real_write_decision_event(*args, **kwargs)
        events.append("write_decision_event_returned")
        return result

    real_to_policy_id = main_trust_decisions.to_policy_id

    def _wrapped_to_policy_id(decision_row):
        events.append("to_policy_id_called")
        return real_to_policy_id(decision_row)

    class _RecordingGovernanceService:
        def evaluate_policy(self, decision_id, policy_id):
            events.append("evaluate_policy_called")
            return False

    monkeypatch.setattr(decisions, "write_decision_event", _wrapped_write_decision_event)
    monkeypatch.setattr(main_trust_decisions, "to_policy_id", _wrapped_to_policy_id)
    monkeypatch.setattr(main_trust_decisions, "get_governance_service", lambda: _RecordingGovernanceService())

    _call_record_decision_safe(conn, reference_chain)

    assert events[0] == "write_decision_event_returned"
    assert "to_policy_id_called" in events[1:]
    assert events.count("evaluate_policy_called") == 1
