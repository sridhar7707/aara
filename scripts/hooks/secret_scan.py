#!/usr/bin/env python3
"""Pre-commit secret scan for staged changes. Blocks the commit on a finding.

Installed as .git/hooks/pre-commit (see docs in the owner brief). It reads only the staged
diff, so unstaged work is never inspected. It reports the file, line, and kind of secret,
never the secret itself. Fails closed on a scan error, since a leaked key is costly.

Usage: python scripts/hooks/secret_scan.py          (exit 1 = blocked)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Hugging Face token", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("API secret key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),  # \b: "risk-management..." is not a key
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("hard-coded secret", re.compile(r"""(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["'][^"'\s]{16,}["']""")),
]
ENV_FILE_NAMES = {".env"}


def scan_line(text: str) -> list[str]:
    return [kind for kind, pattern in PATTERNS if pattern.search(text)]


def findings_in_diff(diff_text: str) -> list[tuple[str, int, str]]:
    """Return (file, line number, kind) for each added line that matches a pattern."""
    results: list[tuple[str, int, str]] = []
    path = "?"
    new_line = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else raw[4:]
        elif raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            new_line = int(match.group(1)) if match else 0
        elif raw.startswith("+"):
            for kind in scan_line(raw[1:]):
                results.append((path, new_line, kind))
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1
    return results


def env_files(names: list[str]) -> list[str]:
    return [n for n in names if Path(n).name in ENV_FILE_NAMES]


def _git(args: list[str]) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=60, check=True)
    return done.stdout


def main() -> int:
    try:
        diff = _git(["diff", "--cached", "-U0"])
        names = _git(["diff", "--cached", "--name-only"]).splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"secret_scan: could not read staged changes ({exc}). Commit blocked.\n")
        return 1
    hits = findings_in_diff(diff)
    blocked_env = env_files(names)
    if not hits and not blocked_env:
        return 0
    sys.stderr.write("SECRET SCAN: commit blocked.\n")
    for path, line, kind in hits:
        sys.stderr.write(f"  {path}:{line}  {kind}\n")
    for name in blocked_env:
        sys.stderr.write(f"  {name}  environment file must not be committed\n")
    sys.stderr.write("Remove the secret (use an environment variable), unstage the file, then commit again.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
