"""Tests for scripts/hooks/edit_guard.py (Edit/Write PreToolUse + PostToolUse hook)."""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))

import edit_guard  # noqa: E402


def _payload(event, tool, file_path, cwd):
    return {
        "hook_event_name": event,
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
        "cwd": str(cwd),
    }


@pytest.fixture
def project(tmp_path):
    (tmp_path / "bot" / "strategy").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    return tmp_path


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel


def test_pre_frozen_path_asks_for_confirmation(project):
    out = edit_guard.evaluate(_payload("PreToolUse", "Edit", "bot/main.py", project), project)
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "ask"
    assert "FROZEN" in spec["permissionDecisionReason"]


def test_pre_unfrozen_path_is_silent(project):
    assert edit_guard.evaluate(_payload("PreToolUse", "Edit", "docs/notes.md", project), project) is None


def test_pre_absolute_windows_style_path_is_normalised(project):
    abs_path = str(project / "bot" / "main.py")
    out = edit_guard.evaluate(_payload("PreToolUse", "Write", abs_path, project), project)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_path_outside_project_is_ignored(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "x.py"
    assert edit_guard.evaluate(_payload("PostToolUse", "Edit", str(outside), project), project) is None


def test_non_edit_tool_is_ignored(project):
    assert edit_guard.evaluate(_payload("PreToolUse", "Bash", "bot/main.py", project), project) is None


def test_post_syntax_error_is_reported(project):
    rel = _write(project, "docs/broken.py", "def f(:\n    pass\n")
    out = edit_guard.evaluate(_payload("PostToolUse", "Write", rel, project), project)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "SYNTAX ERROR" in ctx and "broken.py:1" in ctx


def test_post_over_500_lines_is_reported(project):
    rel = _write(project, "docs/big.py", "x = 1\n" * 501)
    out = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)
    assert "501 lines" in out["hookSpecificOutput"]["additionalContext"]


def test_post_missing_test_is_reported_for_implementation_file(project):
    rel = _write(project, "bot/strategy/new_signal.py", "VALUE = 1\n")
    out = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "No test file found" in ctx
    assert "quant-reviewer" in ctx  # strategy path also routes to the quant pass


def test_module_exercised_by_differently_named_test_counts_as_tested(project):
    rel = _write(project, "scripts/tool.py", "VALUE = 1\n")
    _write(project, "tests/test_bash_gate_and_health.py", "import tool\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "No test file" not in ctx


def test_risk_path_routes_to_risk_officer(project):
    rel = _write(project, "bot/risk/limits.py", "VALUE = 1\n")
    _write(project, "tests/test_limits.py", "import limits\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "risk-officer" in ctx


def test_data_path_routes_to_data_engineer(project):
    rel = _write(project, "bot/db/store.py", "VALUE = 1\n")
    _write(project, "tests/test_store.py", "import store\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "data-engineer" in ctx


def test_unrelated_path_gets_no_specialist_routing(project):
    rel = _write(project, "scripts/tool.py", "VALUE = 1\n")
    _write(project, "tests/test_tool.py", "import tool\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "risk-officer" not in ctx and "data-engineer" not in ctx


def test_customer_and_security_files_get_governance_routing(project):
    _write(project, "PRODUCT.md", "# product\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", "PRODUCT.md", project), project)["hookSpecificOutput"]["additionalContext"]
    assert "compliance-advisor" in ctx
    rel = _write(project, "config.py", "X = 1\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "security-reviewer" in ctx


def test_post_clean_file_with_test_only_logs_decision(project):
    rel = _write(project, "scripts/tool.py", "VALUE = 1\n")
    _write(project, "tests/test_tool.py", "def test_x():\n    pass\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "DECISION LOG" in ctx
    assert "No test file" not in ctx and "SYNTAX" not in ctx


def test_post_test_file_itself_is_not_asked_for_a_test(project):
    rel = _write(project, "tests/test_thing.py", "def test_x():\n    pass\n")
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Write", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "No test file" not in ctx


def test_post_non_python_file_still_logs_decision(project):
    rel = _write(project, "docs/readme.md", "# hi\n" * 900)
    ctx = edit_guard.evaluate(_payload("PostToolUse", "Edit", rel, project), project)["hookSpecificOutput"]["additionalContext"]
    assert "DECISION LOG" in ctx and "500" not in ctx


def test_main_malformed_stdin_fails_open():
    out = io.StringIO()
    assert edit_guard.main(io.StringIO("not json"), out) == 0
    assert out.getvalue() == ""


def test_main_emits_json_for_frozen_edit(project):
    stdin = io.StringIO(json.dumps(_payload("PreToolUse", "Edit", "dashboard/app.py", project)))
    out = io.StringIO()
    assert edit_guard.main(stdin, out) == 0
    assert json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"] == "ask"
