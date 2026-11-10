"""Tests for the trusted sanity baseline (ADR-088 revision, quant review finding 1).

A blocked reading must never become the baseline, so a glitch cannot unblock reconcile
on a later cycle.
"""
import sqlite3

from bot._main_prep import load_trusted_value, sanity_check


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE risk_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    con.execute("CREATE TABLE portfolio_snapshots (timestamp TEXT, portfolio_value REAL)")
    return con


def test_first_run_has_no_baseline_and_is_not_blocked():
    con = _con()
    blocked, baseline = sanity_check(con, 10_000.0)
    assert blocked is False and baseline is None
    assert load_trusted_value(con) == 10_000.0


def test_fallback_to_latest_snapshot_only_when_no_trusted_value():
    con = _con()
    con.execute("INSERT INTO portfolio_snapshots VALUES ('2026-11-07T10:00', 10000.0)")
    blocked, baseline = sanity_check(con, 4_000.0)
    assert blocked is True and baseline == 10_000.0


def test_blocked_reading_does_not_become_the_baseline():
    con = _con()
    sanity_check(con, 10_000.0)           # trusted
    blocked, baseline = sanity_check(con, 4_000.0)
    assert blocked is True and baseline == 10_000.0
    assert load_trusted_value(con) == 10_000.0


def test_glitch_stays_blocked_on_every_following_cycle():
    con = _con()
    sanity_check(con, 10_000.0)
    for _ in range(5):
        blocked, baseline = sanity_check(con, 4_000.0)
        assert blocked is True and baseline == 10_000.0
    assert load_trusted_value(con) == 10_000.0


def test_recovery_above_half_is_trusted_again():
    con = _con()
    sanity_check(con, 10_000.0)
    sanity_check(con, 4_000.0)            # blocked, not saved
    blocked, baseline = sanity_check(con, 9_000.0)
    assert blocked is False and baseline == 10_000.0
    assert load_trusted_value(con) == 9_000.0


def test_small_decline_is_not_blocked():
    con = _con()
    sanity_check(con, 10_000.0)
    blocked, _ = sanity_check(con, 9_500.0)
    assert blocked is False


def test_anchors_recorded_once_from_trusted_readings():
    from bot._main_prep import read_anchor, current_week_key
    con = _con()
    sanity_check(con, 10_000.0)
    sanity_check(con, 10_500.0)           # later trusted reading must not overwrite the anchors
    assert read_anchor(con, "first_trusted_value") == 10_000.0
    assert read_anchor(con, f"week_trusted_start:{current_week_key()}") == 10_000.0


def test_blocked_reading_never_sets_an_anchor():
    from bot._main_prep import read_anchor
    con = _con()
    sanity_check(con, 4_000.0)            # no trusted baseline yet: accepted as the first trusted value
    con2 = _con()
    sanity_check(con2, 10_000.0)
    sanity_check(con2, 3_000.0)           # blocked
    assert read_anchor(con2, "first_trusted_value") == 10_000.0
