"""Static check: no undefined names (ruff F821) anywhere in bot/dashboard/database.

Added 2026-07-27 after finding bot/main.py::run() referenced an undefined
`daily_start` local (should have been captured from `rs.daily_start` before
the anchor-fill ran) — a NameError on every single cycle, silently caught by
run_loop()'s broad except-and-continue, that had halted all live trading
for 3+ days before being noticed. Two more instances of the same bug class
(undefined `_DB`, undefined `_logger`) turned up in the same sweep, both
inside exception handlers that swallowed the resulting NameError instead of
running the intended fallback logic. None of these were reachable by normal
unit tests since they only fire on specific runtime code paths (first cycle
of the day; a benchmark/alpha calc failing) -- a static AST check catches
the whole class immediately regardless of which path is exercised.
"""
import subprocess
import sys

import pytest


def test_no_undefined_names_in_source():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "bot/", "dashboard/", "database/", "--select", "F821"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        pytest.skip("ruff not installed -- only present transitively via gradio, not a direct dependency")
    if result.returncode not in (0, 1):
        pytest.skip(f"ruff could not run (exit {result.returncode}): {result.stderr[:300]}")
    assert result.returncode == 0, (
        f"ruff found undefined name(s) -- these raise NameError at runtime, "
        f"often silently swallowed by a broad except block:\n{result.stdout}"
    )
