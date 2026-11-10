#!/usr/bin/env python3
"""Run a Bash-matcher hook only when the Bash command matches its pattern.

Why this exists: the per-hook `"if": "Bash(git commit*)"` filter in settings.json
was not reliably applied, so these hooks fired on every Bash call (lint, version
checks, grep). This gate does the matching itself, so non-matching commands cost
nothing and produce no output.

Usage (from settings.json):  python bash_gate.py <gate-name>
Hook JSON arrives on stdin; it is passed through to the gated script unchanged.
Fails open: any gate error exits 0 and never blocks the Bash command.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# gate name -> (regex matched against the Bash command, script argv relative to project root)
GATES = {
    "commit_pre": (r"\bgit commit\b", ["tests/requirements_tracker.py"]),
    "commit_post": (r"\bgit commit\b", ["scripts/post_commit_review.py"]),
    "push_pre": (r"\bgit push\b", ["scripts/arch_review.py", "--diff"]),
}


def select(gate: str, command: str) -> list[str] | None:
    """Return the argv to run for this gate and command, or None when it should not run."""
    spec = GATES.get(gate)
    if spec is None or not isinstance(command, str):
        return None
    pattern, argv = spec
    return argv if re.search(pattern, command) else None


def main(argv: list[str], raw: str, root: Path) -> int:
    if len(argv) != 2:
        return 0
    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    script_argv = select(argv[1], command)
    if script_argv is None:
        return 0
    subprocess.run([sys.executable, *script_argv], input=raw, text=True, cwd=root, timeout=120)
    return 0


if __name__ == "__main__":
    try:
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
        sys.exit(main(sys.argv, sys.stdin.read(), root))
    except Exception as exc:  # fail open
        sys.stderr.write(f"bash_gate error: {exc}\n")
        sys.exit(0)
