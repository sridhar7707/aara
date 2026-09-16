"""Sprint 8B -- Trading Intelligence Command Center: Morning Brief's KPI
strip and Drawdown chart.

Reuses the SAME real PortfolioSnapshotValue (LegacyPortfolioSnapshotSource)
and LegacyRiskStateSource reads Morning Brief's existing Portfolio Snapshot
and Current Risk State facts already perform, plus the SAME
_compute_drawdown_history() pure function Risk Intelligence already uses.
No new adapter, no new SQL beyond the already-landed open_positions column
(test_legacy_portfolio_snapshot_source.py).
"""
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.ui.morning_brief.screen import DrawdownPoint

_NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)


class _FakePoint:
    """Duck-typed stand-in for MorningBriefPortfolioHistoryPoint -- the
    functions under test only read .as_of / .portfolio_value, matching
    the existing _recent_morning_brief_portfolio_history test convention."""
    def __init__(self, as_of, portfolio_value):
        self.as_of = as_of
        self.portfolio_value = portfolio_value


# --- _compute_todays_change (pure) -----------------------------------------


def test_todays_change_compares_latest_to_the_earliest_point_on_the_same_date():
    points = (
        _FakePoint("2026-09-01T23:00:00+00:00", 90000.0),
        _FakePoint("2026-09-02T09:00:00+00:00", 100000.0),
        _FakePoint("2026-09-02T15:00:00+00:00", 103000.0),
    )
    usd, pct = bootstrap._compute_todays_change(points)

    assert usd == 3000.0
    assert round(pct, 4) == round(3000.0 / 100000.0 * 100, 4)


def test_todays_change_none_with_fewer_than_two_points():
    assert bootstrap._compute_todays_change(()) == (None, None)
    assert bootstrap._compute_todays_change((_FakePoint("2026-09-02T09:00:00+00:00", 100000.0),)) == (None, None)


def test_todays_change_none_when_latest_is_the_only_point_from_today():
    points = (
        _FakePoint("2026-08-20T09:00:00+00:00", 90000.0),
        _FakePoint("2026-09-02T09:00:00+00:00", 100000.0),
    )
    assert bootstrap._compute_todays_change(points) == (None, None)


def test_todays_change_none_when_baseline_value_is_not_positive():
    points = (
        _FakePoint("2026-09-02T01:00:00+00:00", 0.0),
        _FakePoint("2026-09-02T09:00:00+00:00", 100000.0),
    )
    assert bootstrap._compute_todays_change(points) == (None, None)


def test_todays_change_unparseable_latest_timestamp_is_none():
    points = (
        _FakePoint("2026-09-02T01:00:00+00:00", 90000.0),
        _FakePoint("not-a-timestamp", 100000.0),
    )
    assert bootstrap._compute_todays_change(points) == (None, None)


def test_todays_change_negative_when_value_dropped():
    points = (
        _FakePoint("2026-09-02T09:00:00+00:00", 100000.0),
        _FakePoint("2026-09-02T15:00:00+00:00", 97000.0),
    )
    usd, pct = bootstrap._compute_todays_change(points)

    assert usd == -3000.0
    assert pct < 0


# --- _recent_morning_brief_drawdown_history (pure, reuses _compute_drawdown_history)


def test_drawdown_history_reuses_the_same_math_risk_intelligence_uses():
    points = (
        _FakePoint("2026-09-01T00:00:00+00:00", 100000.0),
        _FakePoint("2026-09-02T00:00:00+00:00", 90000.0),
    )
    mb_drawdown = bootstrap._recent_morning_brief_drawdown_history(points)
    ri_drawdown = bootstrap._compute_drawdown_history(points)

    assert [p.drawdown_pct for p in mb_drawdown] == [p.drawdown_pct for p in ri_drawdown]
    assert [p.portfolio_value for p in mb_drawdown] == [p.portfolio_value for p in ri_drawdown]
    assert all(isinstance(p, DrawdownPoint) for p in mb_drawdown)


def test_drawdown_history_windows_to_the_recent_range(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    points = (
        _FakePoint("2026-01-01T00:00:00+00:00", 100000.0),  # outside 30-day window
        _FakePoint("2026-09-01T00:00:00+00:00", 95000.0),   # inside window
    )
    windowed = bootstrap._recent_morning_brief_drawdown_history(points)

    assert [p.as_of for p in windowed] == ["2026-09-01T00:00:00+00:00"]


def test_drawdown_history_of_empty_points_is_empty():
    assert bootstrap._recent_morning_brief_drawdown_history(()) == ()


# --- _build_morning_brief_screen wiring: real sqlite fixture ---------------

_DDL = """
CREATE TABLE portfolio_snapshots (
    timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL,
    open_positions INTEGER
);
CREATE TABLE risk_state (
    key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
);
"""


def _trades_db(snapshot_rows=(), risk_row=None):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    for timestamp, value, cash, open_positions in snapshot_rows:
        conn.execute(
            "INSERT INTO portfolio_snapshots VALUES (?, ?, ?, ?)",
            (timestamp, value, cash, open_positions),
        )
    if risk_row is not None:
        state, updated_at = risk_row
        conn.execute(
            "INSERT INTO risk_state (key, value, updated_at) VALUES "
            "('risk_governor_state', ?, ?)",
            (state, updated_at),
        )
    conn.commit()
    conn.close()
    return path


def test_kpis_populated_from_real_seeded_snapshot_and_risk_state(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(
        snapshot_rows=[
            ("2026-09-02T09:00:00+00:00", 100000.0, 40000.0, 7),
            ("2026-09-02T15:00:00+00:00", 103000.0, 37000.0, 7),
        ],
        risk_row=("NORMAL", "2026-09-02T15:00:00+00:00"),
    )
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.kpis_is_available is True
        assert screen.kpis.total_value == 103000.0
        assert screen.kpis.available_cash == 37000.0
        assert screen.kpis.invested_amount == 103000.0 - 37000.0
        assert screen.kpis.open_positions == 7
        assert screen.kpis.risk_state == "NORMAL"
        assert screen.kpis.todays_change_usd == 3000.0
    finally:
        os.remove(db_path)


def test_kpis_unavailable_when_no_trades_db(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)

    screen = bootstrap._build_morning_brief_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.kpis_is_available is False
    assert screen.kpis is None


def test_kpis_risk_state_is_none_when_risk_state_read_has_no_row_but_snapshot_succeeds(monkeypatch):
    """Independent sub-facts: a real portfolio snapshot with no risk_state
    row must still produce real KPIs, with risk_state honestly None --
    never blocking the whole KPI strip."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(
        snapshot_rows=[("2026-09-02T09:00:00+00:00", 100000.0, 40000.0, 5)],
    )
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.kpis_is_available is True
        assert screen.kpis.risk_state is None
    finally:
        os.remove(db_path)


def test_drawdown_history_populated_from_real_seeded_snapshots(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(
        snapshot_rows=[
            ("2026-09-01T00:00:00+00:00", 100000.0, 40000.0, 5),
            ("2026-09-02T00:00:00+00:00", 95000.0, 45000.0, 5),
        ],
    )
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.drawdown_history_is_available is True
        assert screen.drawdown_history_is_empty is False
        assert round(screen.drawdown_history[-1].drawdown_pct, 2) == 5.0
    finally:
        os.remove(db_path)


def test_drawdown_history_unavailable_when_no_trades_db(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)

    screen = bootstrap._build_morning_brief_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.drawdown_history_is_available is False
    assert screen.drawdown_history is None


def test_existing_morning_brief_fields_remain_intact(monkeypatch):
    """Regression guard: adding kpis/drawdown_history must not disturb the
    existing portfolio_history / decision_activity / risk_state wiring."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(
        snapshot_rows=[("2026-09-02T09:00:00+00:00", 100000.0, 40000.0, 5)],
        risk_row=("WARNING", "2026-09-02T09:00:00+00:00"),
    )
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.portfolio_history_is_available is True
        assert screen.current_risk_state_is_available is True
        assert "WARNING" in screen.current_risk_state_summary
        assert screen.kpis.risk_state == "WARNING"
    finally:
        os.remove(db_path)
