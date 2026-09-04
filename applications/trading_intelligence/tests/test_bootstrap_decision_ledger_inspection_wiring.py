"""Wave 3C: composition-root wiring for the Decision Ledger Inspection
section (ADR-064).

``_build_performance_learning_screen`` now also reads the published Trust
Ledger snapshot through the Wave 3A source + Wave 3B query service and
attaches the frozen ``CandidateDecisionInspection`` (or its non-HEALTHY
health) to the screen. The provider is invoked exactly once by
``PerformanceLearningUI.__init__`` -- no ``demo.load``, no Refresh.
"""
import os
import sqlite3
import tempfile

import gradio as gr
import pytest

from applications.platform.integrations import IntegrationStatus
from applications.trading_intelligence.adapters import trust_ledger_snapshot as _tls


@pytest.fixture(autouse=True)
def _clean_runtime_ledger_snapshot():
    """These tests rely on the product ``.runtime/`` Trust Ledger snapshot
    being ABSENT (so ``ledger_db_path=None`` fails closed). A prior test's
    abandoned slow-worker daemon (from the snapshot-fetch timeout tests)
    can leave a stray file there; sweep it before each test. The dir is
    gitignored, so this never touches the repo."""
    for leftover in list(_tls._RUNTIME_DIR.glob("*trust_ledger_snapshot*")):
        try:
            leftover.unlink()
        except OSError:
            pass
    yield
from applications.trading_intelligence.bootstrap import (
    _build_performance_learning_screen,
    _build_performance_learning_ui,
    build_trading_intelligence_app,
)
from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    CandidateDecisionInspection,
)
from applications.trading_intelligence.ui.performance_learning.screen import (
    PerformanceLearningScreen,
)

_LEDGER_DDL = """
CREATE TABLE candidate_evaluation_events (
    sequence_number           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_event_id        TEXT NOT NULL UNIQUE,
    timestamp                 TEXT NOT NULL,
    asset                     TEXT NOT NULL,
    screening_version         TEXT NOT NULL,
    screening_results         TEXT NOT NULL,
    data_available            INTEGER NOT NULL,
    required_models_available  INTEGER NOT NULL,
    evaluation_requested      INTEGER NOT NULL,
    evaluation_completed      INTEGER NOT NULL,
    record_hash               TEXT NOT NULL,
    previous_record_hash      TEXT NOT NULL
);
CREATE TABLE decision_events (
    sequence_number        INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id            TEXT NOT NULL UNIQUE,
    candidate_event_id     TEXT NOT NULL,
    timestamp              TEXT NOT NULL,
    asset                  TEXT NOT NULL,
    action                 TEXT NOT NULL,
    event_type             TEXT NOT NULL,
    portfolio_snapshot     TEXT NOT NULL,
    market_context         TEXT NOT NULL,
    model_outputs          TEXT NOT NULL,
    risk_checks            TEXT NOT NULL,
    final_confidence       REAL NOT NULL,
    deployment_manifest_id TEXT NOT NULL,
    intent                 TEXT NOT NULL,
    data_completeness      TEXT NOT NULL,
    record_hash            TEXT NOT NULL,
    previous_record_hash   TEXT NOT NULL
);
"""


def _make_ledger_db(*, candidates, decisions):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_LEDGER_DDL)
    for c in candidates:
        conn.execute(
            "INSERT INTO candidate_evaluation_events "
            "(candidate_event_id,timestamp,asset,screening_version,screening_results,"
            "data_available,required_models_available,evaluation_requested,"
            "evaluation_completed,record_hash,previous_record_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", c)
    for d in decisions:
        conn.execute(
            "INSERT INTO decision_events "
            "(decision_id,candidate_event_id,timestamp,asset,action,event_type,"
            "portfolio_snapshot,market_context,model_outputs,risk_checks,"
            "final_confidence,deployment_manifest_id,intent,data_completeness,"
            "record_hash,previous_record_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", d)
    conn.commit()
    conn.close()
    return path


_CAND = ("CAND-1", "2026-07-29T14:33:22+00:00", "BLK", "screen_universe_v1",
         '{"rank":3,"composite_score":0.62}', 1, 0, 1, 1, "h", "p")
_CAND2 = ("CAND-2", "2026-07-29T14:34:00+00:00", "JPM", "screen_universe_v1",
          '{"rank":1}', 0, 0, 1, 0, "h", "p")
_DEC = ("DEC-1", "CAND-1", "2026-07-30T13:48:41+00:00", "BLK", "REJECT",
        "QUALIFIED_REJECTION", "{}", '{"regime":"BULL","macro_score":0.6}',
        '{"xgboost":{"signal":"BUY","confidence":0.57,"metadata":{"x":1}}}',
        '{"gate_trace":[{"gate":"volume","passed":false,"detail":"low"}],"fill_price":1}',
        0.56, "MFE-1", '{"primary_intent":"NO_ACTION","expected_return_basis_points":9}',
        '{"status":"DEGRADED","missing_inputs":[],"stale_inputs":["lstm"]}', "h", "p")


# --- no ledger snapshot -> UNAVAILABLE ----------------------------

def test_no_ledger_path_yields_unavailable_ledger_section():
    screen = _build_performance_learning_screen(None, ledger_db_path=None)
    assert isinstance(screen, PerformanceLearningScreen)
    # No ledger snapshot -> the section renders its honest unavailable
    # state (ADR-064 Section 10: absent / unreadable / structurally short
    # all fail closed to non-HEALTHY; never turned into empty/fabricated).
    assert screen.ledger_available is False
    assert screen.ledger_inspection is None
    assert screen.ledger_health is not None
    assert not screen.ledger_health.is_healthy
    # Outcome History / Attribution / Calibration sections untouched
    assert screen.attribution_breakdown.title == "Attribution Breakdown"


def test_missing_ledger_file_is_explicitly_unavailable():
    screen = _build_performance_learning_screen(
        None, ledger_db_path="no_such_ledger_snapshot_xyz.db")
    assert screen.ledger_available is False
    assert screen.ledger_health.status is IntegrationStatus.UNAVAILABLE


# --- valid ledger snapshot -> HEALTHY inspection ----------------

def test_valid_ledger_snapshot_populates_the_inspection():
    path = _make_ledger_db(candidates=[_CAND, _CAND2], decisions=[_DEC])
    try:
        screen = _build_performance_learning_screen(None, ledger_db_path=path)
        assert screen.ledger_available is True
        insp = screen.ledger_inspection
        assert isinstance(insp, CandidateDecisionInspection)
        assert [c.candidate_event_id for c in insp.candidates] == ["CAND-1", "CAND-2"]
        assert insp.decision_count == 1
        c1 = insp.candidates[0]
        assert [d.decision_id for d in c1.decisions] == ["DEC-1"]
        assert c1.decisions[0].gate_finding.gate == "volume"
        # Wave 3B redaction survived the whole chain
        d = c1.decisions[0]
        assert "metadata" not in (d.model_outputs.get("xgboost") or {})
        assert "fill_price" not in (d.risk_checks or {})
        assert "expected_return_basis_points" not in (d.intent or {})
        assert "macro_score" not in (d.market_context or {})
        # candidate with no decision + incomplete evaluation
        c2 = insp.candidates[1]
        assert c2.has_decisions is False
        assert c2.terminal_state_message == "Evaluation Not Completed — no decision recorded"
    finally:
        os.remove(path)


def test_empty_ledger_tables_is_healthy_but_empty():
    path = _make_ledger_db(candidates=[], decisions=[])
    try:
        screen = _build_performance_learning_screen(None, ledger_db_path=path)
        assert screen.ledger_available is True
        assert screen.ledger_is_empty is True
        assert screen.ledger_inspection.candidates == ()
    finally:
        os.remove(path)


# --- provider invoked exactly once -----------------------------

def test_ui_provider_is_invoked_exactly_once(monkeypatch):
    import applications.trading_intelligence.bootstrap as boot

    calls = {"n": 0}
    real = boot._build_performance_learning_screen

    def _counting(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(boot, "_build_performance_learning_screen", _counting)
    ui = boot._build_performance_learning_ui(None, ledger_db_path=None)
    assert calls["n"] == 1
    ui.build()
    assert calls["n"] == 1  # build() does not re-invoke the provider


# --- composed app still fine ---------------------------------

def test_composed_app_still_has_six_screens_and_ledger_section_css():
    app = build_trading_intelligence_app()
    assert isinstance(app, gr.Blocks)
    for name in ("Morning Brief", "Decision Center", "Portfolio Intelligence",
                 "Risk Intelligence", "Performance & Learning", "Settings"):
        assert name in app.head
    assert app.css and "pl-dli" in app.css
    # existing P&L outcome CSS survived
    assert "pl-outcome-table" in app.css


# --- opt-in production regression (real published snapshot shape) ---

_PROD = os.environ.get("AARA_WAVE3A_LEDGER_SNAPSHOT")


import pytest  # noqa: E402


@pytest.mark.skipif(not _PROD, reason="set AARA_WAVE3A_LEDGER_SNAPSHOT to a real trust_ledger.db")
def test_production_snapshot_wires_into_the_screen():
    screen = _build_performance_learning_screen(None, ledger_db_path=_PROD)
    assert screen.ledger_available is True
    insp = screen.ledger_inspection
    assert len(insp.candidates) == 202
    assert insp.decision_count == 135
    assert insp.unmatched_decisions == ()
    no_decision = [c for c in insp.candidates if not c.has_decisions]
    assert len(no_decision) == 173
    assert insp.data_through is not None
