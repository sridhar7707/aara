"""Tests for dashboard.components.decision_quality.

Reads the Trust Ledger (decision_events/decision_outcome_events), not the
retired decision_log (phase0_decisions.md #17/#18) -- fixtures build a
minimal ledger reference chain, same pattern as tests/phase1a/.
"""
import pytest

import ledger.db as ledger_db
import bot.trust_ledger.candidates as candidates
import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
import bot.trust_ledger.connection as ledger_connection
from bot.strategy.model_output_adapter import build_model_outputs
import dashboard.data as ddata
from bot._main_db import init_db
import dashboard.components.decision_quality as dq


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def dash_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dq_test.db")
    init_db(db_path)
    monkeypatch.setattr(ddata, "DB_PATH", db_path)
    monkeypatch.setattr(dq, "_get_sym_hist", lambda symbol: None)  # no network in tests

    ledger_path = str(tmp_path / "ledger_test.db")
    monkeypatch.setattr(ledger_connection, "DEFAULT_LEDGER_DB_PATH", ledger_path)

    conn = ledger_db.init_db(ledger_path)
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
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-01T00:00:00Z')"
    )
    conn.commit()
    import ledger.ledger as ledger_svc
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-01T00:00:00Z",
    })
    conn.close()
    return None


def _completed_decision(symbol, price, pnl_pct, day="2026-07-01"):
    """price is unused (kept for parity with the old decision_log-based
    signature) -- the ledger doesn't need a fill price to classify win/loss,
    only decision_outcome_events.net_return's sign."""
    conn = ledger_db.get_conn(ledger_connection.DEFAULT_LEDGER_DB_PATH)
    try:
        cand = candidates.record_candidate_evaluation_if_concluded(
            conn, symbol, day, {}, data_available=True, required_models_available=True,
            evaluation_completed=True,
        )
        row = decisions.write_decision_event(
            conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action="BUY",
            event_type="EXECUTED", portfolio_snapshot={"value": 10000.0}, market_context={},
            model_outputs=build_model_outputs(0.7, 0.6, 0.2), risk_checks={"gates": []},
            final_confidence=0.65, deployment_manifest_id="mani_v1",
            intent=decisions.build_intent("BUY"), data_completeness=decisions.build_data_completeness(),
            timestamp=f"{day}T10:00:00Z",
        )
        did = outcomes.write_decision_outcome_event(
            conn, symbol, row["decision_id"], f"{day}T15:00:00Z", pnl_pct, 3,
        )
        return did
    finally:
        conn.close()


def test_empty_state_when_no_completed_decisions(dash_db):
    html = dq.render_decision_quality_summary()
    assert "No completed decisions yet" in html


def test_counts_completed_decisions(dash_db):
    _completed_decision("AAPL", 100.0, 0.05)
    _completed_decision("MSFT", 200.0, -0.03)
    html = dq.render_decision_quality_summary()
    assert "Based on 2 completed decisions" in html


def test_excludes_decisions_without_known_outcome(dash_db):
    _completed_decision("AAPL", 100.0, 0.05)
    # BAC is executed but never gets an outcome event -- must not count
    conn = ledger_db.get_conn(ledger_connection.DEFAULT_LEDGER_DB_PATH)
    try:
        cand = candidates.record_candidate_evaluation_if_concluded(
            conn, "BAC", "2026-07-01", {}, data_available=True, required_models_available=True,
            evaluation_completed=True,
        )
        decisions.write_decision_event(
            conn, candidate_event_id=cand["candidate_event_id"], asset="BAC", action="BUY",
            event_type="EXECUTED", portfolio_snapshot={"value": 10000.0}, market_context={},
            model_outputs=build_model_outputs(0.7, 0.6, 0.2), risk_checks={"gates": []},
            final_confidence=0.65, deployment_manifest_id="mani_v1",
            intent=decisions.build_intent("BUY"), data_completeness=decisions.build_data_completeness(),
            timestamp="2026-07-01T10:00:00Z",
        )
    finally:
        conn.close()
    html = dq.render_decision_quality_summary()
    assert "Based on 1 completed decisions" in html


def test_trend_shows_early_evidence_below_minimum(dash_db):
    for i in range(3):  # below _MIN_FOR_TREND (6)
        _completed_decision(f"SYM{i}", 100.0, 0.05)
    html = dq.render_decision_quality_summary()
    assert "Early evidence" in html


def test_trend_shows_improving_when_second_half_wins_more(dash_db):
    for i in range(3):
        _completed_decision(f"LOSER{i}", 100.0, -0.05)  # first half: all losses
    for i in range(3):
        _completed_decision(f"WINNER{i}", 100.0, 0.05)  # second half: all wins
    html = dq.render_decision_quality_summary()
    assert "Improving" in html


def test_trend_shows_declining_when_second_half_loses_more(dash_db):
    for i in range(3):
        _completed_decision(f"WINNER{i}", 100.0, 0.05)
    for i in range(3):
        _completed_decision(f"LOSER{i}", 100.0, -0.05)
    html = dq.render_decision_quality_summary()
    assert "Declining" in html


def test_strength_hidden_when_no_sector_has_enough_decisions(dash_db):
    """Each symbol below _MIN_FOR_DIMENSION (3) per sector -> no claim made."""
    _completed_decision("AAPL", 100.0, 0.05)   # Tech
    _completed_decision("JPM", 100.0, 0.03)    # Finance
    html = dq.render_decision_quality_summary()
    assert "No sector stands out" in html
    assert "Strength:" not in html


def test_strength_shown_when_a_sector_has_enough_decisions(dash_db):
    for i in range(3):
        # AAPL/MSFT/NVDA are all Technology in SECTOR_MAP, all wins -> 100% WR
        _completed_decision(["AAPL", "MSFT", "NVDA"][i], 100.0, 0.05)
    html = dq.render_decision_quality_summary()
    assert "Strength:" in html


def test_sole_qualifying_sector_with_poor_win_rate_is_weakness_not_strength(dash_db):
    """The exact bug this caught: being the ONLY sector with enough decisions
    must not make it a "Strength" just by default. 1 win, 2 losses = 33% win
    rate is genuinely poor (below the 45% bar) — it should show as a
    Weakness, never mislabeled as a Strength."""
    _completed_decision("AAPL", 100.0, 0.05)    # Tech, win
    _completed_decision("MSFT", 100.0, -0.03)   # Tech, loss
    _completed_decision("NVDA", 100.0, -0.02)   # Tech, loss
    html = dq.render_decision_quality_summary()
    assert "Strength:" not in html
    assert "Weakness:" in html


def test_sole_qualifying_sector_with_middling_win_rate_shows_neither(dash_db):
    """A win rate that's neither clearly good (>=60%) nor clearly bad (<45%)
    — e.g. 50% — must not be forced into either bucket."""
    _completed_decision("AAPL", 100.0, 0.05)    # Tech, win
    _completed_decision("MSFT", 100.0, 0.04)    # Tech, win
    _completed_decision("NVDA", 100.0, -0.03)   # Tech, loss
    _completed_decision("AMD",  100.0, -0.02)   # Tech, loss
    html = dq.render_decision_quality_summary()
    assert "Strength:" not in html
    assert "Weakness:" not in html
    assert "No sector stands out" in html
