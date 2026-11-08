import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Prevent bot/main.py from adding the trading.log file sink during test collection.
# bot/main.py guards logger.add() with this env var; setting it here before any
# bot import ensures tests never write to logs/trading.log.
os.environ.setdefault("_BOT_LOG_HANDLER_ADDED", "1")


def make_ohlcv(n: int = 270, seed: int = 42) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame with enough rows for all indicators including 252-bar momentum."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    close = np.clip(close, 1, None)
    high = close + np.abs(rng.normal(0, 0.3, n))
    low = close - np.abs(rng.normal(0, 0.3, n))
    low = np.clip(low, 0.01, None)
    open_ = close + rng.normal(0, 0.2, n)
    volume = np.abs(rng.normal(10000, 1000, n)) + 100
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


@pytest.fixture
def ohlcv():
    return make_ohlcv()


@pytest.fixture(autouse=True)
def _isolate_default_dashboard_db(tmp_path, monkeypatch):
    """dashboard.data.get_db_conn() falls back to the relative 'trades.db', which
    sqlite3.connect creates in the repo root whenever a test reads it unpatched.
    Redirect that default for every test so the suite never leaks a root file."""
    try:
        import dashboard.data as _dd
    except ImportError:
        return
    monkeypatch.setattr(_dd, "DB_PATH", str(tmp_path / "default_trades.db"))


@pytest.fixture(autouse=True)
def _isolate_scheduler_dbs(tmp_path, monkeypatch):
    """scheduler modules bind their default db_path at import time, so no-argument
    calls from the dashboard always open the cwd-relative 'trades.db'. Redirect
    each module's _conn default to a temp file for every test."""
    import importlib
    temp_db = str(tmp_path / "scheduler_test.db")
    for mod_name in ("scheduler.session_manager", "scheduler.health_monitor"):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        real_conn = mod._conn

        def _redirected(db_path=None, _real=real_conn):
            if db_path in (None, "trades.db"):
                db_path = temp_db
            return _real(db_path)

        monkeypatch.setattr(mod, "_conn", _redirected)


# ADR-081 step 1: model-driven entries are suspended in production (config.MODEL_ENTRIES_ENABLED).
# Entry-path tests exercise the gates behind that switch, so they run with entries enabled.
# A test marked `model_entries_default` keeps the production default and checks the suspension.
@pytest.fixture(autouse=True)
def _enable_model_entries_for_gate_tests(request, monkeypatch):
    if request.node.get_closest_marker("model_entries_default"):
        return
    import bot._main_cycle as _mc
    monkeypatch.setattr(_mc, "MODEL_ENTRIES_ENABLED", True)


def pytest_configure(config):
    config.addinivalue_line("markers", "model_entries_default: keep the production MODEL_ENTRIES_ENABLED default")
