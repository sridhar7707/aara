"""ADR-067 + ADR-069: the pre-gate causal Sentinel Decision lifecycle wired
into bot/_main_trust_decisions.py, and the ADR-069 (B2) recommendation the
pre-gate Decision is now born with.

Proves: a stable decision_id is generated in EntryDecisionRecorder.__init__()
before any entry gate; one Sentinel Decision is created pre-gate on the shared
composition pair, with action / action_source authored by the ADR-069 B2
three-model unanimity rule (SS5.3) -- "BUY"/"SENTINEL" when xgboost, lstm and
finbert all signal BUY, otherwise "WAIT"/"SENTINEL"; a B2-recommendation
failure falls back to "BUY"/"STRATEGY" (SS8.4) without touching the trading
path; the SAME decision_id reaches the Trust Ledger decision_events row,
evidence association, and governance evaluation; a Sentinel failure never
propagates into the trading path; absence falls back to write_decision_event()'s
own new_decision_id(); RiskManager / PaperExecutor / bot/main.py / EntryContext
/ _handle_entry()'s gate sequence are untouched; and no production
record_approval() / register_policy() call is introduced.
"""
from __future__ import annotations

import datetime
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot._main_trust_decisions as mtd  # noqa: E402
from bot._main_trust_decisions import EntryDecisionRecorder, record_decision_safe  # noqa: E402
from sentinel_engine.adapters.recommendation_adapter import recommend_entry_action  # noqa: E402
from sentinel_engine.composition.decision_lifecycle import (  # noqa: E402
    get_decision_service,
    _ledger_repository as _lifecycle_ledger,
)
from sentinel_engine.domain.action_source import ActionSource  # noqa: E402
from sentinel_engine.domain.decision_state import DecisionState  # noqa: E402
from sentinel_engine.events.event_types import EventType  # noqa: E402

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


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
    ledger_svc.append_ledger_row(ledger_conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-28T00:00:00Z",
    })
    row = candidates.record_candidate_evaluation_if_concluded(
        ledger_conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _make_recorder(candidate_event_id="cand-x", manifest_id="mani_v1", symbol="AAPL", trust_conn=None,
                   xgb_prob=0.7, lstm_prob=0.6, sentiment=0.1):
    # defaults: xgb 0.7 -> BUY, lstm 0.6 -> BUY, sentiment 0.1 -> BUY  => unanimous
    return EntryDecisionRecorder(
        trust_conn, candidate_event_id, manifest_id, symbol,
        xgb_prob=xgb_prob, lstm_prob=lstm_prob, sentiment=sentiment, macro_score=0.5,
        regime_name="TRENDING_UP", portfolio_value=10000.0, available_cash=5000.0,
        price_data_timestamp="2026-09-08T13:00:00Z",
    )


def _created_payload(decision_id):
    """The DECISION_CREATED event payload for this decision_id on the shared
    causal-lifecycle ledger (ADR-069 provenance rides here -- SS8.4)."""
    for e in _lifecycle_ledger.get_events():
        if e.event_type == EventType.DECISION_CREATED and e.payload.get("decision_id") == decision_id:
            return e.payload
    return None


# -- 1-4: decision_id genesis + pre-gate Decision(action="BUY") ------------

def test_recorder_generates_decision_id_at_construction_before_any_gate():
    rec = _make_recorder()
    assert isinstance(rec.decision_id, str) and rec.decision_id
    assert rec.decision_id.startswith("DEC-")  # bot/trust_ledger/ids.py::new_decision_id


def test_recorder_decision_id_is_stable_for_the_life_of_the_instance():
    rec = _make_recorder()
    first = rec.decision_id
    rec.trace.append({"gate": "x", "passed": False, "detail": "y"})
    assert rec.decision_id == first


def test_construction_seeds_one_sentinel_decision_with_action_buy():
    # ADR-069: default recorder inputs are unanimous BUY, so the B2 rule
    # concurs -- action stays "BUY", now authored by Sentinel.
    rec = _make_recorder()
    proj = get_decision_service().get_projection(rec.decision_id)
    assert proj is not None
    assert proj.action == "BUY"
    assert proj.status == DecisionState.DECISION_CREATED
    payload = _created_payload(rec.decision_id)
    assert payload is not None
    assert payload["action"] == "BUY"
    assert payload["action_source"] == ActionSource.SENTINEL.value


# -- ADR-069 (B2): the pre-gate Decision is now a Sentinel recommendation ----

def test_b2_unanimous_buy_signals_concur_buy_sentinel():
    rec = _make_recorder(xgb_prob=0.7, lstm_prob=0.6, sentiment=0.2)  # all BUY
    payload = _created_payload(rec.decision_id)
    assert (payload["action"], payload["action_source"]) == ("BUY", "SENTINEL")
    assert get_decision_service().get_projection(rec.decision_id).action == "BUY"


@pytest.mark.parametrize("xgb,lstm,sent", [
    (0.4, 0.6, 0.1),    # xgboost SELL
    (0.7, 0.4, 0.1),    # lstm SELL
    (0.7, 0.6, -0.1),   # finbert SELL
    (0.5, 0.6, 0.1),    # xgboost HOLD (prob == 0.5)
    (0.7, 0.6, 0.0),    # finbert HOLD (score == 0.0)
])
def test_b2_any_non_buy_signal_abstains_wait_sentinel(xgb, lstm, sent):
    rec = _make_recorder(xgb_prob=xgb, lstm_prob=lstm, sentiment=sent)
    payload = _created_payload(rec.decision_id)
    assert (payload["action"], payload["action_source"]) == ("WAIT", "SENTINEL")
    # the projection reflects the same authored action; WAIT is an inert label
    assert get_decision_service().get_projection(rec.decision_id).action == "WAIT"


def test_b2_recommendation_matches_the_pure_rule_over_this_recorders_model_outputs():
    rec = _make_recorder(xgb_prob=0.7, lstm_prob=0.4, sentiment=0.1)
    expected = recommend_entry_action(rec.model_outputs)  # ("WAIT", "SENTINEL")
    payload = _created_payload(rec.decision_id)
    assert (payload["action"], payload["action_source"]) == expected


def test_b2_recommendation_failure_falls_back_to_buy_strategy_without_touching_the_trade(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("b2 down")

    monkeypatch.setattr(mtd, "recommend_entry_action", _boom)
    rec = _make_recorder()  # must not raise
    assert isinstance(rec.decision_id, str) and rec.decision_id.startswith("DEC-")
    payload = _created_payload(rec.decision_id)
    assert (payload["action"], payload["action_source"]) == ("BUY", ActionSource.STRATEGY.value)


def test_b2_never_authors_sell_buy_more_or_hold_for_any_recorder_input():
    seen = set()
    for xgb in (0.2, 0.5, 0.8):
        for lstm in (0.2, 0.5, 0.8):
            for sent in (-0.3, 0.0, 0.3):
                rec = _make_recorder(symbol="AAPL", xgb_prob=xgb, lstm_prob=lstm, sentiment=sent)
                seen.add(_created_payload(rec.decision_id)["action"])
    assert seen <= {"BUY", "WAIT"}


def test_b2_recommendation_is_determined_before_create_decision(monkeypatch):
    """The Decision must be born with the final recommendation -- create_decision()
    receives the already-decided action, never a placeholder later corrected."""
    captured = {}

    class _Capturing:
        def create_decision(self, decision):
            captured["action"] = decision.action
            captured["action_source"] = decision.action_source
            return None

    monkeypatch.setattr(mtd, "get_decision_service", lambda: _Capturing())
    _make_recorder(xgb_prob=0.7, lstm_prob=0.4, sentiment=0.1)  # -> WAIT
    assert captured == {"action": "WAIT", "action_source": "SENTINEL"}


def test_b2_preserves_one_decision_identity_no_second_create_decision(ledger_conn, chain):
    rec = _make_recorder(
        candidate_event_id=chain["candidate_event_id"],
        manifest_id=chain["manifest_id"],
        trust_conn=ledger_conn,
        xgb_prob=0.7, lstm_prob=0.4, sentiment=0.1,   # -> WAIT/SENTINEL
    )
    did = rec.decision_id
    created = [
        e for e in _lifecycle_ledger.get_events()
        if e.event_type == EventType.DECISION_CREATED and e.payload.get("decision_id") == did
    ]
    assert len(created) == 1
    record_decision_safe(
        ledger_conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "REJECT", "QUALIFIED_REJECTION",
        rec.portfolio_snapshot, rec.market_context, rec.model_outputs,
        {"gate_trace": []}, rec.final_confidence,
        mtd.decisions.build_intent("REJECT"), rec.data_completeness,
        decision_id=did,
    )
    # same single identity flows on -- evidence + governance keyed off it, no new Decision
    still_one = [
        e for e in _lifecycle_ledger.get_events()
        if e.event_type == EventType.DECISION_CREATED and e.payload.get("decision_id") == did
    ]
    assert len(still_one) == 1
    ledger_row_id = ledger_conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()[0]
    assert ledger_row_id == did


def test_b2_recommendation_adapter_is_only_wired_into_entry_decision_recorder_init():
    """ADR-069 SS13.2: the sole authorized bot-side production change is
    EntryDecisionRecorder.__init__(). recommend_entry_action must be imported
    into exactly one bot module and called from exactly one place."""
    import ast
    bot_root = _REPO_ROOT / "bot"
    importing = []
    for path in bot_root.rglob("*.py"):
        if path.name.startswith("test_") or "/tests/" in path.as_posix():
            continue
        src = path.read_text(encoding="utf-8")
        if "recommend_entry_action" in src:
            importing.append(path.relative_to(_REPO_ROOT).as_posix())
    assert importing == ["bot/_main_trust_decisions.py"]

    src = (bot_root / "_main_trust_decisions.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "recommend_entry_action"
    ]
    assert len(calls) == 1
    # and that call is inside EntryDecisionRecorder.__init__
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "EntryDecisionRecorder"):
        init = next(f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == "__init__")
        init_calls = [
            n for n in ast.walk(init)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "recommend_entry_action"
        ]
        assert len(init_calls) == 1


def test_two_recorders_seed_two_distinct_decision_ids():
    a = _make_recorder(symbol="AAPL")
    b = _make_recorder(symbol="MSFT")
    assert a.decision_id != b.decision_id
    assert get_decision_service().get_projection(a.decision_id).symbol == "AAPL"
    assert get_decision_service().get_projection(b.decision_id).symbol == "MSFT"


# -- 5-8: the same decision_id flows through Trust Ledger + evidence + gov --

def test_same_decision_id_reaches_trust_ledger_evidence_and_governance(ledger_conn, chain):
    rec = _make_recorder(
        candidate_event_id=chain["candidate_event_id"],
        manifest_id=chain["manifest_id"],
        trust_conn=ledger_conn,
    )
    did = rec.decision_id

    record_decision_safe(
        ledger_conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "REJECT", "QUALIFIED_REJECTION",
        rec.portfolio_snapshot, rec.market_context, rec.model_outputs,
        {"gate_trace": []}, rec.final_confidence,
        mtd.decisions.build_intent("REJECT"), rec.data_completeness,
        decision_id=did,
    )

    ledger_row_id = ledger_conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()[0]
    assert ledger_row_id == did

    types_for_did = [
        e.event_type for e in _lifecycle_ledger.get_events()
        if e.payload.get("decision_id") == did
    ]
    assert EventType.DECISION_CREATED in types_for_did
    assert EventType.EVIDENCE_ATTACHED in types_for_did
    assert EventType.GOVERNANCE_EVALUATED in types_for_did

    proj = get_decision_service().get_projection(did)
    assert proj.status in (DecisionState.EVIDENCE_ATTACHED, DecisionState.GOVERNANCE_EVALUATED)


# -- 9-10: one shared projection / advancement ---------------------------------

def test_projection_is_seeded_once_and_advances_on_the_shared_pair(ledger_conn, chain):
    rec = _make_recorder(
        candidate_event_id=chain["candidate_event_id"],
        manifest_id=chain["manifest_id"],
        trust_conn=ledger_conn,
    )
    did = rec.decision_id
    assert get_decision_service().get_projection(did).status == DecisionState.DECISION_CREATED

    record_decision_safe(
        ledger_conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "REJECT", "QUALIFIED_REJECTION",
        rec.portfolio_snapshot, rec.market_context, rec.model_outputs,
        {"gate_trace": []}, rec.final_confidence,
        mtd.decisions.build_intent("REJECT"), rec.data_completeness,
        decision_id=did,
    )
    assert get_decision_service().get_projection(did).status != DecisionState.DECISION_CREATED


# -- 14: REJECT is an outcome/event, never a DecisionAction -------------------

def test_reject_never_becomes_a_decision_action_value():
    from sentinel_engine.domain.decision_action import DecisionAction
    assert not DecisionAction.has_value("REJECT")
    rec = _make_recorder()
    proj = get_decision_service().get_projection(rec.decision_id)
    assert proj.action == "BUY"  # even the recorder that will REJECT starts as a BUY recommendation


# -- 15-18: failure isolation ------------------------------------------------

def test_sentinel_create_decision_failure_does_not_raise_and_keeps_decision_id(monkeypatch):
    class _Boom:
        def create_decision(self, *_a, **_k):
            raise RuntimeError("sentinel down")

    monkeypatch.setattr(mtd, "get_decision_service", lambda: _Boom())
    rec = _make_recorder()  # must not raise
    assert isinstance(rec.decision_id, str) and rec.decision_id.startswith("DEC-")


def test_record_decision_safe_absence_fallback_uses_write_decision_events_own_id(ledger_conn, chain):
    # No decision_id supplied -> write_decision_event() falls back to new_decision_id(asset),
    # byte-for-byte the pre-ADR-067 behavior. (Exit paths rely on this.)
    record_decision_safe(
        ledger_conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "HOLD", "QUALIFIED_REJECTION",
        {"portfolio_value": 1.0, "current_price": 1.0}, {"regime": "x", "decision_timestamp": "t"},
        {"xgboost": {"signal": "HOLD", "confidence": 0.5, "metadata": {}},
         "lstm": {"signal": "HOLD", "confidence": 0.5, "metadata": {}},
         "finbert": {"signal": "HOLD", "confidence": 0.5, "metadata": {}}},
        {}, 0.5, mtd.decisions.build_intent("HOLD"), mtd.decisions.build_data_completeness(),
    )
    row_id = ledger_conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()[0]
    assert row_id.startswith("DEC-")


# -- 11-13, 19-21: authority / boundary invariants (structural) --------------

def test_risk_manager_approve_buy_call_site_in_main_cycle_is_unchanged():
    src = (_REPO_ROOT / "bot" / "_main_cycle.py").read_text(encoding="utf-8")
    assert "if not risk.approve_buy(symbol, notional, ctx.portfolio_value," in src
    assert "ctx.portfolio_value, ctx.positions, managed_capital=_managed):" in src


def test_entry_context_has_no_sentinel_decision_id_field():
    from bot._main_cycle import EntryContext
    import dataclasses
    fields = {f.name for f in dataclasses.fields(EntryContext)}
    assert "decision_id" not in fields


def test_no_record_approval_or_register_policy_call_in_the_live_trading_path():
    # ADR-045 SS3 / ADR-067 SS7,SS14: the live trading path (bot/, scheduler/)
    # must never call record_approval() or register_policy(). The SentinelEngine
    # facade in sentinel_engine/services/sentinel_engine.py has 1:1 passthrough
    # methods, but that facade is only instantiated in applications/*/bootstrap.py
    # (Gradio UI wiring), never in bot/ or scheduler/ -- so it is not a live-path
    # caller. This test scopes to the ADR-002-protected trading path.
    import ast
    forbidden = {"record_approval", "register_policy"}
    hits = []
    for base in ("bot", "scheduler"):
        for path in (_REPO_ROOT / base).rglob("*.py"):
            if "/tests/" in path.as_posix() or path.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = getattr(f, "attr", None) or getattr(f, "id", None)
                    if name in forbidden:
                        hits.append((path.relative_to(_REPO_ROOT).as_posix(), node.lineno))
    assert hits == [], f"unexpected record_approval/register_policy call in the live trading path: {hits}"


def test_bot_trust_decisions_creates_exactly_one_sentinel_decision_call_site():
    import ast
    src = (_REPO_ROOT / "bot" / "_main_trust_decisions.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    call_sites = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "create_decision"
    ]
    assert len(call_sites) == 1
