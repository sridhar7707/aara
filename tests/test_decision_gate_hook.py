"""Tests for scripts/hooks/decision_gate.py (UserPromptSubmit decision protocol)."""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))

import decision_gate  # noqa: E402


def _run(stdin_text):
    out = io.StringIO()
    code = decision_gate.main(io.StringIO(stdin_text), out)
    return code, out.getvalue()


def test_injects_protocol_on_every_prompt():
    code, out = _run(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi"}))
    assert code == 0
    spec = json.loads(out)["hookSpecificOutput"]
    assert spec["hookEventName"] == "UserPromptSubmit"
    assert "DECISION RULE" in spec["additionalContext"]


def test_protocol_names_all_twelve_roles_and_governed_thresholds():
    ctx = decision_gate.PROTOCOL
    for role in ("architect", "developer", "ml-expert", "stock-strategist",
                 "risk-officer", "data-engineer", "compliance-advisor", "product-manager",
                 "security-reviewer", "qa-tester", "ui-ux-expert", "go-to-market", "support-docs"):
        assert role in ctx
    assert "VETO" in ctx and "external release" in ctx
    assert "stop_loss" in ctx and "XGB threshold" in ctx


def test_malformed_stdin_fails_open_silently():
    code, out = _run("not json")
    assert code == 0 and out == ""
