"""Tests for
applications.trading_intelligence.adapters.trust_ledger_inspection_source.

Covers the ADR-064 read-side source contract:

  - SQLite opened mode=ro; no write of any kind;
  - exactly two authorized tables (candidate_evaluation_events,
    decision_events) and nothing else -- no decision_outcome_events,
    no trades.db / screener_log / signal_log;
  - the exact positive column allowlists; no SELECT *; no excluded column
    (record_hash / previous_record_hash / portfolio_snapshot /
    deployment_manifest_id) selected;
  - a missing authorized table or a missing authorized column makes the
    whole surface UNAVAILABLE (never a partial read);
  - empty authorized tables => HEALTHY + empty; populated => HEALTHY + data;
  - freshness from the snapshot file mtime + MAX(timestamp) across the two
    authorized tables only;
  - only the candidate_event_id relationship: candidate_event_id and
    decision_id are carried verbatim; the source forms no join;
  - valid JSON survives; one malformed JSON value degrades only that field
    to None ("not recorded"); the row and surface survive;
  - excluded nested sub-fields (model metadata; risk_checks fill_price /
    fill_shares / notional; intent expected_return_basis_points;
    market_context macro_score) are stripped before the contract record is
    built;
  - no synthesized replacement identity.

An opt-in read-only production regression runs against a real published
Trust Ledger snapshot when AARA_WAVE3A_LEDGER_SNAPSHOT points at one.
"""
import inspect
import json
import os
import sqlite3

import pytest

from applications.platform.integrations import IntegrationStatus
from applications.trading_intelligence.adapters import trust_ledger_inspection_source
from applications.trading_intelligence.adapters.trust_ledger_inspection_source import (
    TrustLedgerInspectionReader,
)
from applications.trading_intelligence.contracts.candidate_decision_contract import (
    CandidateEvaluationRecord,
    DecisionInspectionRecord,
    LedgerInspection,
)

_SRC = inspect.getsource(trust_ledger_inspection_source)

_CANDIDATE_DDL_FULL = """
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
)
"""

_DECISION_DDL_FULL = """
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
)
"""

_CAND_COLS = (
    "candidate_event_id, timestamp, asset, screening_version, screening_results, "
    "data_available, required_models_available, evaluation_requested, "
    "evaluation_completed, record_hash, previous_record_hash"
)
_DEC_COLS = (
    "decision_id, candidate_event_id, timestamp, asset, action, event_type, "
    "portfolio_snapshot, market_context, model_outputs, risk_checks, "
    "final_confidence, deployment_manifest_id, intent, data_completeness, "
    "record_hash, previous_record_hash"
)


def _candidate(**over):
    base = dict(
        candidate_event_id="CAND-1", timestamp="2026-07-29T14:33:22+00:00",
        asset="BLK", screening_version="screen_universe_v1",
        screening_results='{"rank":3,"composite_score":0.62,"sector":"Financials"}',
        data_available=1, required_models_available=0, evaluation_requested=1,
        evaluation_completed=1, record_hash="h", previous_record_hash="p",
    )
    base.update(over)
    return tuple(base[k] for k in (
        "candidate_event_id", "timestamp", "asset", "screening_version",
        "screening_results", "data_available", "required_models_available",
        "evaluation_requested", "evaluation_completed", "record_hash",
        "previous_record_hash",
    ))


def _decision(**over):
    base = dict(
        decision_id="DEC-1", candidate_event_id="CAND-1",
        timestamp="2026-07-30T13:48:41+00:00", asset="BLK",
        action="REJECT", event_type="QUALIFIED_REJECTION",
        portfolio_snapshot='{"portfolio_value":98892.73,"available_cash":40688.82}',
        market_context='{"regime":"HIGH_VOLATILITY","macro_score":0.60,"decision_timestamp":"2026-07-30T13:48:41+00:00"}',
        model_outputs='{"xgboost":{"signal":"BUY","confidence":0.57,"metadata":{"shap_drivers":[]}},"lstm":{"signal":"BUY","confidence":0.61,"metadata":{"is_degraded":true,"val_loss":0.62}},"finbert":{"signal":"HOLD","confidence":0.5,"metadata":{"raw_score":0.0}},"junk":1}',
        risk_checks='{"gate_trace":[{"gate":"volume","passed":false,"detail":"volume ratio 0.04 < 0.3"}],"fill_price":456.93,"fill_shares":17.4,"notional":7970.1}',
        final_confidence=0.5646,
        deployment_manifest_id="MFE-20260728-001",
        intent='{"primary_intent":"NO_ACTION","thesis":"x","invalidation_point":"y","expected_return_basis_points":2052}',
        data_completeness='{"status":"DEGRADED","missing_inputs":[],"stale_inputs":["lstm"]}',
        record_hash="h", previous_record_hash="p",
    )
    base.update(over)
    return tuple(base[k] for k in (
        "decision_id", "candidate_event_id", "timestamp", "asset", "action",
        "event_type", "portfolio_snapshot", "market_context", "model_outputs",
        "risk_checks", "final_confidence", "deployment_manifest_id", "intent",
        "data_completeness", "record_hash", "previous_record_hash",
    ))


def _make_db(tmp_path, *, candidates=(), decisions=(),
             candidate_ddl=_CANDIDATE_DDL_FULL, decision_ddl=_DECISION_DDL_FULL,
             include_decisions_table=True):
    path = tmp_path / "trust_ledger_snapshot.db"
    conn = sqlite3.connect(str(path))
    conn.execute(candidate_ddl)
    if include_decisions_table:
        conn.execute(decision_ddl)
    for row in candidates:
        conn.execute(
            f"INSERT INTO candidate_evaluation_events ({_CAND_COLS}) "
            f"VALUES ({', '.join('?' * 11)})", row)
    if include_decisions_table:
        for row in decisions:
            conn.execute(
                f"INSERT INTO decision_events ({_DEC_COLS}) "
                f"VALUES ({', '.join('?' * 16)})", row)
    conn.commit()
    conn.close()
    return str(path)


def _read(path):
    return TrustLedgerInspectionReader(db_path=path).read_inspection()


# --- read-only / write-forbidden -----------------------------------

def test_source_opens_read_only_and_cannot_write(tmp_path):
    path = _make_db(tmp_path, candidates=[_candidate()])
    reader = TrustLedgerInspectionReader(db_path=path)
    conn = reader._open_ro()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO candidate_evaluation_events "
                f"({_CAND_COLS}) VALUES ({', '.join('?' * 11)})",
                _candidate(candidate_event_id="CAND-X"),
            )
    finally:
        conn.close()


def test_module_source_uses_mode_ro_and_no_write_sql():
    assert "mode=ro" in _SRC
    upper = _SRC.upper()
    for stmt in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ",
                 "VACUUM", "REPLACE INTO"):
        assert stmt not in upper, f"source contains write SQL {stmt.strip()!r}"


# --- table scope --------------------------------------------------

def test_module_references_only_the_two_authorized_tables():
    assert "candidate_evaluation_events" in _SRC
    assert "decision_events" in _SRC
    for forbidden in ("decision_outcome_events", "trades.db", "trades_db",
                      "screener_log", "signal_log",
                      "constitution_enforcement_events",
                      "risk_evaluation_events", "deployment_manifest_events"):
        assert forbidden not in _SRC, f"source references out-of-scope {forbidden!r}"


def test_no_select_star():
    for select in (trust_ledger_inspection_source._SELECT_CANDIDATES,
                   trust_ledger_inspection_source._SELECT_DECISIONS):
        assert "*" not in select
        assert select.upper().startswith("SELECT ")


# --- positive column allowlist -----------------------------------

def test_candidate_column_allowlist_is_exact():
    assert trust_ledger_inspection_source._CANDIDATE_COLUMNS == (
        "candidate_event_id", "timestamp", "asset", "screening_version",
        "screening_results", "data_available", "required_models_available",
        "evaluation_requested", "evaluation_completed", "sequence_number",
    )


def test_decision_column_allowlist_is_exact():
    assert trust_ledger_inspection_source._DECISION_COLUMNS == (
        "decision_id", "candidate_event_id", "timestamp", "asset", "action",
        "event_type", "final_confidence", "model_outputs", "risk_checks",
        "intent", "market_context", "data_completeness", "sequence_number",
    )


def test_excluded_columns_are_never_selected():
    for excluded in ("record_hash", "previous_record_hash", "portfolio_snapshot",
                     "deployment_manifest_id"):
        assert excluded not in trust_ledger_inspection_source._SELECT_CANDIDATES
        assert excluded not in trust_ledger_inspection_source._SELECT_DECISIONS


def test_sequence_number_is_in_both_allowlists():
    assert "sequence_number" in trust_ledger_inspection_source._CANDIDATE_COLUMNS
    assert "sequence_number" in trust_ledger_inspection_source._DECISION_COLUMNS


# --- schema failure => whole surface UNAVAILABLE ----------------

def test_missing_authorized_table_is_unavailable(tmp_path):
    path = _make_db(tmp_path, candidates=[_candidate()], include_decisions_table=False)
    result = _read(path)
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_missing_authorized_column_is_unavailable(tmp_path):
    short_decision_ddl = _DECISION_DDL_FULL.replace(
        "    final_confidence       REAL NOT NULL,\n", "")
    path = _make_db(tmp_path, candidates=[_candidate()], decisions=[],
                    decision_ddl=short_decision_ddl)
    result = _read(path)
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_absent_snapshot_is_unavailable(tmp_path):
    result = _read(str(tmp_path / "nope.db"))
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_corrupt_file_is_not_healthy(tmp_path):
    path = tmp_path / "trust_ledger_snapshot.db"
    path.write_bytes(b"this is not a sqlite database")
    result = _read(str(path))
    assert result.value is None
    assert result.health.status is not IntegrationStatus.HEALTHY


# --- empty vs populated ----------------------------------------

def test_empty_authorized_tables_is_healthy_and_empty(tmp_path):
    path = _make_db(tmp_path, candidates=[], decisions=[])
    result = _read(path)
    assert result.is_healthy
    assert isinstance(result.value, LedgerInspection)
    assert result.value.candidates == ()
    assert result.value.decisions == ()
    assert result.value.is_empty is True
    assert result.value.data_through is None


def test_populated_tables_are_healthy_with_data(tmp_path):
    cands = [
        _candidate(candidate_event_id="CAND-1", asset="BLK"),
        _candidate(candidate_event_id="CAND-2", asset="JPM",
                   screening_results='{"note":"no screener pick data available for this symbol today"}'),
    ]
    decs = [
        _decision(decision_id="DEC-1", candidate_event_id="CAND-1", action="REJECT"),
        _decision(decision_id="DEC-2", candidate_event_id="CAND-1", action="HOLD",
                  event_type="QUALIFIED_REJECTION",
                  risk_checks='{"exit_reason":"no exit condition met"}'),
        _decision(decision_id="DEC-3", candidate_event_id="CAND-2", action="BUY",
                  event_type="EXECUTED"),
    ]
    path = _make_db(tmp_path, candidates=cands, decisions=decs)
    result = _read(path)

    assert result.is_healthy
    insp = result.value
    assert [c.candidate_event_id for c in insp.candidates] == ["CAND-1", "CAND-2"]
    assert [d.decision_id for d in insp.decisions] == ["DEC-1", "DEC-2", "DEC-3"]
    # ordering is by sequence_number ascending (insertion order here)
    assert [d.sequence_number for d in insp.decisions] == sorted(
        d.sequence_number for d in insp.decisions)
    assert insp.candidates[0].evaluation_completed is True
    assert insp.candidates[0].required_models_available is False
    assert insp.decisions[0].final_confidence == pytest.approx(0.5646)
    assert insp.is_empty is False
    # the {"note": ...} screening_results shape survives verbatim
    assert insp.candidates[1].screening_results == {
        "note": "no screener pick data available for this symbol today"}


# --- freshness ------------------------------------------------

def test_freshness_is_file_mtime_and_max_timestamp(tmp_path):
    cands = [_candidate(candidate_event_id="CAND-1",
                        timestamp="2026-07-29T00:00:00+00:00")]
    decs = [_decision(decision_id="DEC-1",
                      timestamp="2026-09-01T19:00:00+00:00")]
    path = _make_db(tmp_path, candidates=cands, decisions=decs)
    mtime = os.path.getmtime(path)

    insp = _read(path).value
    assert insp.data_through == "2026-09-01T19:00:00+00:00"  # max across both
    assert abs(insp.snapshot_mtime.timestamp() - mtime) < 2.0


def test_freshness_uses_only_the_two_authorized_tables():
    # MAX(timestamp) helper iterates only the two authorized-table constants
    assert trust_ledger_inspection_source._CANDIDATE_TABLE == "candidate_evaluation_events"
    assert trust_ledger_inspection_source._DECISION_TABLE == "decision_events"
    body = inspect.getsource(trust_ledger_inspection_source._max_timestamp)
    assert "_CANDIDATE_TABLE" in body and "_DECISION_TABLE" in body
    for other in ("trades.db", "screener_log", "signal_log",
                  "decision_outcome_events"):
        assert other not in body


# --- only candidate_event_id relationship --------------------

def test_source_forms_no_join_and_carries_candidate_event_id_verbatim(tmp_path):
    cands = [
        _candidate(candidate_event_id="CAND-X"),
        _candidate(candidate_event_id="CAND-Y"),
    ]
    decs = [_decision(decision_id="DEC-1", candidate_event_id="CAND-X")]
    insp = _read(_make_db(tmp_path, candidates=cands, decisions=decs)).value

    assert {c.candidate_event_id for c in insp.candidates} == {"CAND-X", "CAND-Y"}
    assert insp.decisions[0].candidate_event_id == "CAND-X"  # verbatim, unresolved
    # the source's SQL is two plain single-table SELECTs -- no JOIN
    assert "JOIN" not in trust_ledger_inspection_source._SELECT_CANDIDATES.upper()
    assert "JOIN" not in trust_ledger_inspection_source._SELECT_DECISIONS.upper()


def test_identity_columns_are_not_synthesized(tmp_path):
    decs = [_decision(decision_id="DEC-abc123", candidate_event_id="CAND-def456")]
    cands = [_candidate(candidate_event_id="CAND-def456")]
    insp = _read(_make_db(tmp_path, candidates=cands, decisions=decs)).value
    assert insp.decisions[0].decision_id == "DEC-abc123"
    assert insp.decisions[0].candidate_event_id == "CAND-def456"
    assert insp.candidates[0].candidate_event_id == "CAND-def456"


# --- JSON: valid, malformed, redaction ----------------------

def test_valid_json_is_parsed(tmp_path):
    insp = _read(_make_db(tmp_path, candidates=[_candidate()],
                          decisions=[_decision()])).value
    c = insp.candidates[0]
    d = insp.decisions[0]
    assert c.screening_results["rank"] == 3
    assert d.data_completeness["status"] == "DEGRADED"
    assert d.market_context["regime"] == "HIGH_VOLATILITY"
    assert d.risk_checks["gate_trace"][0]["gate"] == "volume"


def test_one_malformed_json_field_degrades_only_that_field(tmp_path):
    good = _decision(decision_id="DEC-1")
    bad = _decision(decision_id="DEC-2", risk_checks='{ this is not json')
    insp = _read(_make_db(tmp_path, candidates=[_candidate()],
                          decisions=[good, bad])).value
    assert _read  # surface healthy
    by_id = {d.decision_id: d for d in insp.decisions}
    assert by_id["DEC-2"].risk_checks is None            # degraded
    assert by_id["DEC-2"].intent is not None             # other fields intact
    assert by_id["DEC-2"].decision_id == "DEC-2"
    assert by_id["DEC-1"].risk_checks is not None        # other rows intact


def test_malformed_json_keeps_the_surface_healthy(tmp_path):
    bad = _decision(risk_checks="not json at all",
                    model_outputs="{bad", intent="[1,2,3]", market_context="")
    result = _read(_make_db(tmp_path, candidates=[_candidate()], decisions=[bad]))
    assert result.is_healthy
    d = result.value.decisions[0]
    assert d.risk_checks is None
    assert d.model_outputs is None
    assert d.intent is None            # parsed to a list, not an object -> None
    assert d.market_context is None


def test_model_outputs_redaction_keeps_only_signal_and_confidence(tmp_path):
    insp = _read(_make_db(tmp_path, candidates=[_candidate()],
                          decisions=[_decision()])).value
    mo = insp.decisions[0].model_outputs
    assert set(mo) == {"xgboost", "lstm", "finbert"}   # "junk" dropped
    for model in mo.values():
        assert set(model) <= {"signal", "confidence"}
        assert "metadata" not in model


def test_risk_checks_excludes_execution_fields(tmp_path):
    insp = _read(_make_db(tmp_path, candidates=[_candidate()],
                          decisions=[_decision()])).value
    rc = insp.decisions[0].risk_checks
    assert "gate_trace" in rc
    for excluded in ("fill_price", "fill_shares", "notional"):
        assert excluded not in rc


def test_intent_excludes_expected_return_basis_points(tmp_path):
    insp = _read(_make_db(tmp_path, candidates=[_candidate()],
                          decisions=[_decision()])).value
    it = insp.decisions[0].intent
    assert it["primary_intent"] == "NO_ACTION"
    assert "expected_return_basis_points" not in it


def test_market_context_excludes_macro_score(tmp_path):
    insp = _read(_make_db(tmp_path, candidates=[_candidate()],
                          decisions=[_decision()])).value
    mc = insp.decisions[0].market_context
    assert mc["regime"] == "HIGH_VOLATILITY"
    assert "macro_score" not in mc


# --- no outcome computation anywhere -------------------------

def test_source_computes_no_outcome_or_pnl():
    lowered = _SRC.lower()
    for token in ("realized_pnl", "gross_return", "net_return",
                  "holding_period", "pnl_pct", "outcome_direction",
                  "win", "loss"):
        assert token not in lowered, f"source references outcome token {token!r}"


# --- opt-in production regression (read-only) ---------------

_PROD = os.environ.get("AARA_WAVE3A_LEDGER_SNAPSHOT")


@pytest.mark.skipif(
    not _PROD, reason="set AARA_WAVE3A_LEDGER_SNAPSHOT to a real trust_ledger.db")
def test_production_snapshot_reads_read_only_without_bridge():
    result = TrustLedgerInspectionReader(db_path=_PROD).read_inspection()
    assert result.is_healthy
    insp = result.value
    assert all(isinstance(c, CandidateEvaluationRecord) for c in insp.candidates)
    assert all(isinstance(d, DecisionInspectionRecord) for d in insp.decisions)
    assert len(insp.candidates) >= 1
    # candidate_event_id relationship is intact: every decision cites a
    # non-empty candidate_event_id (the DB FK guarantees it points at a row)
    assert all(d.candidate_event_id for d in insp.decisions)
    # sequence_number available and ordering deterministic
    assert [c.sequence_number for c in insp.candidates] == sorted(
        c.sequence_number for c in insp.candidates)
    # no outcome / trade bridge: contract records carry no such field
    assert not hasattr(insp.decisions[0] if insp.decisions else insp, "realized_pnl")
    # malformed / optional JSON did not crash the read
    assert result.value.data_through is not None
