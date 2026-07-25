"""Full-app import smoke test.

Unit tests call individual render_* functions directly and never import
dashboard/app.py as a whole, so they never execute registry.validate() —
the check that every registered ComponentSpec was actually mounted to a
Gradio widget. A key mismatch between register(ComponentSpec(key=...)) and
registry.mount(key, ...) passes every unit test and every local smoke test,
then crashes the entire Space at startup (RuntimeError, HTTP 503) the moment
someone actually imports the real app.py — which is exactly what happened
with 'trade_journal' vs 'trade_journal_out' (2026-07-25): the mismatch was
invisible to CI/local checks and only surfaced as a live 503 on HuggingFace
Spaces, which runs the exact code path this test exercises.

Runs in a subprocess (not an in-process import) because dashboard/app.py has
module-level side effects — a ThreadPoolExecutor pre-render pass and a
one-time ComponentSpec registry — that must not run twice in, or leak into,
the rest of the test session.
"""
from __future__ import annotations

import subprocess
import sys

import gradio as gr
import pytest


@pytest.mark.skipif(
    not hasattr(gr, "Timer"),
    reason=(
        "Local gradio build predates gr.Timer (needs gradio>=5.0, which needs "
        "Python>=3.10 — see docs/DEPENDENCIES.md). CI installs the real pin "
        "from requirements.txt; this test is authoritative there."
    ),
)
def test_dashboard_app_imports_without_crashing():
    """Full import of dashboard.app must succeed — catches registry key mismatches,
    missing mounts, and any other module-level wiring error that unit tests can't see
    because they never construct the actual gr.Blocks app."""
    result = subprocess.run(
        [sys.executable, "-c", "import dashboard.app"],
        cwd=".",
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        "`import dashboard.app` failed — this is exactly what crashes the live "
        "HuggingFace Space with a 503 on startup.\n\n"
        f"--- stdout ---\n{result.stdout}\n\n--- stderr ---\n{result.stderr}"
    )
