def test_get_overview_no_db():
    from bot.monitor._dashboard_overview import get_overview
    result = get_overview()
    assert isinstance(result, dict)


def test_overview_md_error_key():
    from bot.monitor._dashboard_overview import overview_md
    result = overview_md({"_error": "test error"})
    assert "test error" in result


def _base_overview_dict(**overrides):
    d = {
        "portfolio": 10000.0, "day_pnl": 0.01, "week_pnl": 0.02,
        "day_pnl_dollars": 100.0, "week_pnl_dollars": 200.0,
        "total_return": 0.05, "inception_date": None,
        "total_trades": 10, "spy_return": None,
        "trades_today": 2, "open_positions": 3, "day_trades_used": 1,
        "macro_score": 0.6, "macro_halt": False, "macro_halt_reason": 0,
        "emergency_halt": False,
        "daily_limit_hit": False, "weekly_limit_hit": False,
        "sync_ok": True, "sync_age_s": 60.0, "sync_err": "", "db_age_s": 120.0,
    }
    d.update(overrides)
    return d


def test_overview_md_full_dict():
    from bot.monitor._dashboard_overview import overview_md
    result = overview_md(_base_overview_dict())
    assert "Portfolio Value" in result
    assert "ACTIVE" in result


# --- Amendment 1 to ADR-010: halt-reason presentation ---

def test_overview_md_genuine_vix_halt(monkeypatch):
    from bot.monitor._dashboard_overview import overview_md
    from bot.db.macro_cache import REASON_VIX_THRESHOLD
    d = _base_overview_dict(macro_halt=True, macro_halt_reason=REASON_VIX_THRESHOLD)
    result = overview_md(d)
    assert "VIX HALT" in result
    assert "DATA UNAVAILABLE" not in result


def test_overview_md_data_unavailable_shows_distinct_status():
    from bot.monitor._dashboard_overview import overview_md
    from bot.db.macro_cache import REASON_DATA_UNAVAILABLE
    d = _base_overview_dict(macro_halt=True, macro_halt_reason=REASON_DATA_UNAVAILABLE)
    result = overview_md(d)
    assert "DATA UNAVAILABLE" in result
    assert "VIX HALT" not in result


def test_overview_md_cold_start_does_not_claim_active():
    # True cold start: no macro evaluation ever recorded. Must not be
    # presented as a confirmed "ACTIVE" state -- the dashboard has no
    # evidence either way.
    from bot.monitor._dashboard_overview import overview_md
    d = _base_overview_dict(macro_halt=False, macro_halt_reason=None)
    result = overview_md(d)
    assert "ACTIVE" not in result
    assert "UNKNOWN" in result


def test_overview_md_emergency_halt_still_takes_priority_over_macro_status():
    from bot.monitor._dashboard_overview import overview_md
    from bot.db.macro_cache import REASON_DATA_UNAVAILABLE
    d = _base_overview_dict(macro_halt=True, macro_halt_reason=REASON_DATA_UNAVAILABLE,
                             emergency_halt=True)
    result = overview_md(d)
    assert "EMERGENCY HALT" in result


def test_get_overview_reports_macro_halt_reason_from_db(tmp_path, monkeypatch):
    # Cold-start integration check: a fresh, empty trades.db has no
    # macro_cache rows at all, so get_overview() must surface
    # macro_halt_reason=None rather than defaulting it to REASON_NONE.
    import sqlite3
    import bot._main_db as main_db
    import bot.monitor.dashboard_data as dashboard_data
    from bot.monitor._dashboard_overview import get_overview

    db_path = tmp_path / "trades.db"
    con = main_db.init_db(str(db_path))
    con.close()
    monkeypatch.setattr(dashboard_data, "_DB", str(db_path))

    result = get_overview()
    assert result.get("macro_halt_reason") is None


def test_fmt_age():
    from bot.monitor._dashboard_overview import _fmt_age
    assert "s ago" in _fmt_age(30)
    assert "m ago" in _fmt_age(90)
    assert "h ago" in _fmt_age(7200)
    assert _fmt_age(None) == "unknown"
