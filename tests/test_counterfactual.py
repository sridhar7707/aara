"""Tests for dashboard.components.counterfactual (Phase 5 Step 12).

Reads the Trust Ledger (decision_events), not the retired decision_log
(phase0_decisions.md #17/#18) -- fixtures build a minimal ledger reference
chain, same pattern as tests/phase1a/.
"""
import pytest

import ledger.db as ledger_db
import ledger.ledger as ledger_svc
import bot.trust_ledger.candidates as candidates
import bot.trust_ledger.connection as ledger_connection
import bot.trust_ledger.decisions as decisions
from bot.strategy.model_output_adapter import build_model_outputs
import dashboard.components.counterfactual as cf

_next_symbol_id = [0]


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def db(tmp_path, monkeypatch):
    ledger_path = str(tmp_path / "counterfactual_test.db")
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
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-01T00:00:00Z",
    })
    conn.close()
    return None


def _rejected(symbol: str, gate_reason: str = "volume gate failed", day: str = "2026-07-01") -> str:
    conn = ledger_db.get_conn(ledger_connection.DEFAULT_LEDGER_DB_PATH)
    try:
        cand = candidates.record_candidate_evaluation_if_concluded(
            conn, symbol, day, {}, data_available=True, required_models_available=True,
            evaluation_completed=True,
        )
        row = decisions.write_decision_event(
            conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action="REJECT",
            event_type="QUALIFIED_REJECTION", portfolio_snapshot={"value": 10000.0}, market_context={},
            model_outputs=build_model_outputs(0.7, 0.6, 0.2),
            risk_checks={"gate_trace": [{"gate": gate_reason, "passed": False, "detail": gate_reason}]},
            final_confidence=0.65, deployment_manifest_id="mani_v1",
            intent=decisions.build_intent("REJECT"), data_completeness=decisions.build_data_completeness(),
            timestamp=f"{day}T10:00:00Z",
        )
        return row["decision_id"]
    finally:
        conn.close()


def _fake_evaluate(forward_returns_by_symbol: dict):
    """Builds a fake _evaluate_rejection(symbol, decision_date) that returns a
    canned forward_return per symbol, sidestepping any real yfinance call."""
    def _fn(symbol, decision_date):
        if symbol not in forward_returns_by_symbol:
            return {"forward_return": None}
        return {"forward_return": forward_returns_by_symbol[symbol]}
    return _fn


def test_no_rejections_shows_progress(db):
    html = cf.render_counterfactual_analysis()
    assert "0 evaluated rejections so far" in html
    assert "Need 15 more" in html


def test_below_threshold_shows_progress(db, monkeypatch):
    symbols = [f"SYM{i}" for i in range(5)]
    for s in symbols:
        _rejected(s)
    monkeypatch.setattr(cf, "_evaluate_rejection", _fake_evaluate({s: 0.05 for s in symbols}))
    html = cf.render_counterfactual_analysis()
    assert "5 evaluated rejections so far" in html
    assert "Need 10 more" in html


def test_still_pending_windows_dont_count_toward_threshold(db, monkeypatch):
    """A symbol with no entry in the fake evaluate map simulates 'window not
    yet complete' -- must not be silently counted as evaluated."""
    symbols = [f"SYM{i}" for i in range(20)]
    for s in symbols:
        _rejected(s)
    evaluated = symbols[:10]  # only half have a closed window
    monkeypatch.setattr(cf, "_evaluate_rejection", _fake_evaluate({s: 0.05 for s in evaluated}))
    html = cf.render_counterfactual_analysis()
    assert "10 evaluated rejections so far" in html


def test_above_threshold_shows_stats(db, monkeypatch):
    symbols = [f"SYM{i}" for i in range(20)]
    for s in symbols:
        _rejected(s)
    # 12 would have won (positive return), 8 would have lost
    forward_returns = {s: (0.05 if idx < 12 else -0.03) for idx, s in enumerate(symbols)}
    monkeypatch.setattr(cf, "_evaluate_rejection", _fake_evaluate(forward_returns))
    html = cf.render_counterfactual_analysis()
    assert "Evaluated Rejections" in html
    assert "Would-Have Won" in html
    assert "60%" in html  # 12/20


def test_gate_reason_breakdown_identifies_worst_and_best_gates(db, monkeypatch):
    # "too_strict_gate" blocks 5 symbols that all would have won (bad gate, 100%)
    # "good_gate" blocks 5 symbols that all would have lost (correctly avoided losers, 0%)
    # "filler_gate" sits strictly in between (60%) so neither extreme ties with it
    worst_syms  = [f"WORST{i}" for i in range(5)]
    best_syms   = [f"BEST{i}" for i in range(5)]
    filler_syms = [f"FILL{i}" for i in range(5)]
    for s in worst_syms:
        _rejected(s, gate_reason="too_strict_gate")
    for s in best_syms:
        _rejected(s, gate_reason="good_gate")
    for s in filler_syms:
        _rejected(s, gate_reason="filler_gate")
    forward_returns = {}
    forward_returns.update({s: 0.10 for s in worst_syms})
    forward_returns.update({s: -0.05 for s in best_syms})
    forward_returns.update({s: (0.01 if idx < 3 else -0.01) for idx, s in enumerate(filler_syms)})
    monkeypatch.setattr(cf, "_evaluate_rejection", _fake_evaluate(forward_returns))
    html = cf.render_counterfactual_analysis()
    assert "too_strict_gate" in html
    assert "good_gate" in html


def test_no_gate_breakdown_when_no_group_has_enough_samples(db, monkeypatch):
    # 15 different gate reasons, one decision each -- none reaches _MIN_PER_GATE_REASON
    symbols = [f"SYM{i}" for i in range(15)]
    for i, s in enumerate(symbols):
        _rejected(s, gate_reason=f"gate_{i}")
    monkeypatch.setattr(cf, "_evaluate_rejection", _fake_evaluate({s: 0.02 for s in symbols}))
    html = cf.render_counterfactual_analysis()
    assert "No single gate reason stands out yet" in html
