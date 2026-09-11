"""Tests for applications.trading_intelligence.services.news_cache_snapshot_diff.

Sprint 7 -- Descriptive Evidence-State Diff. Pure, deterministic comparison
of two already-fetched NewsCacheSnapshot instances: no polarity, confidence,
materiality, freshness, thesis, or validity semantics -- only facts directly
supported by the news_cache data contract (symbol, fetch_date, a flat list
of headline strings, cached_at).
"""
import pytest

from applications.trading_intelligence.adapters.legacy_news_cache_source import (
    NewsCacheSnapshot,
)
from applications.trading_intelligence.services.news_cache_snapshot_diff import (
    NewsCacheSnapshotDiff,
    diff_news_cache_snapshots,
)


def _snapshot(symbol="AAPL", fetch_date="2026-09-01", headlines=(), cached_at="2026-09-01T08:30:00"):
    return NewsCacheSnapshot(
        symbol=symbol, fetch_date=fetch_date, headlines=tuple(headlines), cached_at=cached_at
    )


def test_identical_snapshots_report_no_change():
    before = _snapshot(headlines=("Stock rises on earnings", "Analyst raises target"))
    after = _snapshot(fetch_date="2026-09-02", headlines=("Stock rises on earnings", "Analyst raises target"))

    result = diff_news_cache_snapshots(before, after)

    assert result.is_identical is True
    assert result.same_headlines_reordered is False
    assert result.added_headlines == ()
    assert result.removed_headlines == ()
    assert result.before_headline_count == 2
    assert result.after_headline_count == 2


def test_added_headline_is_reported():
    before = _snapshot(headlines=("Stock rises on earnings",))
    after = _snapshot(fetch_date="2026-09-02", headlines=("Stock rises on earnings", "New product announced"))

    result = diff_news_cache_snapshots(before, after)

    assert result.added_headlines == ("New product announced",)
    assert result.removed_headlines == ()
    assert result.is_identical is False
    assert result.before_headline_count == 1
    assert result.after_headline_count == 2


def test_removed_headline_is_reported():
    before = _snapshot(headlines=("Stock rises on earnings", "Analyst raises target"))
    after = _snapshot(fetch_date="2026-09-02", headlines=("Stock rises on earnings",))

    result = diff_news_cache_snapshots(before, after)

    assert result.removed_headlines == ("Analyst raises target",)
    assert result.added_headlines == ()
    assert result.is_identical is False


def test_changed_content_reports_both_added_and_removed():
    before = _snapshot(headlines=("Stock rises on earnings", "Analyst raises target"))
    after = _snapshot(fetch_date="2026-09-02", headlines=("Stock rises on earnings", "Guidance cut reported"))

    result = diff_news_cache_snapshots(before, after)

    assert result.removed_headlines == ("Analyst raises target",)
    assert result.added_headlines == ("Guidance cut reported",)


def test_same_headlines_reordered_is_not_added_or_removed():
    before = _snapshot(headlines=("Headline A", "Headline B"))
    after = _snapshot(fetch_date="2026-09-02", headlines=("Headline B", "Headline A"))

    result = diff_news_cache_snapshots(before, after)

    assert result.is_identical is False
    assert result.same_headlines_reordered is True
    assert result.added_headlines == ()
    assert result.removed_headlines == ()


def test_empty_snapshots_are_identical():
    before = _snapshot(headlines=())
    after = _snapshot(fetch_date="2026-09-02", headlines=())

    result = diff_news_cache_snapshots(before, after)

    assert result.is_identical is True
    assert result.same_headlines_reordered is False
    assert result.before_headline_count == 0
    assert result.after_headline_count == 0
    assert result.added_headlines == ()
    assert result.removed_headlines == ()


def test_transition_from_empty_to_populated_reports_all_as_added():
    before = _snapshot(headlines=())
    after = _snapshot(fetch_date="2026-09-02", headlines=("First headline",))

    result = diff_news_cache_snapshots(before, after)

    assert result.added_headlines == ("First headline",)
    assert result.removed_headlines == ()
    assert result.is_identical is False


def test_duplicate_headlines_are_diffed_as_a_multiset_not_a_set():
    """The data contract does not deduplicate headlines_json -- a headline
    appearing twice in `before` and once in `after` is one removal, not
    zero (a naive set-difference would wrongly report no change)."""
    before = _snapshot(headlines=("Repeated headline", "Repeated headline"))
    after = _snapshot(fetch_date="2026-09-02", headlines=("Repeated headline",))

    result = diff_news_cache_snapshots(before, after)

    assert result.removed_headlines == ("Repeated headline",)
    assert result.added_headlines == ()
    assert result.before_headline_count == 2
    assert result.after_headline_count == 1


def test_output_is_deterministic_across_repeated_calls():
    before = _snapshot(headlines=("A", "B", "C"))
    after = _snapshot(fetch_date="2026-09-02", headlines=("B", "C", "D"))

    first = diff_news_cache_snapshots(before, after)
    second = diff_news_cache_snapshots(before, after)

    assert first == second


def test_missing_cached_at_on_either_snapshot_does_not_crash():
    before = _snapshot(headlines=("A",), cached_at=None)
    after = _snapshot(fetch_date="2026-09-02", headlines=("A", "B"), cached_at=None)

    result = diff_news_cache_snapshots(before, after)

    assert result.before_cached_at is None
    assert result.after_cached_at is None
    assert result.added_headlines == ("B",)


def test_mismatched_symbols_raise_value_error():
    before = _snapshot(symbol="AAPL")
    after = _snapshot(symbol="MSFT")

    with pytest.raises(ValueError):
        diff_news_cache_snapshots(before, after)


def test_result_carries_snapshot_identity_fields_verbatim():
    before = _snapshot(symbol="AAPL", fetch_date="2026-09-01", cached_at="2026-09-01T08:30:00")
    after = _snapshot(symbol="AAPL", fetch_date="2026-09-02", cached_at="2026-09-02T08:31:00")

    result = diff_news_cache_snapshots(before, after)

    assert result.symbol == "AAPL"
    assert result.before_fetch_date == "2026-09-01"
    assert result.after_fetch_date == "2026-09-02"
    assert result.before_cached_at == "2026-09-01T08:30:00"
    assert result.after_cached_at == "2026-09-02T08:31:00"


def test_diff_result_type_carries_no_polarity_confidence_or_validity_fields():
    """Regression lock for the sprint's explicit scope boundary: the result
    type must never grow a materiality/confidence/validity/thesis field."""
    forbidden_field_names = {
        "polarity", "confidence", "materiality", "material", "valid",
        "invalidated", "thesis", "score", "severity", "alert",
    }
    actual_fields = set(NewsCacheSnapshotDiff.__dataclass_fields__.keys())

    assert actual_fields.isdisjoint(forbidden_field_names)
