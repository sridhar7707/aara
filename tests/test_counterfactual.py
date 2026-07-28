"""Tests for dashboard.components.counterfactual (Phase 5 Step 12)."""
import pytest

import dashboard.data as data
from bot._main_db import init_db
from database.services.decision_service import create_decision, reject_decision
import dashboard.components.counterfactual as cf


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "counterfactual_test.db")
    con = init_db(db_path)
    monkeypatch.setattr(data, "DB_PATH", db_path)
    return con


def _rejected(con, symbol: str, gate_reason: str = "volume gate failed", rejected_by: str = "system"):
    did = create_decision(con, symbol=symbol, price_at_decision=100.0, portfolio_value_at_time=10000.0)
    reject_decision(con, did, rejected_by=rejected_by, reason=gate_reason)
    return did


def _fake_evaluate(forward_returns: dict):
    """Builds a fake evaluate_rejected_decision(con, decision_id) that returns
    a canned forward_return per decision_id, sidestepping any real yfinance call."""
    def _fn(con, decision_id):
        if decision_id not in forward_returns:
            return {"decision_id": decision_id, "forward_return": None, "error": "window not yet complete"}
        return {"decision_id": decision_id, "forward_return": forward_returns[decision_id]}
    return _fn


def test_no_rejections_shows_progress(db):
    html = cf.render_counterfactual_analysis()
    assert "0 evaluated rejections so far" in html
    assert "Need 15 more" in html


def test_below_threshold_shows_progress(db, monkeypatch):
    ids = [_rejected(db, f"SYM{i}") for i in range(5)]
    monkeypatch.setattr(cf, "evaluate_rejected_decision", _fake_evaluate({i: 0.05 for i in ids}))
    html = cf.render_counterfactual_analysis()
    assert "5 evaluated rejections so far" in html
    assert "Need 10 more" in html


def test_still_pending_windows_dont_count_toward_threshold(db, monkeypatch):
    """A decision with no entry in the fake evaluate map simulates 'window not
    yet complete' -- must not be silently counted as evaluated."""
    ids = [_rejected(db, f"SYM{i}") for i in range(20)]
    evaluated_ids = ids[:10]  # only half have a closed window
    monkeypatch.setattr(cf, "evaluate_rejected_decision", _fake_evaluate({i: 0.05 for i in evaluated_ids}))
    html = cf.render_counterfactual_analysis()
    assert "10 evaluated rejections so far" in html


def test_above_threshold_shows_stats(db, monkeypatch):
    ids = [_rejected(db, f"SYM{i}") for i in range(20)]
    # 12 would have won (positive return), 8 would have lost
    forward_returns = {i: (0.05 if idx < 12 else -0.03) for idx, i in enumerate(ids)}
    monkeypatch.setattr(cf, "evaluate_rejected_decision", _fake_evaluate(forward_returns))
    html = cf.render_counterfactual_analysis()
    assert "Evaluated Rejections" in html
    assert "Would-Have Won" in html
    assert "60%" in html  # 12/20


def test_gate_reason_breakdown_identifies_worst_and_best_gates(db, monkeypatch):
    # "too_strict_gate" blocks 5 symbols that all would have won (bad gate, 100%)
    # "good_gate" blocks 5 symbols that all would have lost (correctly avoided losers, 0%)
    # "filler_gate" sits strictly in between (60%) so neither extreme ties with it
    worst_ids  = [_rejected(db, f"WORST{i}", gate_reason="too_strict_gate") for i in range(5)]
    best_ids   = [_rejected(db, f"BEST{i}", gate_reason="good_gate") for i in range(5)]
    filler_ids = [_rejected(db, f"FILL{i}", gate_reason="filler_gate") for i in range(5)]
    forward_returns = {}
    forward_returns.update({i: 0.10 for i in worst_ids})
    forward_returns.update({i: -0.05 for i in best_ids})
    forward_returns.update({i: (0.01 if idx < 3 else -0.01) for idx, i in enumerate(filler_ids)})
    monkeypatch.setattr(cf, "evaluate_rejected_decision", _fake_evaluate(forward_returns))
    html = cf.render_counterfactual_analysis()
    assert "too_strict_gate" in html
    assert "good_gate" in html


def test_no_gate_breakdown_when_no_group_has_enough_samples(db, monkeypatch):
    # 15 different gate reasons, one decision each -- none reaches _MIN_PER_GATE_REASON
    ids = [_rejected(db, f"SYM{i}", gate_reason=f"gate_{i}") for i in range(15)]
    monkeypatch.setattr(cf, "evaluate_rejected_decision", _fake_evaluate({i: 0.02 for i in ids}))
    html = cf.render_counterfactual_analysis()
    assert "No single gate reason stands out yet" in html
