"""Tests for bot/trust_ledger/risk.py (Phase 1A Sprint 4)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import bot._main_db as main_db  # noqa: E402
import bot.trust_ledger.risk as risk_mod  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402
from config import MAX_POSITION_PCT  # noqa: E402


@pytest.fixture
def trades_conn():
    con = main_db.init_db(":memory:")
    yield con
    con.close()


@pytest.fixture
def trust_conn():
    con = ledger_db.init_db(":memory:")
    yield con
    con.close()


class _FakeRisk:
    """Stub matching the subset of RiskManager's interface classify() uses,
    with each check independently controllable -- avoids needing to
    engineer real daily_start_value/portfolio_high state for every case."""
    def __init__(self, halted=False, daily_loss_ok=True, daily_loss_warning=False,
                 weekly_loss_ok=True, drawdown_ok=True):
        self.halted = halted
        self._daily_loss_ok = daily_loss_ok
        self._daily_loss_warning = daily_loss_warning
        self._weekly_loss_ok = weekly_loss_ok
        self._drawdown_ok = drawdown_ok

    def check_daily_loss(self, current_value):
        return self._daily_loss_ok

    def check_daily_loss_warning(self, current_value):
        return self._daily_loss_warning

    def check_weekly_loss(self, current_value):
        return self._weekly_loss_ok

    def check_portfolio_drawdown(self, current_value):
        return self._drawdown_ok


@pytest.mark.parametrize("kwargs,expected", [
    ({}, "NORMAL"),
    ({"halted": True}, "DEFENSIVE"),
    ({"daily_loss_ok": False}, "DEFENSIVE"),
    ({"drawdown_ok": False}, "DEFENSIVE"),
    ({"halted": True, "daily_loss_ok": False}, "DEFENSIVE"),  # both hard breaches -- still DEFENSIVE
    ({"daily_loss_warning": True}, "WARNING"),
    ({"weekly_loss_ok": False}, "WARNING"),
    ({"daily_loss_warning": True, "weekly_loss_ok": False}, "WARNING"),
    # DEFENSIVE takes priority over WARNING when both would independently apply
    ({"halted": True, "daily_loss_warning": True}, "DEFENSIVE"),
])
def test_classify_matrix(kwargs, expected):
    state, reason = risk_mod.classify(_FakeRisk(**kwargs), 10000.0)
    assert state == expected
    assert reason  # non-empty in every case


def test_recommend_position_size_scales_by_classification():
    sizing_base = 10000.0
    assert risk_mod.recommend_position_size(sizing_base, "NORMAL") == sizing_base * MAX_POSITION_PCT
    assert risk_mod.recommend_position_size(sizing_base, "WARNING") == sizing_base * MAX_POSITION_PCT * 0.5
    assert risk_mod.recommend_position_size(sizing_base, "DEFENSIVE") == 0.0


def test_first_ever_call_produces_observation_from_state(trades_conn, trust_conn):
    row = risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=500.0,
    )
    assert row["from_state"] == "OBSERVATION"
    assert row["to_state"] == "NORMAL"


def test_second_call_uses_prior_to_state_as_from_state(trades_conn, trust_conn):
    risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(daily_loss_warning=True), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=0.0,
    )
    second = risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=0.0,
    )
    assert second["from_state"] == "WARNING"
    assert second["to_state"] == "NORMAL"


def test_persisted_state_survives_reload(trades_conn, trust_conn):
    """Simulates a process restart: state is read back from risk_state,
    not from any in-memory value, matching RiskSnapshot's own load/save
    pattern (bot/db/risk_state.py)."""
    risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(halted=True), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=0.0,
    )
    reloaded = risk_mod._get_last_state(trades_conn)
    assert reloaded == "DEFENSIVE"


def test_actual_position_size_matches_cycle_deployed_notional(trades_conn, trust_conn):
    row = risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=1234.56,
    )
    assert row["actual_position_size"] == 1234.56


def test_record_risk_evaluation_writes_to_ledger(trades_conn, trust_conn):
    risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=0.0,
    )
    count = trust_conn.execute("SELECT COUNT(*) FROM risk_evaluation_events").fetchone()[0]
    assert count == 1


def test_record_risk_evaluation_trigger_reason_is_specific(trades_conn, trust_conn):
    """Regression: trigger_reason used to be a generic 'cycle reassessment
    (halted=...)' string regardless of why WARNING/DEFENSIVE was reached --
    an auditor couldn't tell which limit was breached from the ledger alone."""
    row = risk_mod.record_risk_evaluation(
        trades_conn, trust_conn, _FakeRisk(drawdown_ok=False), current_value=10000.0,
        sizing_base=10000.0, cycle_deployed_notional=0.0,
    )
    assert row["trigger_reason"] == "portfolio drawdown limit breached"


def test_classify_with_real_risk_manager_normal_state():
    """Sanity check against the real RiskManager, not just the stub --
    a fresh RiskManager with no breaches classifies as NORMAL."""
    risk = RiskManager(daily_start_value=10000.0, weekly_start_value=10000.0, portfolio_high=10000.0)
    state, _ = risk_mod.classify(risk, 10000.0)
    assert state == "NORMAL"


def test_classify_with_real_risk_manager_defensive_on_daily_loss():
    risk = RiskManager(daily_start_value=10000.0, weekly_start_value=10000.0, portfolio_high=10000.0)
    state, reason = risk_mod.classify(risk, 9000.0)  # -10% daily, breaches DAILY_LOSS_LIMIT_PCT default
    assert state == "DEFENSIVE"
    assert "daily loss" in reason


def test_classify_reason_distinguishes_defensive_causes():
    assert risk_mod.classify(_FakeRisk(halted=True), 10000.0)[1] == "risk.halted is set"
    assert risk_mod.classify(_FakeRisk(daily_loss_ok=False), 10000.0)[1] == "daily loss limit breached"
    assert risk_mod.classify(_FakeRisk(drawdown_ok=False), 10000.0)[1] == "portfolio drawdown limit breached"


def test_bot_main_calls_record_risk_evaluation_safe():
    """Structural regression guard, same rationale as the Sprint 3 fix for
    _handle_exits: a call site silently missing/never wired is invisible to
    every unit test that exercises the ledger function directly. A full
    bot/main.py::run() mock is disproportionate to set up here too."""
    import inspect
    import bot.main as main_mod

    source = inspect.getsource(main_mod.run)
    assert "record_risk_evaluation_safe(" in source
