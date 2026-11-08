#!/usr/bin/env python3
"""SessionStart hook: lazy health check.

Runs the weekly health checks only when the last saved report is older than 7 days.
Injects a three-line summary into the session, not the full output, and points to
the full report file. Fails open: any error prints nothing.

Usage: python session_health.py            (hook mode, run from settings.json)
       python session_health.py --refresh  (force a new run now)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MAX_AGE_SECONDS = 7 * 24 * 3600
REPORT_RELPATH = Path("logs") / "health_latest.txt"  # logs/* is gitignored
SUMMARY_END = "---"  # marks where the saved summary ends and the full output begins

# Fixed commands (never taken from repo data). Same checks as before, run lazily.
CHECKS = [
    ["tests/ui_tester.py"],
    ["tests/requirements_tracker.py", "--status"],
    ["tools/verify_docs.py", "--path", "docs", "--no-surface"],
]

SUMMARY_PATTERNS = [
    r"Results: .*",
    r"Features: .*",
    r"Coverage: .*",
    r"\d+ broken reference\(s\).*",
]


def summarize(text: str) -> list[str]:
    """Pick the few status lines worth injecting into context."""
    lines: list[str] = []
    for pattern in SUMMARY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            lines.append(match.group(0).strip())
    return lines


def run_checks(root: Path) -> str:
    chunks = []
    for argv in CHECKS:
        try:
            done = subprocess.run([sys.executable, *argv], cwd=root, capture_output=True,
                                  text=True, timeout=120)
            chunks.append(f"$ {' '.join(argv)}\n{done.stdout}{done.stderr}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            chunks.append(f"$ {' '.join(argv)}\nFAILED TO RUN: {exc}")
    return "\n".join(chunks)


def write_report(report: Path, summary: list[str], output: str) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    report.write_text(f"# run {stamp}\n" + "\n".join(summary) + f"\n{SUMMARY_END}\n\n" + output,
                      encoding="utf-8")


def read_cached_summary(report: Path) -> tuple[float, list[str]] | None:
    """Return (age_seconds, summary lines) for a report on disk, else None."""
    if not report.is_file():
        return None
    age = time.time() - report.stat().st_mtime
    lines = report.read_text(encoding="utf-8").splitlines()
    summary: list[str] = []
    for line in lines[1:]:
        if line == SUMMARY_END:
            break
        summary.append(line)
    return age, [line for line in summary if line.strip()]


def build_context(root: Path, refresh: bool) -> str:
    report = root / REPORT_RELPATH
    cached = None if refresh else read_cached_summary(report)
    if cached is None or cached[0] > MAX_AGE_SECONDS:
        output = run_checks(root)
        write_report(report, summarize(output), output)
        summary = summarize(output)
        origin = "ran now"
    else:
        summary = cached[1]
        origin = f"cached {int(cached[0] // 86400)}d ago"
    body = "\n".join(f"- {line}" for line in summary) or "- no summary lines found"
    return (f"Health checks ({origin}):\n{body}\n"
            f"Full report: {REPORT_RELPATH.as_posix()}. Refresh: python scripts/hooks/session_health.py --refresh")


def main(argv: list[str], stdout=None) -> int:
    stdout = stdout or sys.stdout
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    context = build_context(root, refresh="--refresh" in argv)
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
              stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # fail open
        sys.stderr.write(f"session_health error: {exc}\n")
        sys.exit(0)
