#!/usr/bin/env python3
"""Edit-time guard for Edit / Write / MultiEdit.

PreToolUse on a frozen path  -> permissionDecision "ask" (a human confirms).
PostToolUse on a .py file    -> syntax check, 500-line cap, missing-test advisory,
                                and a hint to consult the right specialist agent.

Fails open: any internal error is logged to stderr and the edit is never blocked
by a hook bug. Input: hook JSON on stdin. Output: hook JSON on stdout.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

MAX_LINES = 500  # CLAUDE.md: keep files under 500 lines

# Paths project memory marks as frozen (AARA migration; ADR-001 / ADR-002 / ADR-006).
FROZEN_PREFIXES = (
    "bot/",
    "dashboard/",
    "scheduler/",
    "database/",
    "ledger/",
    ".github/workflows/",
)

# Implementation areas where a missing test file is worth flagging (CLAUDE.md).
TESTED_PREFIXES = ("bot/", "scripts/", "analytics/", "backtest/", "sentinel_engine/")

# Strategy / risk / ML code: the quant-reviewer pass applies before commit.
QUANT_PREFIXES = ("bot/strategy/", "bot/risk/", "scripts/train_model.py")

# Changes that move money or limits: route to the risk-officer while editing.
RISK_PREFIXES = ("bot/risk/", "bot/execution/", "bot/capital/")

# Changes to data sources, storage, and sync: route to the data-engineer.
DATA_PREFIXES = (
    "bot/db/", "database/", "bot/_main_db.py", "bot/_main_reconcile.py",
    "bot/strategy/features.py", "bot/strategy/macro.py", "bot/strategy/sentiment.py",
    "bot/strategy/reddit_sentiment.py", "bot/trust_ledger/",
)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit"}

# Standing instruction: every change is a recorded decision, not a silent action.
DECISION_REMINDER = (
    "DECISION LOG: in your next reply state DECIDED / WHY / ROLE for this edit "
    "(which role approved it: architect, developer, ml-expert or stock-strategist)."
)


def _rel(file_path: str, root: Path) -> str | None:
    """Project-relative POSIX path, or None when the file is outside the project."""
    path = Path(file_path)
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _has_test(rel: str, root: Path) -> bool:
    stem = Path(rel).stem
    if stem == "__init__":
        return True
    tests = root / "tests"
    if not tests.is_dir():
        return False
    if any(tests.rglob(f"test*{stem}*.py")):
        return True
    # A test file named for something else still counts if it exercises this module.
    for test_file in tests.rglob("test*.py"):
        try:
            if stem in test_file.read_text(encoding="utf-8"):
                return True
        except (OSError, UnicodeDecodeError):
            continue
    return False


def _context(event: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _pre(rel: str) -> dict | None:
    if not rel.startswith(FROZEN_PREFIXES):
        return None
    reason = (
        f"{rel} is in a path project memory marks FROZEN (ADR-001 / ADR-002 / ADR-006). "
        "Confirm an ADR permits this edit before approving."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }


def _post(rel: str, root: Path) -> dict | None:
    notes: list[str] = []
    if rel.endswith(".py") and (root / rel).is_file():
        notes.extend(_python_notes(rel, root))
    notes.append(DECISION_REMINDER)
    return _context("PostToolUse", "edit_guard:\n- " + "\n- ".join(notes))


def _python_notes(rel: str, root: Path) -> list[str]:
    path = root / rel
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"could not read {rel}: {exc}"]

    notes: list[str] = []
    try:
        ast.parse(source, filename=rel)
    except SyntaxError as exc:
        notes.append(f"SYNTAX ERROR {rel}:{exc.lineno}: {exc.msg}. Fix before continuing.")

    line_count = len(source.splitlines())
    if line_count > MAX_LINES:
        notes.append(f"{rel} is {line_count} lines; CLAUDE.md caps files at {MAX_LINES}. Split it.")

    needs_test = rel.startswith(TESTED_PREFIXES) and not rel.startswith("tests/")
    if needs_test and not _has_test(rel, root):
        notes.append(f"No test file found for {rel}. CLAUDE.md requires tests with every implementation change.")

    if rel.startswith(QUANT_PREFIXES):
        notes.append(f"{rel} is strategy/risk/ML code: consult the quant-reviewer agent before committing.")
    if rel.startswith(RISK_PREFIXES):
        notes.append(f"{rel} changes money or limits: the risk-officer must approve (it can veto).")
    if rel.startswith(DATA_PREFIXES):
        notes.append(f"{rel} touches data or storage: the data-engineer must check sync, writes, and point-in-time safety.")

    return notes


def evaluate(payload: dict, root: Path) -> dict | None:
    """Return the hook response for one tool event, or None for silence."""
    if payload.get("tool_name") not in EDIT_TOOLS:
        return None
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(raw, str) or not raw:
        return None
    rel = _rel(raw, root)
    if rel is None:
        return None
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        return _pre(rel)
    if event == "PostToolUse":
        return _post(rel, root)
    return None


def main(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        payload = json.load(stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    try:
        result = evaluate(payload, root)
    except Exception as exc:  # fail open: a hook bug must never wedge editing
        sys.stderr.write(f"edit_guard error: {exc}\n")
        return 0
    if result:
        json.dump(result, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
