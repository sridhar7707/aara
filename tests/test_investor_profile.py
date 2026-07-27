"""Tests for dashboard.components.settings's Investor Profile (Phase 5 Step 11)."""
import pytest

import dashboard.data as data
from bot._main_db import init_db, log_trade
import dashboard.components.settings as settings


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "investor_profile_test.db")
    con = init_db(db_path)
    # _compute_investor_profile checks os.path.exists(DB_PATH) using settings'
    # own imported name, but reads via get_db_conn(), which falls back to
    # dashboard.data's module-level DB_PATH internally -- both must be patched.
    monkeypatch.setattr(settings, "DB_PATH", db_path)
    monkeypatch.setattr(data, "DB_PATH", db_path)
    return con


def _closed_trade(con, symbol: str, pnl_pct: float, holding_days: int = 5):
    log_trade(con, symbol, "BUY", 1.0, 100.0, 100.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(con, symbol, "SELL_TIME_EXIT", 1.0, 100.0 * (1 + pnl_pct), 100.0,
              "TRENDING_UP", 10000.0, pnl_pct, holding_days=holding_days)


def test_no_db_file_shows_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "missing.db"))
    html = settings.render_investor_profile()
    assert "No trade data available yet" in html


def test_below_threshold_shows_progress_not_insights(db):
    for i in range(5):
        _closed_trade(db, f"SYM{i}", 0.05)
    html = settings.render_investor_profile()
    assert "5 completed trades recorded" in html
    assert "15 more" in html


def test_excludes_sell_reconcile(db):
    log_trade(db, "GOOGL", "BUY", 1.0, 300.0, 300.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "GOOGL", "SELL_RECONCILE", 1.0, 100.0, 100.0, "reconcile", 10000.0, -0.6667)
    profile = settings._compute_investor_profile({})
    assert profile["not_enough"] is True
    assert profile["count"] == 0


def test_strong_win_rate_insight(db):
    for i in range(16):
        _closed_trade(db, f"WIN{i}", 0.05, holding_days=5)
    for i in range(4):
        _closed_trade(db, f"LOSS{i}", -0.03, holding_days=5)
    profile = settings._compute_investor_profile({})
    assert profile["win_rate"] == 80.0
    assert any("Strong win rate" in i for i in profile["insights"])


def test_avg_win_and_loss_percentages_scaled_correctly(db):
    """Regression test: pnl_pct is stored as a raw fraction (0.05 = 5%); avg_win_pct/
    avg_loss_pct in the returned profile must be percentage-scale (5.0, not 0.05)."""
    for i in range(10):
        _closed_trade(db, f"WIN{i}", 0.10, holding_days=5)
    for i in range(10):
        _closed_trade(db, f"LOSS{i}", -0.04, holding_days=5)
    profile = settings._compute_investor_profile({})
    assert profile["avg_win_pct"] == pytest.approx(10.0)
    assert profile["avg_loss_pct"] == pytest.approx(4.0)


def test_early_exit_insight_and_adaptation(db):
    # 10 wins at +10%, 10 wins at +2% -> avg_win=6%, half=3% -> all 10 SMALL wins
    # (2% < 3%) count as early exits -> 50% early-exit rate, comfortably over 30%.
    for i in range(10):
        _closed_trade(db, f"BIG{i}", 0.10, holding_days=5)
    for i in range(10):
        _closed_trade(db, f"SMALL{i}", 0.02, holding_days=5)
    profile = settings._compute_investor_profile({})
    assert profile["early_exit_rate"] > 30
    assert any("sell winners too early" in i for i in profile["insights"])
    assert any("take-profit" in a for a in profile["adaptations"])


def test_large_losses_insight_and_adaptation(db):
    for i in range(12):
        _closed_trade(db, f"WIN{i}", 0.02, holding_days=5)
    for i in range(8):
        _closed_trade(db, f"LOSS{i}", -0.10, holding_days=5)
    profile = settings._compute_investor_profile({})
    assert any("run larger than wins" in i for i in profile["insights"])
    assert any("stop-loss" in a for a in profile["adaptations"])


def test_short_hold_time_insight(db):
    for i in range(20):
        _closed_trade(db, f"SYM{i}", 0.03, holding_days=1)
    profile = settings._compute_investor_profile({})
    assert profile["avg_hold_days"] == 1.0
    assert any("consider longer holds" in i for i in profile["insights"])


def test_long_hold_time_insight(db):
    for i in range(20):
        _closed_trade(db, f"SYM{i}", 0.03, holding_days=45)
    profile = settings._compute_investor_profile({})
    assert any("positions held longer than target" in i for i in profile["insights"])


def test_render_shows_stats_grid_above_threshold(db):
    for i in range(20):
        _closed_trade(db, f"SYM{i}", 0.05, holding_days=5)
    html = settings.render_investor_profile()
    assert "Win Rate" in html
    assert "Avg Hold" in html
    assert "completed trades recorded" not in html
