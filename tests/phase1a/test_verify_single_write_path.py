"""Tests for scripts/verify_single_write_path.py.

Focus: the additive PHASE1A_TRADES_DB env-var override for check 5 (added so
the Phase 1A Section 14 verification orchestrator can target a disposable copy
of the accumulated production trades.db). Checks 1-4 (static analysis of the
repo tree) and the meaning of every check are unchanged; the default target
remains repo-root trades.db.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "verify_single_write_path.py")
CUTOVER = "2026-07-28T20:54:30-05:00"


def _mk_trades(path, rows):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE decision_log (decision_id TEXT, created_at TEXT)")
    c.executemany("INSERT INTO decision_log VALUES (?,?)", rows)
    c.commit()
    c.close()


def _run(env_trades_db=None):
    env = dict(os.environ)
    if env_trades_db is not None:
        env["PHASE1A_TRADES_DB"] = str(env_trades_db)
    else:
        env.pop("PHASE1A_TRADES_DB", None)
    return subprocess.run([sys.executable, SCRIPT], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=600)


def test_env_override_check5_fails_on_post_cutover_row(tmp_path):
    db = tmp_path / "prod_trades.db"
    _mk_trades(str(db), [("d-new", "2026-09-01T00:00:00-05:00")])
    proc = _run(env_trades_db=db)
    assert proc.returncode == 1
    assert "5. decision_log has zero rows written after cutover" in proc.stdout
    assert "[FAIL] 5." in proc.stdout


def test_env_override_check5_passes_when_only_pre_cutover_rows(tmp_path):
    db = tmp_path / "prod_trades.db"
    _mk_trades(str(db), [("d-old", "2026-07-17T18:21:11+00:00")])
    proc = _run(env_trades_db=db)
    assert "[PASS] 5. decision_log has zero rows written after cutover" in proc.stdout
    # checks 1-4 (repo tree) are expected green in a healthy tree, so exit 0 overall
    assert proc.returncode == 0


def test_env_override_check5_passes_when_no_decision_log_table(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(str(db)).close()
    proc = _run(env_trades_db=db)
    assert "[PASS] 5. decision_log has zero rows written after cutover" in proc.stdout
    assert "decision_log table does not exist" in proc.stdout


def test_default_target_is_repo_root_trades_db(tmp_path):
    # No env var -> the script targets repo-root trades.db (its historical default).
    proc = _run(env_trades_db=None)
    assert "5. decision_log has zero rows written after cutover" in proc.stdout
    assert "PHASE1A_TRADES_DB" not in proc.stdout  # never echoed
