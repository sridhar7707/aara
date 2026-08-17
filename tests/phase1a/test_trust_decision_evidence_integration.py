"""ADR-009 Validation Gate: tests for the evidence-integration call site in
bot/_main_trust_decisions.py::record_decision_safe() (to_evidence_records +
EvidenceService.associate_evidence, wired via ADR-013's composition
boundary). Fixture pattern mirrors tests/phase1a/test_decision_capture.py
and tests/phase1a/test_constitution.py."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

import ledger.db as ledger_db  # noqa: E402
import bot._main_trust_decisions as main_trust_decisions  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402


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


# ── ADR-009 Validation Gate (a): failure isolation ──────────────────────────

def test_record_decision_safe_still_writes_decision_if_evidence_integration_fails(conn, reference_chain, monkeypatch):
    """A failure anywhere in the two-stage evidence-integration sequence
    (translation or association) must never fail, delay, or roll back the
    already-committed decision_events write -- the same best-effort
    isolation already proven for constitution.check_and_log."""

    def _boom(model_outputs):
        raise RuntimeError("simulated evidence integration failure")

    monkeypatch.setattr(main_trust_decisions, "to_evidence_records", _boom)

    _call_record_decision_safe(conn, reference_chain)

    count = conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0]
    assert count == 1


# ── ADR-009 Validation Gate (b): decision_id identity ───────────────────────

def test_associate_evidence_receives_the_exact_decision_id(conn, reference_chain, monkeypatch):
    """Every associate_evidence() call must use decision_row["decision_id"]
    verbatim -- the exact identifier new_decision_id(asset) created inside
    write_decision_event() -- for all three Evidence records produced for
    one decision."""

    class _RecordingEvidenceService:
        def __init__(self):
            self.calls = []

        def associate_evidence(self, decision_id, evidence):
            self.calls.append((decision_id, evidence))

    fake_service = _RecordingEvidenceService()
    monkeypatch.setattr(main_trust_decisions, "get_evidence_service", lambda: fake_service)

    _call_record_decision_safe(conn, reference_chain)

    real_decision_id = conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL'"
    ).fetchone()[0]

    assert len(fake_service.calls) == 3
    assert all(decision_id == real_decision_id for decision_id, _ in fake_service.calls)


# ── ADR-009 Validation Gate (c): ordering ───────────────────────────────────

def test_evidence_integration_only_starts_after_write_decision_event_returns(conn, reference_chain, monkeypatch):
    """No to_evidence_records or associate_evidence call may occur before
    write_decision_event() returns."""
    events = []

    real_write_decision_event = decisions.write_decision_event

    def _wrapped_write_decision_event(*args, **kwargs):
        result = real_write_decision_event(*args, **kwargs)
        events.append("write_decision_event_returned")
        return result

    real_to_evidence_records = main_trust_decisions.to_evidence_records

    def _wrapped_to_evidence_records(model_outputs):
        events.append("to_evidence_records_called")
        return real_to_evidence_records(model_outputs)

    class _RecordingEvidenceService:
        def associate_evidence(self, decision_id, evidence):
            events.append("associate_evidence_called")

    monkeypatch.setattr(decisions, "write_decision_event", _wrapped_write_decision_event)
    monkeypatch.setattr(main_trust_decisions, "to_evidence_records", _wrapped_to_evidence_records)
    monkeypatch.setattr(main_trust_decisions, "get_evidence_service", lambda: _RecordingEvidenceService())

    _call_record_decision_safe(conn, reference_chain)

    assert events[0] == "write_decision_event_returned"
    assert "to_evidence_records_called" in events[1:]
    assert events.count("associate_evidence_called") == 3


# ── ADR-034: cached-headline propagation ────────────────────────────────────

def test_entry_decision_recorder_passes_symbol_and_preserves_headlines(conn, reference_chain, monkeypatch):
    """EntryDecisionRecorder.__init__ must call get_cached_headlines with the
    exact symbol it was constructed with, and thread its result unchanged
    into model_outputs['finbert']['metadata']['headlines']."""
    calls = []

    def _fake_get_cached_headlines(ticker):
        calls.append(ticker)
        return ["AAPL headline one", "AAPL headline two"]

    monkeypatch.setattr(main_trust_decisions, "get_cached_headlines", _fake_get_cached_headlines)

    recorder = main_trust_decisions.EntryDecisionRecorder(
        conn, reference_chain["candidate_event_id"], reference_chain["manifest_id"],
        "AAPL", 0.7, 0.6, 0.2, 0.5, "bull", 10000.0, 5000.0, None,
    )

    assert calls == ["AAPL"]
    assert recorder.model_outputs["finbert"]["metadata"]["headlines"] == [
        "AAPL headline one", "AAPL headline two",
    ]


def test_record_exit_decision_safe_passes_symbol_and_preserves_headlines(conn, reference_chain, monkeypatch):
    """record_exit_decision_safe must call get_cached_headlines with the
    exact symbol passed to it, and thread its result unchanged into
    model_outputs['finbert']['metadata']['headlines']."""
    calls = []

    def _fake_get_cached_headlines(ticker):
        calls.append(ticker)
        return ["Exit-path headline"]

    monkeypatch.setattr(main_trust_decisions, "get_cached_headlines", _fake_get_cached_headlines)

    captured = {}

    def _fake_record_decision_safe(trust_conn, candidate_event_id, deployment_manifest_id,
                                    asset, action, event_type, portfolio_snapshot, market_context,
                                    model_outputs, risk_checks, final_confidence, intent,
                                    data_completeness, risk=None):
        captured["model_outputs"] = model_outputs

    monkeypatch.setattr(main_trust_decisions, "record_decision_safe", _fake_record_decision_safe)

    ledger_ctx = main_trust_decisions.ExitLedgerContext(
        trust_conn=conn, candidate_event_id=reference_chain["candidate_event_id"],
        deployment_manifest_id=reference_chain["manifest_id"],
        xgb_prob=0.3, lstm_prob=0.4, sentiment=-0.1, macro_score=0.5,
    )

    main_trust_decisions.record_exit_decision_safe(
        ledger_ctx, "MSFT", "SELL", "EXECUTED", "stop-loss", 10000.0, 50.0,
    )

    assert calls == ["MSFT"]
    assert captured["model_outputs"]["finbert"]["metadata"]["headlines"] == ["Exit-path headline"]


def test_record_executed_preserves_finbert_headlines_when_xgb_drivers_rebuilds_metadata(
    conn, reference_chain, monkeypatch,
):
    """record_executed() rebuilds model_outputs['xgboost']['metadata'] when
    xgb_drivers is supplied (existing behavior), but must never touch
    model_outputs['finbert'] -- its metadata.headlines, set once at __init__
    time, must survive into the write unchanged."""
    monkeypatch.setattr(
        main_trust_decisions, "get_cached_headlines", lambda ticker: ["Survives rebuild"],
    )

    captured = {}

    def _fake_record_decision_safe(trust_conn, candidate_event_id, deployment_manifest_id,
                                    asset, action, event_type, portfolio_snapshot, market_context,
                                    model_outputs, risk_checks, final_confidence, intent,
                                    data_completeness, risk=None):
        captured["model_outputs"] = model_outputs

    monkeypatch.setattr(main_trust_decisions, "record_decision_safe", _fake_record_decision_safe)

    recorder = main_trust_decisions.EntryDecisionRecorder(
        conn, reference_chain["candidate_event_id"], reference_chain["manifest_id"],
        "AAPL", 0.7, 0.6, 0.2, 0.5, "bull", 10000.0, 5000.0, None,
    )
    recorder.record_executed(
        notional=1000.0, fill_price=100.0, fill_shares=10.0,
        stop_pct=0.05, tp_target_pct=0.10, rr_ratio=2.0,
        xgb_drivers=[("rsi", 0.12)],
    )

    assert captured["model_outputs"]["xgboost"]["metadata"] == {
        "shap_drivers": [{"feature": "rsi", "shap_value": 0.12}],
    }
    assert captured["model_outputs"]["finbert"]["metadata"]["headlines"] == ["Survives rebuild"]
