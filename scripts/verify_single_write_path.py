"""Phase 1A -- single-write-path verification, per phase1a_requirements.md
Section 14 ("Single write path (verified, not assumed)") and
phase0_decisions.md #17/#18.

Proves, not assumes, two things:

1. decision_log's write path is unreachable from the automated live trading
   cycle (bot/main.py -> bot/_main_*.py) and has received zero new rows
   since the cutover (commit dfa567a, committed 2026-07-28T20:54:30-05:00)
   -- checked directly against trades.db, not inferred from the Trust
   Ledger looking populated.
2. Exactly one decision-creation path exists end to end: Scanner
   (bot/_main_candidates.py) -> Ledger (bot/trust_ledger/decisions.py) ->
   Paper Execution (bot/trust_ledger/outcomes.py) -- verified by counting
   production callers of each stage's write function.

Read-only. Re-run against the accumulated 30-day trades.db before Phase 1A
acceptance is signed off (phase1a_requirements.md Section 14's own words:
"before Phase 1A acceptance is formally signed off, this check must be
automated and persisted as a script that can be re-run against the
accumulated 30-day database").

Structured like docs/architecture/verify_phase0_claims.py: check(name,
condition, detail) prints PASS/FAIL and the final tally is the verdict.
"""
from __future__ import annotations

import ast
import os
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CUTOVER_COMMIT = "dfa567ad79df5f05174fdc0439470129b1330508"
CUTOVER_TIMESTAMP = "2026-07-28T20:54:30-05:00"  # commit dfa567a's committer date

TRADES_DB_PATH = REPO_ROOT / "trades.db"

# tests/ (fixtures call these directly), docs/ (frozen Phase 0 design-session
# reference copies), scripts/ (offline tooling, not the live trading cycle,
# confirmed empty of these call sites above) are not part of what runs when
# the bot actually trades.
_EXCLUDED_DIRS = {"tests", "docs", "scripts", "__pycache__", ".git", "node_modules"}

results: dict[str, tuple[bool, str]] = {}


def check(name: str, condition: bool, detail: str = "") -> None:
    results[name] = (bool(condition), detail)
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


def _iter_py_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.endswith(".py"):
                yield Path(dirpath) / f


def _parsed_files():
    """Parse every live-path source file once. Yields (posix-relative-path,
    ast.Module). AST-based, not line/regex-based, so mentions of a function
    name inside a comment or docstring (e.g. "...as approve_decision(), so
    a row can only land here via...") can never masquerade as a real call."""
    for path in _iter_py_files():
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (UnicodeDecodeError, OSError, SyntaxError):
            continue
        yield path.relative_to(REPO_ROOT).as_posix(), tree


def _callers_of(fn_name: str) -> list[tuple[str, int]]:
    """Every real Call node invoking fn_name (as a bare name or as an
    attribute, e.g. decisions.write_decision_event(...)), across all parsed
    files -- never matches the function's own `def` line, a comment, or a
    docstring, since those aren't Call nodes."""
    hits = []
    for relpath, tree in _parsed_files():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name == fn_name:
                hits.append((relpath, node.lineno))
    return hits


def _sql_write_sites(table: str) -> list[tuple[str, int, str]]:
    """Every string constant containing an INSERT/UPDATE against `table`,
    across all parsed files. AST string constants merge implicit line
    continuations, so multi-line SQL literals are seen whole."""
    rx = re.compile(rf"(INSERT INTO|UPDATE)\s+{re.escape(table)}\b")
    hits = []
    for relpath, tree in _parsed_files():
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if rx.search(node.value):
                    hits.append((relpath, node.lineno, node.value.strip()[:80]))
    return hits


def run_checks() -> None:
    # ============================================================
    # 1. decision_log write call sites must not be reachable from the
    #    automated live trading cycle.
    # ============================================================
    write_sites = _sql_write_sites("decision_log")
    live_cycle_sites = [h for h in write_sites if re.match(r"bot/(main\.py|_main_\w+\.py)$", h[0])]
    check(
        "1. decision_log has no write call sites in the live trading cycle",
        not live_cycle_sites,
        f"{len(write_sites)} write call site(s) total in non-test/docs/scripts source; "
        + ("none inside bot/main.py or bot/_main_*.py" if not live_cycle_sites
           else f"found in live cycle: {live_cycle_sites}"),
    )

    # ============================================================
    # 2. The remaining decision_log writers (decision_service.create_decision,
    #    timeline.log_decision) are dead code: zero production callers.
    # ============================================================
    create_decision_callers = _callers_of("create_decision")
    log_decision_callers = _callers_of("log_decision")
    check(
        "2. create_decision()/log_decision() (decision_log writers) have zero production callers",
        not create_decision_callers and not log_decision_callers,
        f"create_decision callers: {create_decision_callers or 'none'}; "
        f"log_decision callers: {log_decision_callers or 'none'}",
    )

    # ============================================================
    # 3. approve_decision()/reject_decision() are reachable only from the
    #    dashboard's human-click handler -- never the automated bot cycle.
    #    (They can only ever act on a WAITING_APPROVAL row, and check #2
    #    already proved nothing creates one anymore.)
    # ============================================================
    approve_callers = _callers_of("approve_decision")
    reject_callers = _callers_of("reject_decision")
    unexpected = [
        h for h in approve_callers + reject_callers
        if h[0] != "dashboard/components/pending_approvals.py"
    ]
    check(
        "3. approve_decision()/reject_decision() callers confined to the dashboard's human-click handler",
        not unexpected,
        f"unexpected callers outside dashboard/components/pending_approvals.py: {unexpected}"
        if unexpected else "only dashboard/components/pending_approvals.py calls these",
    )

    # ============================================================
    # 4. Exactly one production caller of each Trust Ledger write stage:
    #    Scanner -> Ledger -> Paper Execution is the only decision-creation
    #    path end to end.
    # ============================================================
    stages = [
        ("4a. Scanner", "record_candidate_evaluation_if_concluded", "bot/_main_candidates.py"),
        ("4b. Ledger", "write_decision_event", "bot/_main_trust_decisions.py"),
        ("4c. Paper Execution", "write_decision_outcome_event", "bot/_main_trust_decisions.py"),
    ]
    for label, fn_name, expected_file in stages:
        callers = _callers_of(fn_name)
        ok = len(callers) == 1 and callers[0][0] == expected_file
        check(
            f"{label} stage has exactly one production caller ({expected_file})",
            ok,
            str(callers),
        )

    # ============================================================
    # 5. decision_log has received zero new rows since the cutover commit --
    #    checked directly against the accumulated database, not inferred
    #    from the Trust Ledger looking populated.
    # ============================================================
    if not TRADES_DB_PATH.exists():
        check(
            "5. decision_log has zero rows written after cutover",
            False,
            f"trades.db not found at {TRADES_DB_PATH} -- cannot verify against real data; re-run once it exists",
        )
    else:
        con = sqlite3.connect(str(TRADES_DB_PATH))
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "decision_log" not in tables:
                check("5. decision_log has zero rows written after cutover", True,
                      "decision_log table does not exist in trades.db")
            else:
                post_cutover_count = con.execute(
                    "SELECT COUNT(*) FROM decision_log WHERE created_at > ?", (CUTOVER_TIMESTAMP,)
                ).fetchone()[0]
                check(
                    "5. decision_log has zero rows written after cutover",
                    post_cutover_count == 0,
                    f"{post_cutover_count} row(s) created after {CUTOVER_TIMESTAMP} "
                    f"(cutover commit {CUTOVER_COMMIT[:7]})",
                )
        finally:
            con.close()


def main() -> int:
    run_checks()
    print()
    n_pass = sum(1 for ok, _ in results.values() if ok)
    print(f"{n_pass}/{len(results)} claims verified")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
