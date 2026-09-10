"""Phase 1A Section 14 verification orchestrator -- read-only.

Runs the automatable Section 14 acceptance checks against the accumulated
*production* Hugging Face-synced snapshots of trust_ledger.db / trades.db and
emits a dated evidence record. Authorised by the Task 5 design review; ADR-071
(Accepted) scopes the single-write-path clause.

Safety (asserted by tests): production DBs are obtained via
huggingface_hub.hf_hub_download only (never sync_db.pull_*), copied into a
disposable temp dir; only the copies are opened writably (ledger.db.init_db
migrates a snapshot). data/trust_ledger.db, trades.db and the HF cache are
untouched; every other read uses mode=ro.

Verdicts: PASS / FAIL / INCONCLUSIVE / SNAPSHOT_UNAVAILABLE / SNAPSHOT_STALE
(the last two force the overall verdict; no PASS is emitted). This orchestrator
NEVER emits an overall PASS on its own -- FAILED_WRITES and the
30-consecutive-days enumeration are inherently INCONCLUSIVE and need human
adjudication + sign-off per ADR-058 D2. A run is not a Phase 1A pass and does
not start the 30-day window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# --- Policy constants (isolated for review) --------------------------------
DEFAULT_WINDOW_START = "2026-07-28"
DEFAULT_WINDOW_END = "2026-08-27"            # inclusive last calendar day
DEFAULT_STALENESS_HOURS = 48.0             # recency bound, only with --require-recent
DEFAULT_HF_DB_REPO_ID = "ksri77/ai-trading-bot-db"
LEDGER_FILENAME, TRADES_FILENAME = "trust_ledger.db", "trades.db"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "analysis" / "phase1a_verification"
VERIFY_SWP_SCRIPT = REPO_ROOT / "scripts" / "verify_single_write_path.py"

PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"
SNAPSHOT_UNAVAILABLE, SNAPSHOT_STALE = "SNAPSHOT_UNAVAILABLE", "SNAPSHOT_STALE"

_DAY_TABLES = {"candidate_evaluation_events": "timestamp", "decision_events": "timestamp",
               "risk_evaluation_events": "timestamp", "constitution_enforcement_events": "check_timestamp"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _finding(cid, name, verdict, detail, counts=None, offending=None) -> dict:
    return {"id": cid, "name": name, "verdict": verdict, "detail": detail,
            "counts": counts or {}, "offending_ids": offending or []}


def _table_exists(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _day_bounds(d: date) -> tuple[str, str]:
    return d.isoformat() + "T00:00:00", (d + timedelta(days=1)).isoformat() + "T00:00:00"


def _max_ledger_timestamp(conn) -> str | None:
    best = None
    for table, col in _DAY_TABLES.items():
        if not _table_exists(conn, table):
            continue
        try:
            row = conn.execute(f"SELECT MAX({col}) FROM {table}").fetchone()
        except sqlite3.OperationalError:
            continue
        if row and row[0] and (best is None or row[0] > best):
            best = row[0]
    return best


def _win_executed(conn, ws, we) -> list[tuple]:
    return conn.execute(
        "SELECT decision_id, asset, action, timestamp, intent, model_outputs, risk_checks, data_completeness "
        "FROM decision_events WHERE event_type='EXECUTED' AND timestamp>=? AND timestamp<? ORDER BY sequence_number",
        (ws, we)).fetchall()


def _fields_complete(mo_s, rc_s, dc_s) -> bool:
    try:
        mo, rc, dc = json.loads(mo_s or "null"), json.loads(rc_s or "null"), json.loads(dc_s or "null")
    except (TypeError, json.JSONDecodeError):
        return False
    return bool(mo) and all(k in mo for k in ("xgboost", "lstm", "finbert")) and bool(rc) and bool(dc)


# --- production snapshot acquisition -------------------------------------
def fetch_production_dbs(work_dir: Path, *, repo_id: str, token: str | None) -> dict:
    """Download both production DBs into the HF cache via hf_hub_download.
    Never touches data/ or the repo copies. Returns {"status": "ok"|"unavailable"}."""
    if not token:
        return {"status": "unavailable", "detail": "HF token unavailable (config.HF_TOKEN / env HF_TOKEN empty)"}
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.utils import disable_progress_bars
        disable_progress_bars()
    except Exception as exc:  # pragma: no cover
        return {"status": "unavailable", "detail": f"huggingface_hub import failed: {exc}"}
    out = {"status": "ok", "repo_id": repo_id}
    for key, filename in (("ledger", LEDGER_FILENAME), ("trades", TRADES_FILENAME)):
        try:
            cached = hf_hub_download(repo_id=repo_id, filename=filename, repo_type="dataset",
                                    token=token, force_download=True)
        except Exception as exc:
            return {"status": "unavailable", "detail": f"hf_hub_download({filename}) failed: {exc}"}
        parts = Path(cached).resolve().parts
        rev = parts[parts.index("snapshots") + 1] if "snapshots" in parts else "unknown"
        out[key] = {"src": cached, "revision": rev}
    return out


def _resolve_sources(work_dir, *, fetch_result, ledger_db_path, trades_db_path, fetch_fn, repo_id, token) -> dict:
    if fetch_result is not None:
        return fetch_result
    if ledger_db_path and trades_db_path:
        return {"status": "ok", "repo_id": "(explicit paths)",
                "ledger": {"src": ledger_db_path, "revision": "local"},
                "trades": {"src": trades_db_path, "revision": "local"}}
    return fetch_fn(work_dir, repo_id=repo_id, token=token)


# --- checks ------------------------------------------------------------
def check_single_write_path(temp_trades: Path, *, runner=None) -> dict:
    name = "Single write path (verify_single_write_path.py; ADR-071 scope)"
    if runner is not None:
        return runner(str(temp_trades))
    env = {**os.environ, "PHASE1A_TRADES_DB": str(temp_trades)}
    try:
        proc = subprocess.run([sys.executable, str(VERIFY_SWP_SCRIPT)], cwd=str(REPO_ROOT),
                              env=env, capture_output=True, text=True, timeout=600)
    except Exception as exc:
        return _finding("SINGLE_WRITE_PATH", name, INCONCLUSIVE, f"could not execute: {exc}")
    tail = "\n".join(proc.stdout.strip().splitlines()[-8:])
    detail = (f"exit={proc.returncode}. {tail}"
              + (f" | stderr: {proc.stderr.strip()[:300]}" if proc.returncode and proc.stderr.strip() else "")
              + " | checks 1-4 are static analysis of the current repo tree, not per-day window proof.")
    return _finding("SINGLE_WRITE_PATH", name, PASS if proc.returncode == 0 else FAIL, detail,
                    counts={"exit_code": proc.returncode})


def check_candidate_linkage(conn, ws, we) -> dict:
    """Every window decision links to a candidate with evaluation_completed=1
    (mirrors phase1a_daily_acceptance_check.check_candidate_linkage, windowed)."""
    total = conn.execute("SELECT COUNT(*) FROM decision_events WHERE timestamp>=? AND timestamp<?", (ws, we)).fetchone()[0]
    if total == 0:
        return _finding("CANDIDATE_LINKAGE", "Candidate-evaluation linkage (every decision)",
                        INCONCLUSIVE, "0 decision_events in window.")
    bad = [r[0] for r in conn.execute(
        "SELECT d.decision_id FROM decision_events d "
        "LEFT JOIN candidate_evaluation_events c ON c.candidate_event_id=d.candidate_event_id "
        "WHERE d.timestamp>=? AND d.timestamp<? AND (c.candidate_event_id IS NULL OR c.evaluation_completed!=1)",
        (ws, we))]
    return _finding("CANDIDATE_LINKAGE", "Candidate-evaluation linkage (every decision)",
                    FAIL if bad else PASS, f"{total - len(bad)}/{total} decisions link to a completed candidate.",
                    counts={"decisions": total, "unlinked": len(bad)}, offending=bad[:50])


def check_manifest_linkage(conn, ws, we) -> dict:
    """Every window decision references a manifest that reached PROMOTED
    (mirrors check_manifest_linkage, windowed)."""
    rows = conn.execute("SELECT DISTINCT decision_id, deployment_manifest_id FROM decision_events "
                        "WHERE timestamp>=? AND timestamp<?", (ws, we)).fetchall()
    if not rows:
        return _finding("MANIFEST_LINKAGE", "Deployment-manifest linkage (every decision)",
                        INCONCLUSIVE, "0 decision_events in window.")
    bad = [d for d, m in rows if not conn.execute(
        "SELECT 1 FROM deployment_manifest_events WHERE manifest_id=? AND event_type='PROMOTED' LIMIT 1", (m,)).fetchone()]
    return _finding("MANIFEST_LINKAGE", "Deployment-manifest linkage (every decision)",
                    FAIL if bad else PASS, f"{len(rows) - len(bad)}/{len(rows)} decisions reference a PROMOTED manifest.",
                    counts={"decisions": len(rows), "unpromoted": len(bad)}, offending=bad[:50])


def check_data_integrity_all(conn, ws, we) -> dict:
    """Section 14 'every decision has ... model outputs present, a risk
    evaluation present, and data_completeness recorded' for EVERY window
    decision incl. QUALIFIED_REJECTION -- the coverage gap Task 5 found in
    check_executed_completeness (EXECUTED-only)."""
    rows = conn.execute("SELECT decision_id, model_outputs, risk_checks, data_completeness "
                        "FROM decision_events WHERE timestamp>=? AND timestamp<?", (ws, we)).fetchall()
    if not rows:
        return _finding("DATA_INTEGRITY_ALL", "Data integrity - all decisions", INCONCLUSIVE,
                        "0 decision_events in window.")
    bad = [r[0] for r in rows if not _fields_complete(r[1], r[2], r[3])]
    return _finding("DATA_INTEGRITY_ALL",
                    "Data integrity - all decisions (model_outputs[xgboost/lstm/finbert] + risk_checks + data_completeness)",
                    FAIL if bad else PASS, f"{len(rows) - len(bad)}/{len(rows)} window decisions carry all three fields.",
                    counts={"decisions": len(rows), "incomplete": len(bad)}, offending=bad[:50])


def check_executed_completeness(conn, ws, we) -> dict:
    name = "EXECUTED-decision completeness (check_executed_completeness, windowed)"
    ex = _win_executed(conn, ws, we)
    if not ex:
        return _finding("EXECUTED_COMPLETENESS", name, INCONCLUSIVE,
                        "0 EXECUTED decisions in window; EXECUTED-only check is vacuous (not a FAIL).")
    bad = [d for (d, _a, _ac, _ts, _i, mo, rc, dc) in ex if not _fields_complete(mo, rc, dc)]
    return _finding("EXECUTED_COMPLETENESS", name, FAIL if bad else PASS,
                    f"{len(ex) - len(bad)}/{len(ex)} EXECUTED decisions complete.",
                    counts={"executed": len(ex), "incomplete": len(bad)}, offending=bad[:50])


def check_duplicate_fingerprints(conn, ws, we) -> dict:
    name = "Duplicate decisions (S12: EXECUTED-only; check_duplicate_fingerprints, windowed)"
    ex = _win_executed(conn, ws, we)
    if not ex:
        return _finding("DUPLICATE_FINGERPRINTS", name, INCONCLUSIVE,
                        "0 EXECUTED decisions in window; S12 guard is EXECUTED-only, so vacuous (not a FAIL).")
    seen, dups = {}, []
    for d, asset, action, ts, intent_json, *_ in ex:
        intent = json.loads(intent_json) if intent_json else {}
        if intent.get("override_reason"):
            continue
        key = (asset, action, ts[:10])
        dups.append([d, seen[key]]) if key in seen else seen.__setitem__(key, d)
    return _finding("DUPLICATE_FINGERPRINTS", name, FAIL if dups else PASS,
                    f"{len(dups)} duplicate (asset, action, day) pair(s) among EXECUTED decisions w/o override.",
                    counts={"executed": len(ex), "duplicate_pairs": len(dups)},
                    offending=[x for pair in dups for x in pair][:50])


def check_reproducibility(conn, ws, we) -> dict:
    name = "Reproducibility sample (FR-0.10/NFR-8 artifact-checksum; EXECUTED-only)"
    if not _win_executed(conn, ws, we):
        return _finding("REPRODUCIBILITY_SAMPLE", name, INCONCLUSIVE,
                        "0 EXECUTED decisions in window; vacuous. ledger.reproducibility verifies artifact "
                        "checksums only, not output reproduction (no inference pipeline).")
    try:
        from scripts import phase1a_daily_acceptance_check as check_mod
        failures = check_mod.sample_reproducibility(conn)
    except Exception as exc:
        return _finding("REPRODUCIBILITY_SAMPLE", name, INCONCLUSIVE, f"could not run: {exc}")
    return _finding("REPRODUCIBILITY_SAMPLE", name, FAIL if failures else PASS,
                    f"{len(failures)} failure(s) in the most-recent EXECUTED sample (artifact checksums only).",
                    counts={"failures": len(failures)}, offending=failures[:20])


def check_provenance_chain(conn, ws, we) -> dict:
    """Full-population manifest-chain resolution for the window decision set,
    surfacing the known FinBERT provenance gap explicitly (INCONCLUSIVE, not
    PASS, not omitted). No schema/bootstrap changes."""
    name = "Provenance chain (Decision -> Manifest -> Training runs/Artifacts -> Strategy -> Risk rules)"
    manifests = [r[0] for r in conn.execute(
        "SELECT DISTINCT deployment_manifest_id FROM decision_events WHERE timestamp>=? AND timestamp<?", (ws, we))]
    if not manifests:
        return _finding("PROVENANCE_CHAIN", name, INCONCLUSIVE, "0 decision_events in window.")
    fails, finbert_gap, roles = [], False, set()
    try:
        for mid in manifests:
            if not conn.execute("SELECT 1 FROM deployment_manifest_events WHERE manifest_id=? AND event_type='PROMOTED' LIMIT 1", (mid,)).fetchone():
                fails.append(f"{mid}: never PROMOTED"); continue
            mrow = conn.execute("SELECT component_training_runs, strategy_version_id, risk_ruleset_id "
                                "FROM deployment_manifests WHERE manifest_id=?", (mid,)).fetchone()
            if not mrow:
                fails.append(f"{mid}: manifest row missing"); continue
            ctr_raw, strat_id, risk_id = mrow
            try:
                ctr = json.loads(ctr_raw) if ctr_raw else {}
            except json.JSONDecodeError:
                fails.append(f"{mid}: component_training_runs not JSON"); continue
            for role, run_id in ctr.items():
                run = conn.execute("SELECT artifact_id FROM model_training_runs WHERE training_run_id=?", (run_id,)).fetchone()
                if not run:
                    fails.append(f"{mid}: training run {run_id!r} ({role}) missing"); continue
                if not conn.execute("SELECT 1 FROM model_artifacts WHERE artifact_id=?", (run[0],)).fetchone():
                    fails.append(f"{mid}: artifact {run[0]!r} ({role}) missing"); continue
                roles.add(role.lower())
            if strat_id and not conn.execute("SELECT 1 FROM strategy_versions WHERE strategy_version_id=?", (strat_id,)).fetchone():
                fails.append(f"{mid}: strategy_version {strat_id!r} missing")
            if risk_id and not conn.execute("SELECT 1 FROM risk_rulesets WHERE risk_ruleset_id=?", (risk_id,)).fetchone():
                fails.append(f"{mid}: risk_ruleset {risk_id!r} missing")
            has_fb = any(k.lower() == "finbert" for k in ctr) or conn.execute(
                "SELECT 1 FROM model_artifacts WHERE LOWER(model_family)='finbert' LIMIT 1").fetchone() is not None
            finbert_gap = finbert_gap or not has_fb
    except sqlite3.OperationalError as exc:
        return _finding("PROVENANCE_CHAIN", name, INCONCLUSIVE, f"snapshot provenance schema differs: {exc}")
    if fails:
        return _finding("PROVENANCE_CHAIN", name, FAIL, "; ".join(fails[:20]),
                        counts={"manifests": len(manifests)}, offending=fails[:20])
    if finbert_gap:
        return _finding("PROVENANCE_CHAIN", name, INCONCLUSIVE,
                        f"Resolved for all window decisions: roles {sorted(roles)} + strategy + risk rules. "
                        "FinBERT has model_outputs but NO training-run/artifact in the manifest chain "
                        "(recovered S6 requires all three). Not resolved here (schema/bootstrap out of scope).",
                        counts={"manifests": len(manifests), "resolved_roles": sorted(roles)})
    return _finding("PROVENANCE_CHAIN", name, PASS,
                    f"All {len(manifests)} manifest(s) resolve fully (roles {sorted(roles)} + strategy + risk rules).",
                    counts={"manifests": len(manifests), "resolved_roles": sorted(roles)})


def check_hash_chain_integrity(conn) -> dict:
    name = "Hash-chain integrity + active_deployment_pointer drift (ledger.integrity)"
    try:
        import ledger.integrity as integrity
        res = integrity.run_integrity_check(conn)
    except Exception as exc:
        return _finding("HASH_CHAIN_INTEGRITY", name, INCONCLUSIVE, f"could not run: {exc}")
    broken, drift = res.get("broken_chains") or {}, bool(res.get("pointer_drift"))
    if broken or drift:
        return _finding("HASH_CHAIN_INTEGRITY", name, FAIL,
                        f"broken_chains={list(broken)} pointer_drift={drift}",
                        counts={"broken_chain_tables": list(broken), "pointer_drift": drift})
    return _finding("HASH_CHAIN_INTEGRITY", name, PASS, "All Group-A hash chains clean; no pointer drift.")


def check_failed_writes() -> dict:
    return _finding("FAILED_WRITES", "Zero failed writes over the window", INCONCLUSIVE,
                    "Not provable from durable artifacts: a write that raised before INSERT leaves no row and no "
                    "chain gap, and bot error logs are ephemeral/uncommitted. A prospective durable failure log "
                    "(protected bot/, out of scope) would be required.")


def check_per_day_enumeration(conn, trades_conn, ws_date, we_date) -> dict:
    """Deterministic per-calendar-day evidence enumeration. Always INCONCLUSIVE:
    '30 consecutive days' is an enumeration + human-adjudication item (Task 5)."""
    d0, d1 = date.fromisoformat(ws_date), date.fromisoformat(we_date)
    have_const = _table_exists(conn, "constitution_enforcement_events")
    trades_ok = trades_conn is not None and _table_exists(trades_conn, "trades")
    per_day, empty_days = [], []
    n_ev = n_empty = n_wknd = 0
    cur = d0
    while cur <= d1:
        lo, hi = _day_bounds(cur)
        cand = conn.execute("SELECT COUNT(*) FROM candidate_evaluation_events WHERE timestamp>=? AND timestamp<?", (lo, hi)).fetchone()[0]
        dec = conn.execute("SELECT COUNT(*) FROM decision_events WHERE timestamp>=? AND timestamp<?", (lo, hi)).fetchone()[0]
        risk = conn.execute("SELECT COUNT(*) FROM risk_evaluation_events WHERE timestamp>=? AND timestamp<?", (lo, hi)).fetchone()[0]
        con_ = (conn.execute("SELECT COUNT(*) FROM constitution_enforcement_events WHERE check_timestamp>=? AND check_timestamp<?", (lo, hi)).fetchone()[0]
                if have_const else None)
        trd = (trades_conn.execute("SELECT COUNT(*) FROM trades WHERE timestamp>=? AND timestamp<?", (lo, hi)).fetchone()[0]
               if trades_ok else None)
        weekend = cur.weekday() >= 5
        has_ev = any(x for x in (cand, dec, risk, con_, trd) if x)
        cls = "weekend" if weekend else ("evidence" if has_ev else "empty-trading-day")
        n_wknd += weekend
        n_ev += (not weekend and has_ev)
        if not weekend and not has_ev:
            n_empty += 1
            empty_days.append(cur.isoformat())
        per_day.append({"date": cur.isoformat(), "weekday": cur.strftime("%a"), "class": cls,
                        "candidate": cand, "decision": dec, "risk": risk, "constitution": con_, "trades": trd})
        cur += timedelta(days=1)
    detail = (f"{n_ev} trading day(s) with evidence, {n_empty} empty trading day(s)"
              + (f": {empty_days}" if empty_days else "") + f", {n_wknd} weekend/non-trading day(s). "
              "'30 consecutive days' is a human-adjudication item; this orchestrator does not PASS it. "
              "Weekday/weekend from stdlib calendar only (no market-holiday source in the repo).")
    return _finding("PER_DAY_ENUMERATION", "30 consecutive days - per-day evidence enumeration", INCONCLUSIVE, detail,
                    counts={"trading_days_with_evidence": n_ev, "empty_trading_days": n_empty,
                            "weekend_days": n_wknd, "empty_trading_day_dates": empty_days, "per_day": per_day})


def check_snapshot_freshness(snap_max, run_ts, window_end, *, require_recent, staleness_hours) -> dict:
    name = "Snapshot freshness (covers window + optional recency)"
    counts = {"snapshot_max_timestamp": snap_max, "run_timestamp": run_ts.isoformat(),
              "window_end": window_end, "staleness_hours": staleness_hours, "require_recent": require_recent}
    if not snap_max:
        return _finding("SNAPSHOT_FRESHNESS", name, SNAPSHOT_STALE, "Snapshot has no ledger events.", counts=counts)
    covers = snap_max[:10] >= window_end
    age_h, recency_ok = None, True
    try:
        parsed = datetime.fromisoformat(snap_max.replace("Z", "+00:00"))
        parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        age_h = (run_ts - parsed).total_seconds() / 3600.0
        recency_ok = (not require_recent) or age_h <= staleness_hours
    except ValueError:
        recency_ok = not require_recent
    counts.update({"covers_window": covers, "age_hours": round(age_h, 2) if age_h is not None else None,
                   "recency_ok": recency_ok})
    if not covers:
        return _finding("SNAPSHOT_FRESHNESS", name, SNAPSHOT_STALE,
                        f"Snapshot max date {snap_max[:10]} < window end {window_end}: cannot verify the whole window.",
                        counts=counts)
    if not recency_ok:
        return _finding("SNAPSHOT_FRESHNESS", name, SNAPSHOT_STALE,
                        f"Snapshot is {age_h:.1f}h old (> {staleness_hours}h) with --require-recent.", counts=counts)
    return _finding("SNAPSHOT_FRESHNESS", name, PASS, f"Snapshot covers the window (max {snap_max}).", counts=counts)


# --- orchestration ---------------------------------------------------
def _overall_verdict(checks) -> str:
    verdicts = {c["verdict"] for c in checks}
    if FAIL in verdicts:
        return FAIL
    return PASS if verdicts and verdicts.issubset({PASS}) else INCONCLUSIVE


_NOTES = [
    "READ-ONLY: production DBs are copied to a disposable temp dir; only the copies are opened writably "
    "(ledger.db.init_db migrates a snapshot). data/trust_ledger.db, trades.db and the HF cache are untouched.",
    "NEVER emits an overall PASS on its own: FAILED_WRITES and PER_DAY_ENUMERATION are inherently INCONCLUSIVE "
    "and need human adjudication + sign-off per ADR-058 D2.",
    "A run with overall != FAIL is NOT a Phase 1A pass and does NOT start the 30-day window.",
    "single-write-path checks 1-4 are static analysis of the current repo tree, not per-day window proof.",
]


def run_verification(*, window_start=DEFAULT_WINDOW_START, window_end=DEFAULT_WINDOW_END,
                     fetch_result=None, ledger_db_path=None, trades_db_path=None,
                     fetch_fn=fetch_production_dbs, hf_repo_id=DEFAULT_HF_DB_REPO_ID, hf_token=None,
                     swp_runner=None, require_recent=False, staleness_hours=DEFAULT_STALENESS_HOURS,
                     now=None, work_dir=None) -> dict:
    run_ts = now or _utc_now()
    ws = window_start + "T00:00:00"
    we = (date.fromisoformat(window_end) + timedelta(days=1)).isoformat() + "T00:00:00"
    made_tmp = work_dir is None
    wd = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="phase1a_verif_"))
    base = {"schema": "phase1a-verification/v1", "run_timestamp": run_ts.isoformat(),
            "window": {"start": window_start, "end": window_end}, "hf_repo_id": hf_repo_id}
    try:
        src = _resolve_sources(wd, fetch_result=fetch_result, ledger_db_path=ledger_db_path,
                               trades_db_path=trades_db_path, fetch_fn=fetch_fn, repo_id=hf_repo_id, token=hf_token)
        if src.get("status") != "ok":
            return {**base, "hf_revisions": {}, "snapshot_max_timestamp": None, "source_sha256": {},
                    "checks": [], "overall_verdict": SNAPSHOT_UNAVAILABLE,
                    "detail": src.get("detail", "production snapshot unavailable"), "notes": list(_NOTES)}
        temp_ledger, temp_trades = wd / "ledger_copy.db", wd / "trades_copy.db"
        shutil.copy2(src["ledger"]["src"], temp_ledger)
        shutil.copy2(src["trades"]["src"], temp_trades)
        source_sha = {"trust_ledger.db": _sha256(src["ledger"]["src"]),
                      "trades.db": _sha256(src["trades"]["src"])}
        hf_revisions = {"trust_ledger.db": src["ledger"]["revision"], "trades.db": src["trades"]["revision"]}

        import ledger.db as ledger_db
        conn = ledger_db.init_db(str(temp_ledger))          # migrates the DISPOSABLE copy only
        trades_conn = sqlite3.connect(f"file:{temp_trades}?mode=ro", uri=True)
        try:
            snap_max = _max_ledger_timestamp(conn)
            freshness = check_snapshot_freshness(snap_max, run_ts, window_end,
                                                 require_recent=require_recent, staleness_hours=staleness_hours)
            checks = [
                check_single_write_path(temp_trades, runner=swp_runner),
                check_candidate_linkage(conn, ws, we),
                check_manifest_linkage(conn, ws, we),
                check_data_integrity_all(conn, ws, we),
                check_executed_completeness(conn, ws, we),
                check_duplicate_fingerprints(conn, ws, we),
                check_reproducibility(conn, ws, we),
                check_provenance_chain(conn, ws, we),
                check_hash_chain_integrity(conn),
                check_failed_writes(),
                check_per_day_enumeration(conn, trades_conn, window_start, window_end),
            ]
        finally:
            trades_conn.close()
            conn.close()
        overall = SNAPSHOT_STALE if freshness["verdict"] == SNAPSHOT_STALE else _overall_verdict(checks)
        return {**base, "hf_revisions": hf_revisions, "snapshot_max_timestamp": snap_max,
                "source_sha256": source_sha, "snapshot_freshness": freshness,
                "checks": checks, "overall_verdict": overall, "notes": list(_NOTES)}
    finally:
        if made_tmp:
            shutil.rmtree(wd, ignore_errors=True)


# --- evidence output -----------------------------------------------
def render_markdown(result: dict) -> str:
    w = result["window"]
    L = [f"# Phase 1A Section 14 Verification - {result['run_timestamp']}", "",
         f"- **Overall verdict:** `{result['overall_verdict']}`",
         f"- **Window:** {w['start']} .. {w['end']} (inclusive)",
         f"- **HF dataset:** `{result.get('hf_repo_id')}`",
         f"- **HF revisions:** {result.get('hf_revisions') or '(unavailable)'}",
         f"- **Snapshot max ledger timestamp:** {result.get('snapshot_max_timestamp')}",
         f"- **Source SHA-256:** {result.get('source_sha256') or '(unavailable)'}", ""]
    if result["overall_verdict"] == SNAPSHOT_UNAVAILABLE:
        L += [f"> {result.get('detail', '')}", ""]
    fr = result.get("snapshot_freshness")
    if fr:
        L += [f"**Snapshot freshness:** `{fr['verdict']}` - {fr['detail']}", ""]
    L += ["## Checks", "", "| ID | Verdict | Name | Detail |", "| --- | --- | --- | --- |"]
    for c in result.get("checks", []):
        esc = c["detail"].replace("|", r"\|")
        L.append(f"| {c['id']} | `{c['verdict']}` | {c['name']} | {esc} |")
    L.append("")
    pd = next((c for c in result.get("checks", []) if c["id"] == "PER_DAY_ENUMERATION"), None)
    if pd:
        L += ["## Per-day evidence enumeration", "",
              "| Date | Day | Class | cand | dec | risk | const | trades |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in pd["counts"].get("per_day", []):
            L.append(f"| {r['date']} | {r['weekday']} | {r['class']} | {r['candidate']} | {r['decision']} | "
                     f"{r['risk']} | {r['constitution']} | {r['trades']} |")
        L.append("")
    L += ["## Notes", ""] + [f"- {n}" for n in result.get("notes", [])]
    L += ["", "## What this run does NOT do", "",
          "- It does not close Phase 1A Section 14 or ADR-004 Criterion 1.",
          "- It does not start the 30-consecutive-day validation window.",
          "- An overall verdict other than FAIL still requires a named human reviewer to adjudicate the "
          "INCONCLUSIVE items against the enumeration and record acceptance per ADR-058 D2.", ""]
    return "\n".join(L)


def write_evidence(result: dict, output_dir, *, label: str | None = None) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = result["run_timestamp"].replace(":", "").replace("-", "").replace("+0000", "Z")
    prefix = f"{stamp}-phase1a-verification" + (f"-{label}" if label else "")
    jp, mp = out / f"{prefix}.json", out / f"{prefix}.md"
    for p in (jp, mp):
        if p.exists():
            raise FileExistsError(f"refusing to overwrite existing evidence: {p}")
    jp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    mp.write_text(render_markdown(result), encoding="utf-8")
    return jp, mp


def _load_hf_config() -> tuple[str, str | None]:
    try:
        from config import HF_DB_REPO_ID, HF_TOKEN
        return HF_DB_REPO_ID or DEFAULT_HF_DB_REPO_ID, HF_TOKEN or os.environ.get("HF_TOKEN") or None
    except Exception:
        return os.environ.get("HF_DB_REPO_ID", DEFAULT_HF_DB_REPO_ID), os.environ.get("HF_TOKEN") or None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 1A Section 14 verification orchestrator (read-only).")
    ap.add_argument("--window-start", default=DEFAULT_WINDOW_START)
    ap.add_argument("--window-end", default=DEFAULT_WINDOW_END)
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    ap.add_argument("--no-emit", action="store_true", help="run and print, write no evidence file")
    ap.add_argument("--label", default=None, help="filename suffix, e.g. 'pre-window-baseline'")
    ap.add_argument("--require-recent", action="store_true")
    ap.add_argument("--staleness-hours", type=float, default=DEFAULT_STALENESS_HOURS)
    ap.add_argument("--ledger-db", default=None, help="explicit trust_ledger.db path (skips HF fetch)")
    ap.add_argument("--trades-db", default=None, help="explicit trades.db path (skips HF fetch)")
    args = ap.parse_args(argv)
    repo_id, token = _load_hf_config()
    result = run_verification(window_start=args.window_start, window_end=args.window_end,
                              ledger_db_path=args.ledger_db, trades_db_path=args.trades_db,
                              hf_repo_id=repo_id, hf_token=token, require_recent=args.require_recent,
                              staleness_hours=args.staleness_hours)
    print(render_markdown(result))
    if not args.no_emit:
        jp, mp = write_evidence(result, args.output_dir, label=args.label)
        print(f"\nEvidence written:\n  {jp}\n  {mp}")
    return 0 if result["overall_verdict"] in (PASS, INCONCLUSIVE) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
