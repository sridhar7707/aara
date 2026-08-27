"""Tests for bootstrap._format_candidate_screening_summary -- the pure
formatting combining a real LegacyCandidateScreeningSource result into
Morning Brief's Candidate Screening Summary available_summary text.
"""
from applications.trading_intelligence.adapters.legacy_candidate_screening_source import (
    CandidateScreeningPick,
    CandidateScreeningSnapshot,
)
from applications.trading_intelligence.bootstrap import _format_candidate_screening_summary


def test_summary_states_the_actual_screened_at_date_not_today():
    snapshot = CandidateScreeningSnapshot(
        screened_at="2026-08-20T11:32:31+00:00",
        picks=(CandidateScreeningPick(symbol="SNOW", rank=1, composite_score=0.7295, sector="Technology"),),
    )

    summary = _format_candidate_screening_summary(snapshot)

    assert "2026-08-20" in summary
    assert "today" not in summary.lower()


def test_summary_includes_candidate_count_and_top_pick():
    snapshot = CandidateScreeningSnapshot(
        screened_at="2026-08-20T11:32:31+00:00",
        picks=(
            CandidateScreeningPick(symbol="SNOW", rank=1, composite_score=0.7295, sector="Technology"),
            CandidateScreeningPick(symbol="BLK", rank=2, composite_score=0.6959, sector="Financials"),
        ),
    )

    summary = _format_candidate_screening_summary(snapshot)

    assert summary == "2 candidates screened on 2026-08-20 -- top pick SNOW (rank 1, score 0.73)."


def test_summary_uses_singular_candidate_for_a_single_pick():
    snapshot = CandidateScreeningSnapshot(
        screened_at="2026-08-20T11:32:31+00:00",
        picks=(CandidateScreeningPick(symbol="SNOW", rank=1, composite_score=0.7295, sector="Technology"),),
    )

    summary = _format_candidate_screening_summary(snapshot)

    assert summary == "1 candidate screened on 2026-08-20 -- top pick SNOW (rank 1, score 0.73)."


def test_summary_omits_score_clause_when_top_pick_has_no_score():
    snapshot = CandidateScreeningSnapshot(
        screened_at="2026-08-20T11:32:31+00:00",
        picks=(CandidateScreeningPick(symbol="SNOW", rank=1, composite_score=None, sector="Technology"),),
    )

    summary = _format_candidate_screening_summary(snapshot)

    assert summary == "1 candidate screened on 2026-08-20 -- top pick SNOW (rank 1)."


def test_summary_omits_top_pick_clause_entirely_when_no_rank_exists():
    snapshot = CandidateScreeningSnapshot(
        screened_at="2026-08-20T11:32:31+00:00",
        picks=(CandidateScreeningPick(symbol="SNOW", rank=None, composite_score=None, sector=None),),
    )

    summary = _format_candidate_screening_summary(snapshot)

    assert summary == "1 candidate screened on 2026-08-20."
