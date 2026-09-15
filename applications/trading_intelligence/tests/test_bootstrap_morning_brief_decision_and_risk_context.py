"""Decision Activity & Risk State Context sprint: Morning Brief's two new
additive facts.

Reuses the SAME DecisionOutcomeQueryService lineage Decision Center's own
outcome linkage and Performance & Learning's Outcome History already
exercise (own TradesDbOutcomeReader instance here -- independent, no shared
state, matching every other per-section adapter's own independence in this
product), and the SAME LegacyRiskStateSource read Risk Intelligence's own
Current State section already uses (own instance, independent). No new
adapter, no new pairing/derivation path, no new SQL.
"""
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    DecisionOutcome,
    OutcomeLineage,
    OutcomeStatus,
    PairingConfidence,
    PairingMethod,
)

_ID = 0


def _outcome(**overrides):
    global _ID
    _ID += 1
    defaults = dict(
        decision_id=f"trade-{_ID}",
        symbol="AAA",
        entry_trade_id=_ID,
        entry_timestamp="2026-09-01T12:00:00+00:00",
        entry_price=10.0,
        entry_shares=1.0,
        status=OutcomeStatus.OPEN,
        pairing_method=PairingMethod.NONE_OPEN,
        pairing_confidence=PairingConfidence.NONE,
    )
    defaults.update(overrides)
    return DecisionOutcome(**defaults)


def _lineage(*outcomes):
    return OutcomeLineage(decisions=tuple(outcomes), excluded_sells=())


_NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)


# --- _recent_decision_activity_counts (pure) --------------------------


def test_counts_only_decisions_inside_the_24h_window(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    lineage = _lineage(
        _outcome(entry_timestamp="2026-09-02T06:00:00+00:00"),  # 6h ago -> in window
        _outcome(entry_timestamp="2026-09-01T00:00:00+00:00"),  # 36h ago -> out
    )

    total, resolved = bootstrap._recent_decision_activity_counts(lineage)

    assert total == 1
    assert resolved == 0


def test_exact_boundary_is_inclusive(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    exactly_24h_ago = (_NOW - timedelta(hours=24)).isoformat()
    lineage = _lineage(_outcome(entry_timestamp=exactly_24h_ago))

    total, _ = bootstrap._recent_decision_activity_counts(lineage)

    assert total == 1


def test_resolved_means_closed_specifically_not_partial_or_ambiguous(monkeypatch):
    """Matches Decision Center's own "Decision Outcome" section vocabulary
    exactly: only CLOSED counts as resolved; OPEN/PARTIAL/AMBIGUOUS are all
    "not yet resolved"."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    lineage = _lineage(
        _outcome(entry_timestamp="2026-09-02T06:00:00+00:00", status=OutcomeStatus.CLOSED),
        _outcome(entry_timestamp="2026-09-02T06:00:00+00:00", status=OutcomeStatus.PARTIAL),
        _outcome(entry_timestamp="2026-09-02T06:00:00+00:00", status=OutcomeStatus.AMBIGUOUS),
        _outcome(entry_timestamp="2026-09-02T06:00:00+00:00", status=OutcomeStatus.OPEN),
    )

    total, resolved = bootstrap._recent_decision_activity_counts(lineage)

    assert total == 4
    assert resolved == 1


def test_naive_timestamp_is_treated_as_utc(monkeypatch):
    """entry_timestamp is naive-but-UTC by the bot's own convention (same
    assumption format_display_timestamp / _format_risk_state_as_of /
    _recent_morning_brief_portfolio_history already make)."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    lineage = _lineage(_outcome(entry_timestamp="2026-09-02T06:00:00"))  # naive

    total, _ = bootstrap._recent_decision_activity_counts(lineage)

    assert total == 1


def test_unparseable_timestamp_is_dropped_not_guessed(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    lineage = _lineage(_outcome(entry_timestamp="not-a-timestamp"))

    total, resolved = bootstrap._recent_decision_activity_counts(lineage)

    assert (total, resolved) == (0, 0)


def test_empty_lineage_is_a_real_zero_not_an_error(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)

    total, resolved = bootstrap._recent_decision_activity_counts(_lineage())

    assert (total, resolved) == (0, 0)


def test_custom_window_hours_is_honored(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    lineage = _lineage(_outcome(entry_timestamp="2026-09-02T04:00:00+00:00"))  # 8h ago

    total_1h, _ = bootstrap._recent_decision_activity_counts(lineage, window_hours=1)
    total_12h, _ = bootstrap._recent_decision_activity_counts(lineage, window_hours=12)

    assert total_1h == 0
    assert total_12h == 1


# --- _format_decision_activity_summary / _format_current_risk_state_summary


def test_format_decision_activity_summary_matches_the_exact_template():
    assert bootstrap._format_decision_activity_summary(3, 1) == (
        "3 BUY decisions in the last 24h, 1 already resolved."
    )


def test_format_decision_activity_summary_real_zero_is_honest_not_omitted():
    assert bootstrap._format_decision_activity_summary(0, 0) == (
        "0 BUY decisions in the last 24h, 0 already resolved."
    )


def test_format_current_risk_state_summary_reuses_the_existing_as_of_formatting():
    """Reuses _format_risk_state_as_of verbatim -- proves it, not just
    asserts a hand-written expectation, so this test breaks if that shared
    formatter's behavior ever changes."""
    raw = "2026-09-01T19:00:00+00:00"
    expected_as_of = bootstrap._format_risk_state_as_of(raw)

    summary = bootstrap._format_current_risk_state_summary("NORMAL", raw)

    assert summary == f"Current risk state: NORMAL (as of {expected_as_of})."


# --- _build_morning_brief_screen wiring: real sqlite fixture -------------

_DDL = """
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, symbol TEXT, action TEXT,
    shares REAL, price REAL, notional REAL,
    regime TEXT, portfolio_value REAL, pnl_pct REAL,
    xgb_prob REAL, lstm_prob REAL, sentiment_score REAL, macro_score REAL,
    ensemble_score REAL, realized_pnl REAL, order_id TEXT, holding_days INTEGER,
    feature_drivers TEXT, ai_reasoning TEXT,
    stop_loss REAL, take_profit REAL, risk_reward_ratio REAL
);
CREATE TABLE risk_state (
    key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
);
"""


def _trades_db(buy_rows=(), risk_row=None):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    for trade_id, timestamp in buy_rows:
        conn.execute(
            "INSERT INTO trades (id, timestamp, symbol, action) VALUES (?, ?, 'AAPL', 'BUY')",
            (trade_id, timestamp),
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


def test_decision_activity_is_derived_from_real_seeded_trades(monkeypatch):
    """End-to-end proof: a real sqlite trades.db with one recent and one
    old BUY row drives a real "1 BUY decisions..." fact through the actual
    production _build_morning_brief_screen()."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(buy_rows=[
        (1, "2026-09-02T06:00:00+00:00"),  # 6h ago -> recent
        (2, "2026-09-01T00:00:00+00:00"),  # 36h ago -> not recent
    ])
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.decision_activity_is_available is True
        assert screen.decision_activity_summary == (
            "1 BUY decisions in the last 24h, 0 already resolved."
        )
    finally:
        os.remove(db_path)


def test_risk_state_is_derived_from_real_seeded_risk_state_row(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(risk_row=("WARNING", "2026-09-01T19:00:00+00:00"))
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.current_risk_state_is_available is True
        assert "WARNING" in screen.current_risk_state_summary
        assert "Current risk state:" in screen.current_risk_state_summary
    finally:
        os.remove(db_path)


def test_decision_activity_unavailable_when_no_trades_db(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)

    screen = bootstrap._build_morning_brief_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.decision_activity_is_available is False
    assert screen.decision_activity_summary is None


def test_risk_state_unavailable_when_no_trades_db(monkeypatch):
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)

    screen = bootstrap._build_morning_brief_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.current_risk_state_is_available is False
    assert screen.current_risk_state_summary is None


def test_decision_activity_and_risk_state_are_independent_of_each_other(monkeypatch):
    """A real decision-activity fact must still populate even when the
    risk_state table has no row -- same independence every other
    per-section adapter in this product already has."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    db_path = _trades_db(buy_rows=[(1, "2026-09-02T06:00:00+00:00")])  # no risk_state row
    try:
        screen = bootstrap._build_morning_brief_screen(db_path=db_path)

        assert screen.decision_activity_is_available is True
        assert screen.current_risk_state_is_available is False
    finally:
        os.remove(db_path)


def test_no_fabricated_values_on_source_failure(monkeypatch):
    """Both sources forced to fail -> both facts stay honestly
    unavailable, never a fabricated count or state."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    monkeypatch.setattr(
        bootstrap.DecisionOutcomeQueryService, "get_lineage",
        lambda self: ReadResult.failed(IntegrationHealth.unavailable("trades_db_outcomes")),
    )
    monkeypatch.setattr(
        bootstrap.LegacyRiskStateSource, "get_risk_state",
        lambda self: ReadResult.failed(IntegrationHealth.unavailable("trades_db_risk_state")),
    )

    screen = bootstrap._build_morning_brief_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.decision_activity_summary is None
    assert screen.current_risk_state_summary is None


def test_existing_morning_brief_sections_remain_intact(monkeypatch):
    """Regression guard: adding the two new facts must not disturb the
    existing four-section wiring."""
    monkeypatch.setattr(bootstrap, "_now_utc", lambda: _NOW)
    monkeypatch.setattr(
        bootstrap.DecisionOutcomeQueryService, "get_lineage",
        lambda self: ReadResult.failed(IntegrationHealth.unavailable("trades_db_outcomes")),
    )
    monkeypatch.setattr(
        bootstrap.LegacyRiskStateSource, "get_risk_state",
        lambda self: ReadResult.failed(IntegrationHealth.unavailable("trades_db_risk_state")),
    )

    screen = bootstrap._build_morning_brief_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.portfolio_snapshot is not None
    assert screen.market_mood_regime is not None
    assert screen.candidate_screening_summary is not None
    assert screen.overnight_holdings_news is not None
