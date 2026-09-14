"""Sprint 1: Risk Intelligence's Portfolio Drawdown chart.

Reuses LegacyPortfolioSnapshotSource.get_portfolio_history() -- the exact
same real adapter Portfolio Intelligence's and Morning Brief's own charts
call -- and computes drawdown_pct from the running peak over that real
history in bootstrap._compute_drawdown_history(). No new backend reader,
no schema change.
"""
import sqlite3

from applications.platform.integrations import IntegrationStatus
from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.ui.risk_intelligence.screen import DrawdownPoint


def _trades_db(tmp_path, rows):
    path = tmp_path / "trades.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE portfolio_snapshots (
            timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL,
            open_positions INTEGER
        );
        CREATE TABLE risk_state (
            key TEXT PRIMARY KEY, state TEXT, updated_at TEXT
        );
        """
    )
    for timestamp, value in rows:
        conn.execute(
            "INSERT INTO portfolio_snapshots VALUES (?, ?, ?, ?)",
            (timestamp, value, 0.0, 0),
        )
    conn.commit()
    conn.close()
    return str(path)


def _empty_trades_db(tmp_path):
    path = tmp_path / "trades.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE portfolio_snapshots (timestamp TEXT PRIMARY KEY, "
        "portfolio_value REAL, available_cash REAL, open_positions INTEGER);"
    )
    conn.commit()
    conn.close()
    return str(path)


# --- _compute_drawdown_history() (pure function) --------------------------


def test_compute_drawdown_history_is_zero_at_a_new_peak():
    points = [
        _FakePoint("2026-09-01T00:00:00+00:00", 100.0),
        _FakePoint("2026-09-02T00:00:00+00:00", 110.0),
    ]
    history = bootstrap._compute_drawdown_history(points)

    assert history == (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100.0, drawdown_pct=0.0),
        DrawdownPoint(as_of="2026-09-02T00:00:00+00:00", portfolio_value=110.0, drawdown_pct=0.0),
    )


def test_compute_drawdown_history_computes_real_pct_below_running_peak():
    points = [
        _FakePoint("2026-09-01T00:00:00+00:00", 100.0),  # peak so far: 100
        _FakePoint("2026-09-02T00:00:00+00:00", 90.0),   # 10% below peak
        _FakePoint("2026-09-03T00:00:00+00:00", 80.0),   # 20% below peak
        _FakePoint("2026-09-04T00:00:00+00:00", 95.0),   # peak still 100 -> 5% below
        _FakePoint("2026-09-05T00:00:00+00:00", 120.0),  # new peak -> 0%
    ]
    history = bootstrap._compute_drawdown_history(points)

    assert [round(p.drawdown_pct, 4) for p in history] == [0.0, 10.0, 20.0, 5.0, 0.0]
    assert [p.portfolio_value for p in history] == [100.0, 90.0, 80.0, 95.0, 120.0]


def test_compute_drawdown_history_of_empty_points_is_empty():
    assert bootstrap._compute_drawdown_history([]) == ()


class _FakePoint:
    """Duck-typed stand-in for the adapter's own PortfolioHistoryPoint --
    _compute_drawdown_history only reads .as_of / .portfolio_value."""
    def __init__(self, as_of, portfolio_value):
        self.as_of = as_of
        self.portfolio_value = portfolio_value


# --- _build_risk_intelligence_screen() wiring, real sqlite fixture --------


def test_drawdown_history_wired_from_real_portfolio_snapshots(tmp_path):
    db_path = _trades_db(
        tmp_path,
        [
            ("2026-09-01T00:00:00+00:00", 100000.0),
            ("2026-09-02T00:00:00+00:00", 95000.0),
        ],
    )

    screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

    assert screen.drawdown_history_is_available
    assert not screen.drawdown_history_is_empty
    assert [p.as_of for p in screen.drawdown_history] == [
        "2026-09-01T00:00:00+00:00", "2026-09-02T00:00:00+00:00",
    ]
    assert round(screen.drawdown_history[1].drawdown_pct, 2) == 5.0


def test_drawdown_history_empty_when_table_exists_with_no_rows(tmp_path):
    db_path = _empty_trades_db(tmp_path)

    screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

    assert screen.drawdown_history_is_available
    assert screen.drawdown_history_is_empty
    assert screen.drawdown_history == ()


def test_drawdown_history_unavailable_when_no_portfolio_snapshots_table(tmp_path):
    path = tmp_path / "trades.db"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE unrelated (id INTEGER);")
    conn.commit()
    conn.close()

    screen = bootstrap._build_risk_intelligence_screen(db_path=str(path))

    assert not screen.drawdown_history_is_available
    assert screen.drawdown_history is None
    assert screen.drawdown_history_health.status is IntegrationStatus.API_ERROR


def test_drawdown_history_is_independent_of_current_risk_state_availability(tmp_path):
    """Portfolio drawdown must still be wired even when risk_state itself
    has no row -- same independence Portfolio Intelligence's Alpaca
    sections already have relative to its Capital Summary."""
    db_path = _trades_db(tmp_path, [("2026-09-01T00:00:00+00:00", 100000.0)])
    # No row inserted into risk_state -> current stays None (unavailable).

    screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

    assert not screen.is_available  # current risk state: unavailable
    assert screen.drawdown_history_is_available  # drawdown: still real
    assert len(screen.drawdown_history) == 1
