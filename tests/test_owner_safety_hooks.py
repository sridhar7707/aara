"""Tests for owner_brief, claim_check, and secret_scan. Fake secrets are built at runtime."""
import io
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))

import claim_check  # noqa: E402
import owner_brief  # noqa: E402
import secret_scan  # noqa: E402


# ---- owner_brief ----

def test_brief_shows_countdown_and_proposed_decisions():
    text = owner_brief.build_brief(["Results: 0 FAIL  0 WARN"], ["abc1234 feat: x"], 2,
                                   ["ADR-999-example"], date(2026, 11, 7))
    assert "Results: 0 FAIL  0 WARN" in text
    assert "ADR-999-example" in text
    assert "2027-11-07" in text and "365 days away" in text
    assert "Uncommitted files: 2" in text


def test_brief_handles_missing_sources():
    text = owner_brief.build_brief([], [], 0, [], date(2026, 11, 7))
    assert "no health report yet" in text
    assert "none found" in text
    assert "none" in text


# ---- claim_check ----

def test_flags_return_promises_with_line_numbers():
    text = "Welcome.\nWe guarantee profit every month.\nRisk-free returns!\n"
    hits = claim_check.find_claims(text)
    assert [n for n, _, _ in hits] == [2, 3]


def test_plain_text_is_not_flagged():
    assert claim_check.find_claims("Signals are advice. You decide.\n") == []


def test_claim_check_only_scans_customer_paths(tmp_path):
    (tmp_path / "docs" / "internal").mkdir(parents=True)
    (tmp_path / "docs" / "internal" / "note.md").write_text("guaranteed returns\n", encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": "docs/internal/note.md"}}
    assert claim_check.evaluate(payload, tmp_path) is None


def test_claim_check_warns_on_customer_path(tmp_path):
    (tmp_path / "PRODUCT.md").write_text("Guaranteed returns for members.\n", encoding="utf-8")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "PRODUCT.md"}}
    out = claim_check.evaluate(payload, tmp_path)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "CLAIM CHECK" in ctx and "PRODUCT.md:1" in ctx


def test_claim_check_malformed_stdin_fails_open(tmp_path):
    out = io.StringIO()
    assert claim_check.main(io.StringIO("nope"), out, root=tmp_path) == 0
    assert out.getvalue() == ""


# ---- secret_scan ----

def test_detects_aws_key_in_added_line():
    key = "AKIA" + "0" * 16
    diff = f"+++ b/config.py\n@@ -1,0 +1 @@\n+KEY = '{key}'\n"
    hits = secret_scan.findings_in_diff(diff)
    assert hits == [("config.py", 1, "AWS access key")]


def test_detects_hard_coded_password_and_reports_line():
    value = "a" * 20
    diff = f"+++ b/bot/x.py\n@@ -3,0 +4,2 @@\n+x = 1\n+password = \"{value}\"\n"
    hits = secret_scan.findings_in_diff(diff)
    assert hits == [("bot/x.py", 5, "hard-coded secret")]


def test_clean_diff_has_no_findings():
    assert secret_scan.findings_in_diff("+++ b/a.py\n@@ -0,0 +1 @@\n+VALUE = 1\n") == []


def test_removed_secret_is_not_reported():
    key = "AKIA" + "0" * 16
    assert secret_scan.findings_in_diff(f"+++ b/a.py\n@@ -1 +0,0 @@\n-KEY = '{key}'\n") == []


def test_env_file_is_blocked_but_example_is_allowed():
    assert secret_scan.env_files([".env", "config/.env", ".env.example"]) == [".env", "config/.env"]
