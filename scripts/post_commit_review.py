"""PostToolUse hook: run after `git commit`. Runs deterministic lint on the committed
Python files, then tells Claude (via hook context) which reviews to run on this commit.

Claude receives the output in the same turn and acts on it. No human step is needed.

Input: hook JSON on stdin (ignored). Output: hook JSON on stdout.
Never fails the commit: any error is reported as context, not raised.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Files whose change alters what the bot trades or how much it risks. These get a
# quant-reviewer pass in addition to the code review that runs on every commit.
RISK_PATHS = (
    "bot/strategy/",
    "bot/risk/",
    "bot/_main_cycle.py",
    "bot/_main_positions.py",
    "bot/_main_prep.py",
    "bot/main.py",
    "bot/capital/",
    "scripts/train_model.py",
    "config.py",
)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout


def _changed_files() -> list[str]:
    out = _git("show", "--name-only", "--pretty=format:", "HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _lint(py_files: list[str]) -> str:
    if not py_files:
        return ""
    # Unused imports/variables and undefined names only: the mechanical issues that
    # code review kept repeating. Style is not enforced here.
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F401,F841,F811,F821", "--no-cache", *py_files],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        return "ruff (F401/F841/F811/F821): clean"
    return "ruff findings:\n" + (result.stdout or result.stderr).strip()


def main() -> int:
    try:
        files = _changed_files()
        py_files = [f for f in files if f.endswith(".py") and Path(f).exists()]
        risky = [f for f in files if any(f.startswith(p) or f == p for p in RISK_PATHS)]

        lines = [f"Post-commit checks for {_git('rev-parse', '--short', 'HEAD').strip()}:"]
        lines.append(_lint(py_files))
        lines.append("Code review (every commit): run /code-review on HEAD and fix confirmed findings.")
        if risky:
            lines.append(
                "Risk-path change (" + ", ".join(risky) + "): run the quant-reviewer agent on "
                "`git diff HEAD~1..HEAD`. Fix confirmed findings before the next push."
            )
        context = "\n".join(lines)
    except Exception as exc:  # the hook must never block the workflow
        context = f"Post-commit review hook could not run: {exc}"

    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
