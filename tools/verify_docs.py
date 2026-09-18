#!/usr/bin/env python3
"""Documentation drift detector.

Exists because of a real incident (2026-09-18): docs/ARCHITECTURE.md claimed
"535 tests across 28 test files" and "8 tables" in trades.db while the real
numbers were 1,441/69 and 21 -- and nobody noticed until a resume review
caught it, which then turned up a dozen more of the same pattern across
other root docs (wrong retrain cadence, wrong SQLite table counts, a
confidence-gate table that quietly contradicted the actual enforced code).

This script does NOT understand English. It can't tell you a paragraph is
wrong. What it CAN do, cheaply and repeatably, is catch the two mechanical
patterns that caused every one of those incidents:

  1. A markdown/backtick reference to a file that no longer exists at that
     path (catches dead links like the LICENSE incident, moved/renamed
     files, and typos).
  2. A parenthetical "(N lines)" annotation next to a file path that no
     longer matches that file's real line count.

It also SURFACES (does not verify -- that needs a human) every sentence
matching "<number> tests/files/tables/modules/ADRs/documents" so a reviewer
can eyeball them for drift instead of relying on remembering to check.

Usage:
    python tools/verify_docs.py                  # scan all of docs/ + root *.md
    python tools/verify_docs.py --path docs/ARCHITECTURE.md   # scan one file
    python tools/verify_docs.py --json            # machine-readable output
    python tools/verify_docs.py --no-surface      # skip the numeric-claims list (faster, CI-friendly)

Exit code: 1 if any broken reference or line-count mismatch was found, 0
otherwise. The surfaced numeric-claims list never affects the exit code --
it's for human review, not an automated gate, since many of those numbers
are legitimately historical (dated changelog entries) rather than current
claims.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Backtick-quoted things that look like a repo-relative path: at least one
# '/' or a recognizable extension, no spaces, no URL scheme.
_PATH_IN_BACKTICKS = re.compile(r"`([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+|[A-Za-z0-9_\-]+/[A-Za-z0-9_./\-]*)`")
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_LINE_COUNT_CLAIM = re.compile(
    r"`([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)`[^\n(]{0,40}\((\d[\d,]*)\s*lines?\)"
)
_NUMERIC_CLAIM = re.compile(
    r"(?<![\d,-])\b(\d{1,3}(?:,\d{3})*)\s+(tests?|test functions?|files?|tables?|modules?|ADRs?|"
    r"documents?|component modules?|screens?)\b",
    re.IGNORECASE,
)

# Directories never worth treating as "the whole repo" for path-existence checks.
_SKIP_DIR_NAMES = {
    "__pycache__", ".git", "node_modules", ".venv", "venv", ".pytest_cache",
    ".ruff_cache", "data", "backups", "logs", ".playwright-mcp",
}

_basename_index: dict[str, list[Path]] | None = None


def _build_basename_index() -> dict[str, list[Path]]:
    """Repo-wide basename -> path(s) index, built once and cached. Backs the
    fallback for bare filenames in prose (e.g. `risk_manager.py` with no
    directory) -- most doc references are written this way, and it would be
    pure noise to demand every mention carry its full path. A bare name is
    only reported broken if NOTHING in the repo has that basename."""
    global _basename_index
    if _basename_index is not None:
        return _basename_index
    index: dict[str, list[Path]] = {}
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in _SKIP_DIR_NAMES for part in p.parts):
            continue
        index.setdefault(p.name, []).append(p)
    _basename_index = index
    return index


def _iter_md_files(start: Path) -> list[Path]:
    if start.is_file():
        return [start]
    return sorted(
        p for p in start.rglob("*.md")
        if not any(part in _SKIP_DIR_NAMES for part in p.parts)
    )


# Design docs for these two packages routinely shorthand their own internal
# layout as a bare top-level name -- "ui/", "services/", "adapters/" -- since
# the doc's own surrounding prose already establishes which package is meant.
# Both packages really do have all of these as real subdirectories; try each
# before giving up on an unqualified directory-looking reference.
_KNOWN_APP_ROOTS = (
    "applications/trading_intelligence", "applications/wealth_intelligence", "sentinel_engine", "bot",
)


def _resolve_candidate(raw: str, doc_dir: Path) -> Path | None:
    """Try the reference as repo-root-relative, then as relative to the doc's
    own directory, then (for a bare filename with no directory component) as
    a repo-wide basename lookup, then (for a bare top-level directory name)
    nested under each of _KNOWN_APP_ROOTS. Returns the resolved path if any
    of those exist, else None."""
    raw = raw.split("#")[0].strip()
    if not raw or raw.startswith(("http://", "https://", "mailto:")):
        return None
    # docs/DOCUMENT_INDEX.md's own convention cites sibling docs relative to
    # docs/ itself (e.g. "platform/AARA_ARCHITECTURE_AUTHORITY.md") -- try
    # that base too, not just repo-root and the citing doc's own directory.
    for base in (ROOT, doc_dir, ROOT / "docs"):
        candidate = (base / raw).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            continue
        if candidate.exists():
            return candidate
    if "/" not in raw:
        matches = _build_basename_index().get(raw)
        if matches:
            return matches[0]
    elif raw.count("/") <= 2:  # e.g. "ui/", "ui/decision_center/screen.py" -- not a deep repo path
        for app_root in _KNOWN_APP_ROOTS:
            candidate = (ROOT / app_root / raw).resolve()
            if candidate.exists():
                return candidate
    return None


_RUNTIME_DATA_EXTENSIONS = (".db", ".duckdb", ".log")


def _looks_like_real_path(raw: str) -> bool:
    """Filter out backtick spans that are code identifiers, config keys, or
    CLI flags rather than file paths -- e.g. `MAX_POSITION_PCT`, `--update`,
    `get_sharpe_ratio()`. A real path reference in this repo's docs always
    contains a '/' or a known source extension."""
    if raw.startswith("-") or raw.endswith("()"):
        return False
    if "/" in raw:
        return True
    return bool(re.search(r"\.(py|md|txt|json|yml|yaml|db|toml|cfg|ini)$", raw))


def _is_expected_runtime_artifact(raw: str) -> bool:
    """data/ (per .gitignore: raw/, processed/, trust_ledger.db, HALT_TRADING,
    etc.) and any .db/.duckdb/.log file are created at runtime, not checked
    into git -- their absence in a fresh checkout is correct, not a broken
    reference."""
    path_part = raw.split("#")[0].strip()
    if path_part.startswith("data/"):
        return True
    return path_part.endswith(_RUNTIME_DATA_EXTENSIONS)


def _is_known_archived_path(raw: str) -> bool:
    """sentinel/ (the pre-ADR-001 scaffold, distinct from the real, current
    sentinel_engine/ package) was archived to archive/sentinel_phase2a_
    scaffold/ per ADR-008. ~9 product/platform design docs cite
    sentinel/frontend/... paths as historical evidence and now carry an
    explicit note saying so (added 2026-09-18) -- flagging the same known,
    already-explained archival on every run is noise, not signal. This does
    NOT cover sentinel_engine/, which is a real, current, unarchived package."""
    path_part = raw.split("#")[0].strip()
    return path_part == "sentinel" or path_part.startswith("sentinel/")


def check_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    doc_dir = path.parent
    broken_refs: list[str] = []
    line_mismatches: list[str] = []
    numeric_claims: list[str] = []

    seen_refs: set[str] = set()
    for m in _PATH_IN_BACKTICKS.finditer(text):
        raw = m.group(1)
        if (not _looks_like_real_path(raw) or raw in seen_refs
                or _is_expected_runtime_artifact(raw) or _is_known_archived_path(raw)):
            continue
        seen_refs.add(raw)
        if _resolve_candidate(raw, doc_dir) is None:
            broken_refs.append(raw)

    for m in _MD_LINK.finditer(text):
        target = m.group(2)
        if target in seen_refs or _is_expected_runtime_artifact(target) or _is_known_archived_path(target):
            continue
        seen_refs.add(target)
        if _resolve_candidate(target, doc_dir) is None:
            broken_refs.append(target)

    for m in _LINE_COUNT_CLAIM.finditer(text):
        rel_path, claimed = m.group(1), int(m.group(2).replace(",", ""))
        resolved = _resolve_candidate(rel_path, doc_dir)
        if resolved is None:
            continue  # already reported as a broken ref above
        actual = len(resolved.read_text(encoding="utf-8", errors="replace").splitlines())
        if actual != claimed:
            line_mismatches.append(f"{rel_path}: doc says {claimed} lines, actual is {actual}")

    for m in _NUMERIC_CLAIM.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        numeric_claims.append(f"L{line_no}: \"{m.group(0)}\"")

    return {
        "broken_refs": broken_refs,
        "line_mismatches": line_mismatches,
        "numeric_claims": numeric_claims,
    }


_TECH_DEBT_PATH = ROOT / "docs" / "TECHNICAL_DEBT.md"
_TEST_PATH_IN_ROW = re.compile(r"`([A-Za-z0-9_./\-]*tests?/[A-Za-z0-9_./\-]*test_[A-Za-z0-9_./\-]+\.py)`")
_FAIL_LANGUAGE = re.compile(r"\bfail(ing|s|ed)?\b", re.IGNORECASE)


def check_active_debt_freshness() -> list[str]:
    """Exists because of a real incident (2026-09-18): TD-014 in TECHNICAL_DEBT.md
    described 4 failing tests. The tests got fixed and the fix was verified in the
    same session -- but the TECHNICAL_DEBT.md row was never updated, because
    "fix the tests" and "update the row describing the tests" were treated as two
    separate tasks. It sat in Active Debt, describing a problem that no longer
    existed, until a reviewer cited that exact row back at us.

    This scans only the Active Debt table (never Resolved -- a resolved row is
    allowed to describe a past failure). For any row that both names a real test
    file and uses fail-language ("failing", "fails", "failed"), it actually runs
    those tests. A row claiming failure whose named tests now pass is almost
    certainly the same stale-debt-entry bug recurring, and is reported as such."""
    if not _TECH_DEBT_PATH.exists():
        return []
    text = _TECH_DEBT_PATH.read_text(encoding="utf-8", errors="replace")
    if "## Active Debt" not in text:
        return []
    active_section = text.split("## Active Debt", 1)[1].split("## Resolved Debt", 1)[0]

    findings: list[str] = []
    for line in active_section.splitlines():
        if not line.strip().startswith("|") or not _FAIL_LANGUAGE.search(line):
            continue
        if re.search(r"\bflak(y|iness|es)?\b|\bintermitten(t|tly)\b", line, re.IGNORECASE):
            continue  # self-describes as non-deterministic; one run can't confirm or deny it
        test_paths = sorted(set(_TEST_PATH_IN_ROW.findall(line)))
        resolved_paths = [p for p in (_resolve_candidate(p, ROOT) for p in test_paths) if p is not None]
        if not resolved_paths:
            continue
        row_id = line.strip().split("|")[1].strip() if line.strip().startswith("|") else "?"
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *[str(p) for p in resolved_paths], "-q", "--tb=no"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        if result.returncode == 0:
            summary = (result.stdout.strip().splitlines() or [""])[-1]
            findings.append(
                f"{row_id}: claims failing tests in {test_paths}, but they pass now ({summary}) "
                f"-- this Active Debt row is likely stale, verify and move it to Resolved"
            )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default="docs", help="File or directory to scan (default: docs/)")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    ap.add_argument("--no-surface", action="store_true", help="Skip the numeric-claims surfacing list")
    ap.add_argument("--check-debt", action="store_true",
                     help="Also run tests named in TECHNICAL_DEBT.md's Active Debt rows that claim "
                          "failures, and flag any that pass now (stale debt entry). Slower -- runs "
                          "real pytest processes.")
    args = ap.parse_args()

    if args.check_debt:
        debt_findings = check_active_debt_freshness()
        if debt_findings:
            print("-- docs/TECHNICAL_DEBT.md (Active Debt freshness check) --")
            for f in debt_findings:
                print(f"  STALE DEBT ENTRY  {f}")
            print()
        else:
            print("No Active Debt rows claiming test failures were contradicted by a real test run.\n")

    target = (ROOT / args.path).resolve()
    files = _iter_md_files(target)
    if not files:
        print(f"No markdown files found under {target}", file=sys.stderr)
        return 1

    report: dict[str, dict] = {}
    any_hard_failure = False
    for f in files:
        result = check_file(f)
        rel = str(f.relative_to(ROOT))
        if result["broken_refs"] or result["line_mismatches"] or (result["numeric_claims"] and not args.no_surface):
            report[rel] = result
        if result["broken_refs"] or result["line_mismatches"]:
            any_hard_failure = True

    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if any_hard_failure else 0

    n_broken = sum(len(r["broken_refs"]) for r in report.values())
    n_mismatch = sum(len(r["line_mismatches"]) for r in report.values())
    n_claims = sum(len(r["numeric_claims"]) for r in report.values())
    print(f"Scanned {len(files)} markdown files under {args.path}\n")

    for rel, result in report.items():
        if not (result["broken_refs"] or result["line_mismatches"] or result["numeric_claims"]):
            continue
        print(f"-- {rel} --")
        for ref in result["broken_refs"]:
            print(f"  BROKEN REF     `{ref}` does not exist")
        for mm in result["line_mismatches"]:
            print(f"  LINE MISMATCH  {mm}")
        if not args.no_surface:
            for claim in result["numeric_claims"]:
                print(f"  numeric claim  {claim}  (not auto-verified -- eyeball this)")
        print()

    print(f"Summary: {n_broken} broken reference(s), {n_mismatch} line-count mismatch(es), "
          f"{n_claims} numeric claim(s) surfaced for review.")
    if any_hard_failure:
        print("FAILED — fix the broken references / line-count mismatches above.")
    else:
        print("No broken references or line-count mismatches found. "
              "Numeric claims above still need a human's eyes — this tool cannot verify prose.")
    return 1 if any_hard_failure else 0


if __name__ == "__main__":
    sys.exit(main())
