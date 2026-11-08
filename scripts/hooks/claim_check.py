#!/usr/bin/env python3
"""PostToolUse hook: flags return promises in customer-facing text.

Only files under customer-facing paths are scanned. Prints a short warning and sends the
owner to the compliance-advisor. It never blocks an edit. Fails open.

Input: hook JSON on stdin. Output: hook JSON on stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edit_guard import EDIT_TOOLS, _rel  # noqa: E402  (shared path normalisation)

CUSTOMER_PREFIXES = ("PRODUCT.md", "README.md", "applications/", "docs/products/", "docs/aara/", "brand/")
TEXT_SUFFIXES = (".md", ".txt", ".html", ".py")
MAX_HITS = 5

CLAIM_PATTERNS = [
    (re.compile(r"\bguarantee[ds]?\b", re.I), "guarantee"),
    (re.compile(r"\brisk[- ]free\b", re.I), "risk-free"),
    (re.compile(r"\bno risk\b", re.I), "no risk"),
    (re.compile(r"\bwill (make|earn|double|grow|beat)\b", re.I), "will make/earn/double/grow/beat"),
    (re.compile(r"\bsure (win|thing|profit)\b", re.I), "sure win/thing/profit"),
    (re.compile(r"\bprofits? (every|always|for sure)\b", re.I), "profit every/always"),
    (re.compile(r"\b\d+(\.\d+)?\s*%\s*(returns?|profit|gains?)\b", re.I), "percent return claim"),
]


def find_claims(text: str) -> list[tuple[int, str, str]]:
    """Return (line_number, phrase, claim kind) for each suspicious line, capped at MAX_HITS."""
    hits: list[tuple[int, str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, kind in CLAIM_PATTERNS:
            match = pattern.search(line)
            if match:
                hits.append((number, match.group(0), kind))
                break
        if len(hits) >= MAX_HITS:
            break
    return hits


def evaluate(payload: dict, root: Path) -> dict | None:
    if payload.get("tool_name") not in EDIT_TOOLS:
        return None
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not isinstance(raw, str) or not raw:
        return None
    rel = _rel(raw, root)
    if rel is None or not rel.startswith(CUSTOMER_PREFIXES) or not rel.endswith(TEXT_SUFFIXES):
        return None
    path = root / rel
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    hits = find_claims(text)
    if not hits:
        return None
    lines = [f"{rel}:{n} '{phrase}' ({kind})" for n, phrase, kind in hits]
    context = ("CLAIM CHECK: possible return promise in customer-facing text:\n- "
               + "\n- ".join(lines)
               + "\nRemove it, or send it to the compliance-advisor before any release.")
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}


def main(stdin=None, stdout=None, root: Path | None = None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        payload = json.load(stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    project = root or Path(__file__).resolve().parents[2]
    try:
        result = evaluate(payload, project)
    except Exception as exc:  # fail open
        sys.stderr.write(f"claim_check error: {exc}\n")
        return 0
    if result:
        json.dump(result, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
