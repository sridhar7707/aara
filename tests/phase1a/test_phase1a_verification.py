"""Tests for scripts/phase1a_verification.py -- the Phase 1A Section 14
verification orchestrator.

Synthetic ledger/trades databases are built with the same fixture primitives
as tests/phase1a/test_acceptance_30day.py. No network: the HF fetch is bypassed
by passing explicit DB paths or a mocked fetch_fn. The single-write-path
subprocess is stubbed via swp_runner except where its real behaviour is tested.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402
from scripts import phase1a_verification as pv  # noqa: E402

WS, WE = "2026-07-28", "2026-08-27"
_GOOD_MO = build_model_outputs(0.7, 0.6, 0.2)


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


def _pass_swp(_temp_trades):
    return pv._finding("SINGLE_WRITE_PATH", "stub", pv.PASS, "stubbed PASS")


def _bootstrap_chain(conn, tmp_path, *, with_finbert=False):
    art = tmp_path / "m.pkl"
    art.write_bytes(b"weights")
    chk = hashlib.sha256(art.read_bytes()).hexdigest()
    size = art.stat().st_size
    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_a','xgboost','v1',NULL,'h','2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO model_artifacts VALUES ('lstm_a','lstm','v1',NULL,'h','2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO model_training_runs VALUES ('xgb_r','xgb_a','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',?,?,?,'2026-06-01T00:00:00Z')", (str(art), chk, size))
    conn.execute("INSERT INTO model_training_runs VALUES ('lstm_r','lstm_a','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',?,?,?,'2026-06-01T00:00:00Z')", (str(art), chk, size))
    ctr = {"xgboost": "xgb_r", "lstm": "lstm_r"}
    if with_finbert:
        conn.execute("INSERT INTO model_artifacts VALUES ('fb_a','finbert','v1',NULL,'h','2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO model_training_runs VALUES ('fb_r','fb_a','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',?,?,?,'2026-06-01T00:00:00Z')", (str(art), chk, size))
        ctr["finbert"] = "fb_r"
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO deployment_manifests VALUES ('mani_v1',?,'risk_v1','strat_v1','fp','{}','2026-06-15T00:00:00Z')", (json.dumps(ctr),))
    conn.commit()
    ledger_svc.transition_manifest(conn, "mani_v1", "CREATED", "2026-06-15T00:00:00Z")
    ledger_svc.transition_manifest(conn, "mani_v1", "TESTING_STARTED", "2026-06-15T00:01:00Z")
    ledger_svc.transition_manifest(conn, "mani_v1", "REVIEW_REQUESTED", "2026-06-15T00:02:00Z")
    appr = ledger_svc.append_ledger_row(conn, "approval_events", {
        "approval_id": "APR-1", "timestamp": "2026-06-15T00:03:00Z", "subject_type": "MANIFEST_PROMOTION",
        "subject_id": "mani_v1", "decision": "APPROVE", "reason_checklist": {}, "reason_comment": "ok",
        "reviewer": "tester"})
    ledger_svc.transition_manifest(conn, "mani_v1", "APPROVED", "2026-06-15T00:04:00Z",
                                   approval_event_id=appr["approval_id"])
    ledger_svc.transition_manifest(conn, "mani_v1", "PROMOTED", "2026-06-15T00:05:00Z")
    return "mani_v1"


def _write_decision(conn, mid, *, day, asset="AAA", action="REJECT", event_type="QUALIFIED_REJECTION",
                    model_outputs=None, risk_checks=None, data_completeness=None, hh=10):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, asset, day, {}, data_available=True, required_models_available=True, evaluation_completed=True)
    return decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=asset, action=action, event_type=event_type,
        portfolio_snapshot={"v": 1.0}, market_context={"regime": "bull"},
        model_outputs=_GOOD_MO if model_outputs is None else model_outputs,
        risk_checks={"gates": []} if risk_checks is None else risk_checks,
        final_confidence=0.6, deployment_manifest_id=mid, intent=decisions.build_intent(action),
        data_completeness=decisions.build_data_completeness() if data_completeness is None else data_completeness,
        timestamp=f"{day}T{hh:02d}:00:00Z")


def _make_ledger(tmp_path, name="led.db", *, with_finbert=False, populate=None):
    path = str(tmp_path / name)
    conn = ledger_db.init_db(path)
    mid = _bootstrap_chain(conn, tmp_path, with_finbert=with_finbert)
    if populate:
        populate(conn, mid)
    conn.close()
    return path


def _make_trades(tmp_path, name="tr.db", *, decision_log=(), trades=()):
    path = str(tmp_path / name)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE decision_log (decision_id TEXT, created_at TEXT)")
    c.execute("CREATE TABLE trades (timestamp TEXT, symbol TEXT)")
    c.executemany("INSERT INTO decision_log VALUES (?,?)", list(decision_log))
    c.executemany("INSERT INTO trades VALUES (?,?)", list(trades))
    c.commit()
    c.close()
    return path


def _run(ledger_path, trades_path, **kw):
    kw.setdefault("swp_runner", _pass_swp)
    kw.setdefault("window_start", WS)
    kw.setdefault("window_end", WE)
    return pv.run_verification(ledger_db_path=ledger_path, trades_db_path=trades_path, **kw)


def _verdict(result, check_id):
    return next(c["verdict"] for c in result["checks"] if c["id"] == check_id)


def _check(result, check_id):
    return next(c for c in result["checks"] if c["id"] == check_id)


# --- 1. clean synthetic dataset -----------------------------------------
def test_clean_dataset_checks_pass_where_provable(tmp_path):
    def pop(conn, mid):
        for i, day in enumerate(("2026-07-30", "2026-07-30", "2026-08-17")):
            _write_decision(conn, mid, day=day, asset=f"S{i}", hh=10 + i)
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    tr = _make_trades(tmp_path, decision_log=[("D-old", "2026-07-01T00:00:00+00:00")],
                      trades=[("2026-07-30T12:00:00+00:00", "S0")])
    r = _run(led, tr)
    assert _verdict(r, "CANDIDATE_LINKAGE") == pv.PASS
    assert _verdict(r, "MANIFEST_LINKAGE") == pv.PASS
    assert _verdict(r, "DATA_INTEGRITY_ALL") == pv.PASS
    assert _verdict(r, "PROVENANCE_CHAIN") == pv.PASS
    assert _verdict(r, "HASH_CHAIN_INTEGRITY") == pv.PASS
    # inherently-inconclusive criteria keep the overall from being PASS
    assert _verdict(r, "FAILED_WRITES") == pv.INCONCLUSIVE
    assert _verdict(r, "PER_DAY_ENUMERATION") == pv.INCONCLUSIVE
    assert r["overall_verdict"] == pv.INCONCLUSIVE
    assert r["snapshot_freshness"]["verdict"] == pv.PASS


# --- 2. broken hash chain --------------------------------------------
def test_broken_hash_chain_fails(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-05")
        # raw insert with a fabricated all-zero hash -> genuinely broken chain
        conn.execute(
            "INSERT INTO cost_models (cost_model_id, spread_assumption, slippage_assumption, "
            "commission_rules, tax_assumptions, created_at, record_hash, previous_record_hash) "
            "VALUES ('cm_bad', 0.001, 0.001, '{}', '{}', '2026-08-05T00:00:00Z', "
            "'0000000000000000000000000000000000000000000000000000000000000000', "
            "'0000000000000000000000000000000000000000000000000000000000000000')")
        conn.commit()
    led = _make_ledger(tmp_path, populate=pop)
    tr = _make_trades(tmp_path)
    r = _run(led, tr)
    assert _verdict(r, "HASH_CHAIN_INTEGRITY") == pv.FAIL
    assert r["overall_verdict"] == pv.FAIL


# --- 3/4/5. QUALIFIED_REJECTION with a missing integrity field ---------
@pytest.mark.parametrize("kwargs", [
    {"model_outputs": {}},
    {"risk_checks": {}},
    {"data_completeness": {}},
])
def test_qualified_rejection_missing_field_fails(tmp_path, kwargs):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-06", asset="OK")
        _write_decision(conn, mid, day="2026-08-06", asset="BAD", hh=11, **kwargs)
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    r = _run(led, _make_trades(tmp_path))
    di = _check(r, "DATA_INTEGRITY_ALL")
    assert di["verdict"] == pv.FAIL
    assert di["counts"]["incomplete"] == 1
    assert di["offending_ids"]
    assert r["overall_verdict"] == pv.FAIL


# --- 6. zero EXECUTED rows -> EXECUTED-only checks INCONCLUSIVE --------
def test_zero_executed_makes_executed_only_checks_inconclusive(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-17", asset="Q1")
        _write_decision(conn, mid, day="2026-08-17", asset="Q2", hh=11)
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    r = _run(led, _make_trades(tmp_path))
    for cid in ("EXECUTED_COMPLETENESS", "DUPLICATE_FINGERPRINTS", "REPRODUCIBILITY_SAMPLE"):
        assert _verdict(r, cid) == pv.INCONCLUSIVE, cid
        assert "vacuous" in _check(r, cid)["detail"].lower()
    assert all(c["verdict"] != pv.PASS or c["id"] not in
               ("EXECUTED_COMPLETENESS", "DUPLICATE_FINGERPRINTS", "REPRODUCIBILITY_SAMPLE")
               for c in r["checks"])


# --- 7. missing snapshot -> SNAPSHOT_UNAVAILABLE ----------------------
def test_missing_snapshot_is_unavailable():
    r = pv.run_verification(fetch_fn=lambda *a, **k: {"status": "unavailable", "detail": "mocked: no token"},
                            swp_runner=_pass_swp)
    assert r["overall_verdict"] == pv.SNAPSHOT_UNAVAILABLE
    assert r["checks"] == []
    assert not any(c.get("verdict") == pv.PASS for c in r["checks"])
    assert "mocked" in r["detail"]


# --- 8. stale snapshot -> SNAPSHOT_STALE -----------------------------
def test_stale_snapshot_forces_overall_stale(tmp_path):
    # window_end is in the future relative to the synthetic snapshot's latest
    # event, so the snapshot cannot cover the window -> SNAPSHOT_STALE.
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-05")
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    r = _run(led, _make_trades(tmp_path), window_end="2099-12-31")
    assert r["snapshot_freshness"]["verdict"] == pv.SNAPSHOT_STALE
    assert r["overall_verdict"] == pv.SNAPSHOT_STALE
    assert r["snapshot_freshness"]["counts"]["covers_window"] is False


# --- 9. missing/unknown provenance (FinBERT gap) -> INCONCLUSIVE -----
def test_finbert_provenance_gap_is_inconclusive_not_pass(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-17")
    led = _make_ledger(tmp_path, with_finbert=False, populate=pop)   # xgboost+lstm only in the manifest
    r = _run(led, _make_trades(tmp_path))
    prov = _check(r, "PROVENANCE_CHAIN")
    assert prov["verdict"] == pv.INCONCLUSIVE
    assert "finbert" in prov["detail"].lower()
    assert prov["verdict"] != pv.PASS


# --- 10. failed-write historical criterion -> INCONCLUSIVE ----------
def test_failed_writes_is_always_inconclusive(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-20")
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    r = _run(led, _make_trades(tmp_path))
    fw = _check(r, "FAILED_WRITES")
    assert fw["verdict"] == pv.INCONCLUSIVE
    assert "not provable" in fw["detail"].lower()


# --- 11. source DB unchanged after verification --------------------
def test_source_databases_are_not_modified(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-17")
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    tr = _make_trades(tmp_path, decision_log=[("d", "2026-07-01T00:00:00+00:00")])

    def digest(p):
        return (hashlib.sha256(open(p, "rb").read()).hexdigest(), os.path.getmtime(p))

    before = {led: digest(led), tr: digest(tr)}
    repo_ledger = os.path.join(pv.REPO_ROOT, "data", "trust_ledger.db")
    repo_trades = os.path.join(pv.REPO_ROOT, "trades.db")
    repo_before = {p: digest(p) for p in (repo_ledger, repo_trades) if os.path.exists(p)}

    _run(led, tr)

    assert {led: digest(led), tr: digest(tr)} == before
    assert {p: digest(p) for p in repo_before} == repo_before


# --- 12. evidence JSON/Markdown generated correctly ---------------
def test_write_evidence_creates_json_and_markdown_and_refuses_overwrite(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-17")
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    r = _run(led, _make_trades(tmp_path))
    out = tmp_path / "evidence"
    jp, mp = pv.write_evidence(r, out, label="pre-window-baseline")
    assert jp.exists() and mp.exists()
    assert "pre-window-baseline" in jp.name
    loaded = json.loads(jp.read_text(encoding="utf-8"))
    assert loaded["overall_verdict"] == r["overall_verdict"]
    assert loaded["checks"] and "run_timestamp" in loaded
    md = mp.read_text(encoding="utf-8")
    assert md.startswith("# Phase 1A Section 14 Verification")
    assert "does not start the 30-consecutive-day validation window" in md
    with pytest.raises(FileExistsError):
        pv.write_evidence(r, out, label="pre-window-baseline")


# --- 13. per-day enumeration identifies an empty evidence day ------
def test_per_day_enumeration_flags_empty_trading_day(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-07-28")   # Tue: evidence
        _write_decision(conn, mid, day="2026-07-29")   # Wed: evidence
        # 2026-07-30 (Thu) and 2026-07-31 (Fri) left empty
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    r = _run(led, _make_trades(tmp_path), window_start="2026-07-28", window_end="2026-07-31")
    enum = _check(r, "PER_DAY_ENUMERATION")
    assert enum["verdict"] == pv.INCONCLUSIVE
    assert enum["counts"]["empty_trading_days"] == 2
    assert "2026-07-30" in enum["counts"]["empty_trading_day_dates"]
    assert "2026-07-31" in enum["counts"]["empty_trading_day_dates"]
    assert enum["counts"]["trading_days_with_evidence"] == 2


# --- extra: real single-write-path subprocess + env override ---------
def test_real_single_write_path_subprocess_targets_temp_trades(tmp_path):
    def pop(conn, mid):
        _write_decision(conn, mid, day="2026-08-17")
    led = _make_ledger(tmp_path, with_finbert=True, populate=pop)
    # a post-cutover decision_log row -> real verify_single_write_path.py check 5 FAIL -> exit 1
    tr = _make_trades(tmp_path, decision_log=[("d-new", "2026-09-01T00:00:00-05:00")])
    r = pv.run_verification(ledger_db_path=led, trades_db_path=tr, window_start=WS, window_end=WE)
    swp = _check(r, "SINGLE_WRITE_PATH")
    assert swp["verdict"] == pv.FAIL
    assert swp["counts"]["exit_code"] == 1
