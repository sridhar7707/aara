"""End-to-end integration tests for Phase 1A Sprint 3: proves _handle_entry
(bot/_main_cycle.py) and _handle_exits (bot/_main_positions.py) actually
write decision_events rows when wired to a real ledger connection -- not
just that they tolerate ledger_ctx=None (already covered by the fact that
every existing tests/test_main.py test still passes unmodified)."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bot._main_db as main_db  # noqa: E402
import ledger.db as ledger_db  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
from bot._main_cycle import _handle_entry, EntryContext  # noqa: E402
from bot._main_positions import _handle_exits  # noqa: E402
from bot._main_trust_decisions import ExitLedgerContext  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def trades_db():
    con = main_db.init_db(":memory:")
    yield con
    con.close()


@pytest.fixture
def ledger_conn():
    con = ledger_db.init_db(":memory:")
    yield con
    con.close()


@pytest.fixture
def chain(ledger_conn):
    ledger_conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    ledger_conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    ledger_conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    ledger_conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    ledger_conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    ledger_conn.commit()
    row = candidates.record_candidate_evaluation_if_concluded(
        ledger_conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _minimal_entry_ctx(ledger_conn, chain, **overrides) -> EntryContext:
    defaults = dict(
        positions={}, buy_order_syms=set(), earnings_map={}, bars_map={},
        sig_bars=__import__("pandas").DataFrame(), latest={}, current_price=100.0, current_atr=1.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, available_cash=5000.0,
        xgb_prob=0.7, lstm_prob=0.6, macro_score=0.5, macro_cap=1.0,
        macro_halt=False, spy_5bar_return=None, vs_spy_today=0.0, sentiments={},
        ensemble_size=0.12, xgb=None, stop_fired_today=set(), volume_ratio=1.0,
        tradeable_capital=5000.0,
        trust_conn=ledger_conn, candidate_event_id=chain["candidate_event_id"],
        deployment_manifest_id=chain["manifest_id"],
    )
    defaults.update(overrides)
    return EntryContext(**defaults)


class _AlwaysApproveRisk:
    def approve_buy(self, *args, **kwargs):
        return True


class _FakeFillClient:
    def buy(self, symbol, notional, limit_price=None):
        return {"order_id": "ord-1"}

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 10.0

    def get_fill_price(self, order_id):
        return 100.0


class _FakeXgb:
    def explain(self, row):
        return [("rsi", 0.1)]


def _latest_decision(conn, asset):
    row = conn.execute(
        "SELECT decision_id, action, event_type, risk_checks, model_outputs FROM decision_events "
        "WHERE asset=? ORDER BY sequence_number DESC LIMIT 1", (asset,),
    ).fetchone()
    return row


def test_handle_entry_gate_rejection_writes_qualified_rejection(trades_db, ledger_conn, chain):
    from database.services.decision_service import create_decision
    did = create_decision(trades_db, "AAPL", 100.0, 10000.0)
    ctx = _minimal_entry_ctx(ledger_conn, chain, macro_halt=True, decision_id=did)

    _handle_entry(trades_db, client=None, risk=None, symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    _, action, event_type, risk_checks, model_outputs = row
    assert action == "REJECT"
    assert event_type == "QUALIFIED_REJECTION"
    trace = json.loads(risk_checks)["gate_trace"]
    assert trace[-1]["gate"] == "vix_halt"
    assert trace[-1]["passed"] is False
    outputs = json.loads(model_outputs)
    assert set(outputs.keys()) == {"xgboost", "lstm", "finbert"}


def test_handle_entry_executed_buy_writes_executed_decision(trades_db, ledger_conn, chain):
    from database.services.decision_service import create_decision
    did = create_decision(trades_db, "AAPL", 100.0, 10000.0)
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, decision_id=did, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    _, action, event_type, risk_checks, model_outputs = row
    assert action == "BUY"
    assert event_type == "EXECUTED"
    trace_payload = json.loads(risk_checks)
    assert trace_payload["notional"] > 0
    assert trace_payload["fill_price"] == 100.0
    # Regression: record_executed() used to reuse the __init__-time
    # model_outputs, which never has SHAP drivers (computing them for
    # every rejected gate would waste SHAP calls) -- an EXECUTED buy must
    # carry the real drivers computed just before the fill, not an empty list.
    outputs = json.loads(model_outputs)
    assert outputs["xgboost"]["metadata"]["shap_drivers"] == [{"feature": "rsi", "shap_value": 0.1}]


def test_handle_entry_correlation_gate_carries_specific_reason(trades_db, ledger_conn, chain):
    """Regression: the correlation gate used to write a generic placeholder
    ('correlated with an existing held position') to the ledger instead of
    the specific coefficient/symbol _passes_correlation_gate already
    computes -- every other gate carries its real computed detail."""
    import pandas as pd
    from database.services.decision_service import create_decision
    from bot._main_positions import BarData

    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    aapl_bars = pd.DataFrame({"close": [100 + i for i in range(30)]}, index=dates)
    msft_bars = pd.DataFrame({"close": [200 + i for i in range(30)]}, index=dates)  # perfectly correlated

    class _FakePosition:
        market_value = 1000.0

    did = create_decision(trades_db, "AAPL", 100.0, 10000.0)
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, decision_id=did,
        positions={"MSFT": _FakePosition()},
        bars_map={"AAPL": BarData(pd.DataFrame(), aapl_bars), "MSFT": BarData(pd.DataFrame(), msft_bars)},
    )

    _handle_entry(trades_db, client=None, risk=None, symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    trace = json.loads(row[3])["gate_trace"]
    assert trace[-1]["gate"] == "correlation"
    assert "correlation with held MSFT" in trace[-1]["detail"]


def test_bot_main_passes_ledger_ctx_to_handle_exits():
    """Regression test for a real bug caught by code review: bot/main.py's
    production call to _handle_exits() previously omitted ledger_ctx
    entirely, so every exit-side write (7 branches, all individually unit-
    and integration-tested) was silently dead in production. A full
    bot/main.py::run() mock is disproportionate (needs a mocked Alpaca
    account and full market-data pipeline) -- this cheap source check
    guards against the same class of regression recurring."""
    import inspect
    import bot.main as main_mod

    source = inspect.getsource(main_mod.run)
    call_start = source.index("_handle_exits(")
    call_text = source[call_start:source.index("\n\n", call_start)]
    assert "ledger_ctx=" in call_text


def test_handle_entry_order_never_fills_writes_qualified_rejection(trades_db, ledger_conn, chain):
    from database.services.decision_service import create_decision

    class _NoBuyClient:
        def buy(self, symbol, notional, limit_price=None):
            return None

    did = create_decision(trades_db, "AAPL", 100.0, 10000.0)
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, decision_id=did, current_atr=2.0,
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_NoBuyClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "REJECT"
    assert row[2] == "QUALIFIED_REJECTION"


class _NeverExitRisk:
    def check_stop_loss(self, *a, **k):
        return False

    def check_trailing_stop(self, *a, **k):
        return False

    def check_pdt(self, *a, **k):
        return True


class _FakePosition:
    def __init__(self, avg_entry_price, qty, unrealized_plpc):
        self.avg_entry_price = avg_entry_price
        self.qty = qty
        self.unrealized_plpc = unrealized_plpc


def _exit_ledger_ctx(ledger_conn, chain):
    return ExitLedgerContext(
        trust_conn=ledger_conn, candidate_event_id=chain["candidate_event_id"],
        deployment_manifest_id=chain["manifest_id"], xgb_prob=0.6, lstm_prob=0.55,
        sentiment=0.1, macro_score=0.5,
    )


def test_handle_exits_hold_writes_hold_decision(trades_db, ledger_conn, chain):
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    _handle_exits(
        trades_db, client=None, risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=100.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=0, pdt_exempt=True,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )
    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "HOLD"
    assert row[2] == "QUALIFIED_REJECTION"


def test_handle_exits_ensemble_sell_writes_executed_sell(trades_db, ledger_conn, chain):
    from database.services.decision_service import create_decision, mark_executed
    from bot._main_db import log_trade

    class _FakeSellClient:
        def sell(self, symbol, qty, limit_price=None):
            return {"order_id": "ord-2"}

        def wait_for_fill(self, order_id, timeout_secs=12):
            return 1.0

    did = create_decision(trades_db, "AAPL", 100.0, 10000.0)
    trade_id = log_trade(trades_db, "AAPL", "BUY", 1.0, 100.0, 100.0, "TRENDING_UP", 10000.0, 0.0)
    mark_executed(trades_db, did, trade_id=trade_id)

    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    _handle_exits(
        trades_db, client=_FakeSellClient(), risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=110.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=2, pdt_exempt=True,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )
    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "SELL"
    assert row[2] == "EXECUTED"


def test_handle_exits_none_ledger_ctx_is_noop(trades_db):
    """No ledger_ctx passed -- must behave exactly as before Sprint 3."""
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    result = _handle_exits(
        trades_db, client=None, risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=100.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=0, pdt_exempt=True,
        stop_fired_today=set(),
    )
    assert result is True  # no exception, no ledger write attempted
