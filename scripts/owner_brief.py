#!/usr/bin/env python3
"""Plain-English owner brief. Prints a short status with no model tokens.

Usage: python scripts/owner_brief.py
Reads the cached health summary, recent commits, uncommitted-file count, and ADRs still
Proposed. Never writes anything. Fails soft: a missing source prints a note, not a crash.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

FORWARD_TEST_REVIEW = date(2027, 11, 7)  # ADR-082, pre-registered; do not move
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))

import session_health  # noqa: E402  (reuses the cached-summary reader)

STATUS_PROPOSED = re.compile(r"\*\*Status:\*\*\s*Proposed")


def build_brief(health_lines: list[str], commits: list[str], dirty_count: int,
                proposed: list[str], today: date) -> str:
    days_left = (FORWARD_TEST_REVIEW - today).days
    out = ["OWNER BRIEF", "", "Health (checked weekly):"]
    if health_lines:
        out += [f"  {line}" for line in health_lines]
    else:
        out.append("  no health report yet: python scripts/hooks/session_health.py --refresh")
    out += ["", "Recent work:"]
    out += [f"  {c}" for c in commits] if commits else ["  none found"]
    out += ["", f"Uncommitted files: {dirty_count}"]
    out += ["", f"Decisions waiting on you ({len(proposed)} proposed ADRs):"]
    out += [f"  {name}" for name in proposed[:10]] or ["  none"]
    out += ["", f"Forward-test verdict: {FORWARD_TEST_REVIEW.isoformat()} "
                f"({days_left} days away). Its rules are fixed; do not change them."]
    return "\n".join(out)


def _git(args: list[str]) -> list[str]:
    try:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line for line in done.stdout.splitlines() if line.strip()]


def _proposed_adrs() -> list[str]:
    names = []
    for path in sorted((ROOT / "docs" / "decisions").glob("ADR-*.md")):
        try:
            head = path.read_text(encoding="utf-8").splitlines()[:15]
        except (OSError, UnicodeDecodeError):
            continue
        if any(STATUS_PROPOSED.search(line) for line in head):
            names.append(path.stem)
    return names


def main() -> int:
    report = ROOT / session_health.REPORT_RELPATH
    cached = session_health.read_cached_summary(report)
    health = cached[1] if cached else []
    commits = _git(["log", "-5", "--format=%h %s"])
    dirty = len(_git(["status", "--porcelain"]))
    print(build_brief(health, commits, dirty, _proposed_adrs(), date.today()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
