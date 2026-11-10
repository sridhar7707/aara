"""Tests for scripts/hooks/bash_gate.py and scripts/hooks/session_health.py."""
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))

import bash_gate  # noqa: E402
import session_health  # noqa: E402


# ---- bash_gate ----

def test_gate_selects_script_only_for_matching_command():
    assert bash_gate.select("commit_post", "git commit -m 'x'") == ["scripts/post_commit_review.py"]
    assert bash_gate.select("commit_post", "ruff check bot/") is None
    assert bash_gate.select("push_pre", "git push origin main") == ["scripts/arch_review.py", "--diff"]
    assert bash_gate.select("push_pre", "git status") is None


def test_gate_unknown_name_never_runs():
    assert bash_gate.select("nope", "git commit") is None


def test_gate_main_skips_subprocess_for_non_matching_command(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bash_gate.subprocess, "run", lambda *a, **k: calls.append(a))
    raw = json.dumps({"tool_input": {"command": "python -m pytest -q"}})
    assert bash_gate.main(["bash_gate.py", "commit_post"], raw, tmp_path) == 0
    assert calls == []


def test_gate_main_runs_script_for_matching_command(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bash_gate.subprocess, "run", lambda argv, **k: calls.append(argv))
    raw = json.dumps({"tool_input": {"command": "git commit -m 'x'"}})
    bash_gate.main(["bash_gate.py", "commit_post"], raw, tmp_path)
    assert len(calls) == 1 and calls[0][-1] == "scripts/post_commit_review.py"


def test_gate_malformed_stdin_fails_open(tmp_path):
    assert bash_gate.main(["bash_gate.py", "commit_post"], "not json", tmp_path) == 0


# ---- session_health ----

SAMPLE_OUTPUT = (
    "Results: 0 FAIL  0 WARN\n"
    "Features:  60 complete / 0 in progress / 0 planned\n"
    "Coverage:  100% of features complete\n"
    "0 broken reference(s), 0 line-count mismatch(es)\n"
)


def test_summarize_keeps_only_status_lines():
    lines = session_health.summarize(SAMPLE_OUTPUT + "lots of noise\nBROKEN REF `x`\n")
    assert lines == [
        "Results: 0 FAIL  0 WARN",
        "Features:  60 complete / 0 in progress / 0 planned",
        "Coverage:  100% of features complete",
        "0 broken reference(s), 0 line-count mismatch(es)",
    ]


def test_fresh_cache_does_not_run_checks(monkeypatch, tmp_path):
    report = tmp_path / "logs" / "health_latest.txt"
    report.parent.mkdir(parents=True)
    report.write_text("# run now\nResults: 0 FAIL  0 WARN\n0 broken reference(s), 0 line-count mismatch(es)\n---\n\nbody\n",
                      encoding="utf-8")

    def boom(_root):
        raise AssertionError("checks must not run when cache is fresh")

    monkeypatch.setattr(session_health, "run_checks", boom)
    context = session_health.build_context(tmp_path, refresh=False)
    assert "cached" in context and "Results: 0 FAIL  0 WARN" in context
    assert "body" not in context  # full output is never injected


def test_stale_cache_reruns_and_writes_report(monkeypatch, tmp_path):
    report = tmp_path / "logs" / "health_latest.txt"
    report.parent.mkdir(parents=True)
    report.write_text("# old\nResults: old\n", encoding="utf-8")
    old = time.time() - 8 * 24 * 3600
    import os
    os.utime(report, (old, old))

    monkeypatch.setattr(session_health, "run_checks", lambda _root: SAMPLE_OUTPUT)
    context = session_health.build_context(tmp_path, refresh=False)
    assert "ran now" in context
    assert "Results: 0 FAIL  0 WARN" in context
    assert "Results: 0 FAIL  0 WARN" in report.read_text(encoding="utf-8")


def test_refresh_flag_forces_run_even_when_fresh(monkeypatch, tmp_path):
    report = tmp_path / "logs" / "health_latest.txt"
    report.parent.mkdir(parents=True)
    report.write_text("# fresh\nResults: stale\n", encoding="utf-8")
    monkeypatch.setattr(session_health, "run_checks", lambda _root: SAMPLE_OUTPUT)
    assert "ran now" in session_health.build_context(tmp_path, refresh=True)


def test_main_emits_session_start_json(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(session_health, "run_checks", lambda _root: SAMPLE_OUTPUT)
    out = io.StringIO()
    assert session_health.main([], out) == 0
    spec = json.loads(out.getvalue())["hookSpecificOutput"]
    assert spec["hookEventName"] == "SessionStart"
