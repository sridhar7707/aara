"""Tests for bot/execution/factory.py (Phase 1A Sprint 5)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot.execution.factory import get_executor  # noqa: E402
from bot.execution.alpaca_client import AlpacaClient  # noqa: E402
from bot.execution.paper_executor import PaperExecutor  # noqa: E402


def test_default_backend_is_alpaca_client(monkeypatch):
    monkeypatch.delenv("EXECUTION_BACKEND", raising=False)
    executor = get_executor()
    assert isinstance(executor, AlpacaClient)


def test_explicit_alpaca_paper_backend(monkeypatch):
    monkeypatch.setenv("EXECUTION_BACKEND", "alpaca_paper")
    executor = get_executor()
    assert isinstance(executor, AlpacaClient)


def test_paper_ledger_backend_returns_paper_executor(monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_BACKEND", "paper_ledger")
    monkeypatch.chdir(tmp_path)  # PaperExecutor's default db_path is relative
    (tmp_path / "data").mkdir()
    executor = get_executor()
    assert isinstance(executor, PaperExecutor)


def test_live_backend_raises_if_base_url_still_paper(monkeypatch):
    monkeypatch.setenv("EXECUTION_BACKEND", "live")
    import bot.execution.factory as factory_mod
    monkeypatch.setattr(factory_mod, "ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    with pytest.raises(ValueError, match="ALPACA_BASE_URL still points"):
        get_executor()


def test_live_backend_succeeds_when_base_url_is_live(monkeypatch):
    monkeypatch.setenv("EXECUTION_BACKEND", "live")
    import bot.execution.factory as factory_mod
    monkeypatch.setattr(factory_mod, "ALPACA_BASE_URL", "https://api.alpaca.markets")
    executor = get_executor()
    assert isinstance(executor, AlpacaClient)


def test_unknown_backend_raises():
    os.environ["EXECUTION_BACKEND"] = "something_made_up"
    try:
        with pytest.raises(ValueError, match="Unknown EXECUTION_BACKEND"):
            get_executor()
    finally:
        del os.environ["EXECUTION_BACKEND"]


def test_all_construction_call_sites_use_get_executor_not_alpaca_client_directly():
    """Structural regression guard, same rationale as the Sprint 3 fix for
    _handle_exits and the Sprint 4 fix for record_risk_evaluation_safe: a
    call site quietly left on direct AlpacaClient() construction bypasses
    get_executor() (and EXECUTION_BACKEND) entirely, invisibly to every
    test that only exercises get_executor() itself. bot/main.py,
    bot/_main_runner.py (both call sites), and scheduler/startup_job.py
    were the known real construction sites as of Sprint 5 -- startup_job's
    _verify_broker() is a deliberate, documented exception (see its own
    comment) since its whole job is verifying the real Alpaca connection."""
    import inspect
    import bot.main as main_mod
    import bot._main_runner as runner_mod

    assert "get_executor(" in inspect.getsource(main_mod.run)
    assert "get_executor(" in inspect.getsource(runner_mod.end_of_day_summary)
    assert "get_executor(" in inspect.getsource(runner_mod.run_loop)
