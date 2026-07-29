"""Tests for bot/trust_ledger/constitution.py (Phase 1A constitution
enforcement logging, phase1a_requirements.md Section 13a). Fixture pattern
mirrors tests/phase1a/test_decision_capture.py."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.constitution as constitution  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402

_ALL_RULE_IDS = {"rule_1", "rule_2", "rule_3", "rule_4", "rule_5", "rule_6"}


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


def _write_decision(conn, reference_chain, action="BUY", event_type="EXECUTED",
                     portfolio_value=10000.0, final_confidence=0.65, intent=None):
    return decisions.write_decision_event(
        conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset="AAPL", action=action, event_type=event_type,
        portfolio_snapshot={"portfolio_value": portfolio_value},
        market_context={"regime": "bull"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=final_confidence,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=intent if intent is not None else decisions.build_intent(action),
        data_completeness=decisions.build_data_completeness(),
    )


# ── check_and_log: shape ───────────────────────────────────────────────────

def test_check_and_log_writes_one_row_per_rule(conn, reference_chain):
    decision_row = _write_decision(conn, reference_chain)
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    assert {r["rule_id"] for r in rows} == _ALL_RULE_IDS
    stored_count = conn.execute(
        "SELECT COUNT(*) FROM constitution_enforcement_events WHERE decision_id=?",
        (decision_row["decision_id"],),
    ).fetchone()[0]
    assert stored_count == 6


def test_check_and_log_rows_are_hash_chained(conn, reference_chain):
    decision_row = _write_decision(conn, reference_chain)
    constitution.check_and_log(conn, decision_row, risk=None)
    breaks = ledger_svc.verify_chain(conn, "constitution_enforcement_events")
    assert breaks == []


def test_check_and_log_works_without_a_risk_manager(conn, reference_chain):
    """risk=None (e.g. a caller not wired to the live pipeline) must not raise --
    same best-effort contract as everywhere else in the Trust Ledger."""
    decision_row = _write_decision(conn, reference_chain)
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    assert all(r["check_result"] in ("PASS", "FAIL", "ESCALATED") for r in rows)


def test_table_is_append_only(conn, reference_chain):
    import sqlite3
    decision_row = _write_decision(conn, reference_chain)
    constitution.check_and_log(conn, decision_row, risk=None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE constitution_enforcement_events SET check_result='FAIL' WHERE sequence_number=1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM constitution_enforcement_events WHERE sequence_number=1")


# ── Rule 1: Risk Governor Authority ─────────────────────────────────────────

def test_rule_1_passes_when_risk_normal(conn, reference_chain):
    risk = RiskManager()
    decision_row = _write_decision(conn, reference_chain, action="BUY")
    rows = constitution.check_and_log(conn, decision_row, risk=risk)
    rule1 = next(r for r in rows if r["rule_id"] == "rule_1")
    assert rule1["check_result"] == "PASS"


def test_rule_1_escalates_buy_when_defensive(conn, reference_chain):
    risk = RiskManager()
    risk.halted = True
    decision_row = _write_decision(conn, reference_chain, action="BUY")
    rows = constitution.check_and_log(conn, decision_row, risk=risk)
    rule1 = next(r for r in rows if r["rule_id"] == "rule_1")
    assert rule1["check_result"] == "ESCALATED"
    assert rule1["action_taken"] == "advisory_only"


def test_rule_1_does_not_escalate_sell_when_defensive(conn, reference_chain):
    """Constitution Rule 1 only gates BUY/INCREASE_SIZE, not exits."""
    risk = RiskManager()
    risk.halted = True
    decision_row = _write_decision(conn, reference_chain, action="SELL")
    rows = constitution.check_and_log(conn, decision_row, risk=risk)
    rule1 = next(r for r in rows if r["rule_id"] == "rule_1")
    assert rule1["check_result"] == "PASS"


def test_rule_1_does_not_mutate_risk_manager_state(conn, reference_chain):
    """Regression guard: constitution checks must be read-only against the
    live RiskManager -- calling a mutating method here (e.g. check_daily_loss)
    could set risk.halted mid-cycle before approve_buy() would have,
    changing which later symbols get blocked. See constitution.py's
    module docstring."""
    risk = RiskManager(daily_start_value=10000.0)
    assert risk.halted is False
    decision_row = _write_decision(conn, reference_chain, portfolio_value=8000.0)  # -20%, breaches daily loss
    constitution.check_and_log(conn, decision_row, risk=risk)
    assert risk.halted is False


# ── Rule 3: Trade Structure Requirement ─────────────────────────────────────

def test_rule_3_escalates_when_thesis_fields_missing(conn, reference_chain):
    """Known, documented gap: decisions.build_intent() doesn't populate
    thesis/invalidation_point/expected_return_basis_points yet, so this is
    expected to escalate today -- a real signal, not a checker bug."""
    decision_row = _write_decision(conn, reference_chain, action="BUY")
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule3 = next(r for r in rows if r["rule_id"] == "rule_3")
    assert rule3["check_result"] == "ESCALATED"
    assert "intent.thesis" in rule3["reason"]


def test_rule_3_passes_when_all_fields_present(conn, reference_chain):
    intent = {
        "primary_intent": "OPPORTUNITY_ENTRY", "contributing_modules": [],
        "thesis": "undervalued financial sector entry",
        "invalidation_point": "close below $95",
        "expected_return_basis_points": 250,
    }
    decision_row = _write_decision(conn, reference_chain, action="BUY", intent=intent)
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule3 = next(r for r in rows if r["rule_id"] == "rule_3")
    assert rule3["check_result"] == "PASS"


def test_rule_3_not_applicable_to_hold_or_reject(conn, reference_chain):
    decision_row = _write_decision(conn, reference_chain, action="REJECT", event_type="QUALIFIED_REJECTION")
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule3 = next(r for r in rows if r["rule_id"] == "rule_3")
    assert rule3["check_result"] == "PASS"


def test_rule_3_sell_does_not_require_a_fresh_thesis(conn, reference_chain):
    """A SELL is a RISK_MANAGEMENT_EXIT -- the original BUY's invalidation
    point firing, not a new position -- so it must not be held to the same
    thesis/invalidation_point/expected_return bar as a BUY. Only the
    confidence floor applies."""
    decision_row = _write_decision(conn, reference_chain, action="SELL", intent=decisions.build_intent("SELL"))
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule3 = next(r for r in rows if r["rule_id"] == "rule_3")
    assert rule3["check_result"] == "PASS"


def test_rule_3_sell_still_escalates_below_confidence_floor(conn, reference_chain):
    decision_row = _write_decision(
        conn, reference_chain, action="SELL", intent=decisions.build_intent("SELL"), final_confidence=0.3,
    )
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule3 = next(r for r in rows if r["rule_id"] == "rule_3")
    assert rule3["check_result"] == "ESCALATED"


# ── Rule 4: Portfolio Drawdown Circuit Breaker ──────────────────────────────

def test_rule_4_passes_with_no_drawdown(conn, reference_chain):
    risk = RiskManager(portfolio_high=10000.0)
    decision_row = _write_decision(conn, reference_chain, portfolio_value=10000.0)
    rows = constitution.check_and_log(conn, decision_row, risk=risk)
    rule4 = next(r for r in rows if r["rule_id"] == "rule_4")
    assert rule4["check_result"] == "PASS"


def test_rule_4_escalates_at_warning_drawdown(conn, reference_chain):
    risk = RiskManager(portfolio_high=10000.0)
    decision_row = _write_decision(conn, reference_chain, portfolio_value=8400.0)  # -16%
    rows = constitution.check_and_log(conn, decision_row, risk=risk)
    rule4 = next(r for r in rows if r["rule_id"] == "rule_4")
    assert rule4["check_result"] == "ESCALATED"


def test_rule_4_escalates_at_critical_drawdown(conn, reference_chain):
    risk = RiskManager(portfolio_high=10000.0)
    decision_row = _write_decision(conn, reference_chain, portfolio_value=7000.0)  # -30%
    rows = constitution.check_and_log(conn, decision_row, risk=risk)
    rule4 = next(r for r in rows if r["rule_id"] == "rule_4")
    assert rule4["check_result"] == "ESCALATED"
    assert "critical" in rule4["reason"]


# ── Rule 5: Approval Escalation for First N Trades ──────────────────────────

def test_rule_5_escalates_before_autonomy_threshold(conn, reference_chain):
    decision_row = _write_decision(conn, reference_chain, action="BUY")
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule5 = next(r for r in rows if r["rule_id"] == "rule_5")
    assert rule5["check_result"] == "ESCALATED"


def test_rule_5_passes_after_autonomy_threshold_with_high_confidence(conn, reference_chain):
    """Seeds AUTONOMY_TRADE_COUNT prior EXECUTED decisions directly via
    decisions.write_decision_event (bypassing check_fingerprint's open-position
    dedup guard, which record_decision_safe would otherwise apply)."""
    for _ in range(constitution.AUTONOMY_TRADE_COUNT):
        _write_decision(conn, reference_chain, action="BUY", final_confidence=0.9)
    decision_row = _write_decision(conn, reference_chain, action="BUY", final_confidence=0.9)
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule5 = next(r for r in rows if r["rule_id"] == "rule_5")
    assert rule5["check_result"] == "PASS"


def test_rule_5_not_applicable_to_hold_or_reject(conn, reference_chain):
    decision_row = _write_decision(conn, reference_chain, action="HOLD", event_type="QUALIFIED_REJECTION")
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule5 = next(r for r in rows if r["rule_id"] == "rule_5")
    assert rule5["check_result"] == "PASS"


# ── Rule 6: Override Prevention ─────────────────────────────────────────────

def test_rule_6_always_passes_citing_db_enforcement(conn, reference_chain):
    decision_row = _write_decision(conn, reference_chain)
    rows = constitution.check_and_log(conn, decision_row, risk=None)
    rule6 = next(r for r in rows if r["rule_id"] == "rule_6")
    assert rule6["check_result"] == "PASS"
    assert "append-only" in rule6["reason"]


# ── record_decision_safe integration ────────────────────────────────────────

def test_record_decision_safe_logs_constitution_rows(conn, reference_chain):
    from bot._main_trust_decisions import record_decision_safe

    record_decision_safe(
        conn, reference_chain["candidate_event_id"], reference_chain["manifest_id"],
        "AAPL", "BUY", "EXECUTED",
        {"portfolio_value": 10000.0}, {"regime": "bull"}, build_model_outputs(0.7, 0.6, 0.2),
        {"gates": []}, 0.65, decisions.build_intent("BUY"), decisions.build_data_completeness(),
        risk=RiskManager(),
    )
    decision_id = conn.execute("SELECT decision_id FROM decision_events WHERE asset='AAPL'").fetchone()[0]
    count = conn.execute(
        "SELECT COUNT(*) FROM constitution_enforcement_events WHERE decision_id=?", (decision_id,)
    ).fetchone()[0]
    assert count == 6


def test_record_decision_safe_still_writes_decision_if_constitution_check_fails(conn, reference_chain, monkeypatch):
    """Best-effort contract: a constitution-check failure must never block or
    roll back the primary decision_events write."""
    from bot._main_trust_decisions import record_decision_safe

    def _boom(*a, **k):
        raise RuntimeError("simulated constitution check failure")

    monkeypatch.setattr(constitution, "check_and_log", _boom)
    record_decision_safe(
        conn, reference_chain["candidate_event_id"], reference_chain["manifest_id"],
        "AAPL", "BUY", "EXECUTED",
        {"portfolio_value": 10000.0}, {"regime": "bull"}, build_model_outputs(0.7, 0.6, 0.2),
        {"gates": []}, 0.65, decisions.build_intent("BUY"), decisions.build_data_completeness(),
        risk=RiskManager(),
    )
    count = conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0]
    assert count == 1
