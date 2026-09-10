"""Tests for applications.trading_intelligence.ui.decision_center.screen."""
import datetime
import dataclasses
import inspect

import pytest

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.screen import (
    CONFIDENCE_QUALIFIER,
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
    EvidencePolarityRow,
    INTERPRETED_STRATEGY_DECISION_LABEL,
    ReadStatus,
    SENTINEL_NON_CONCURRENCE_STATEMENT,
    SENTINEL_RECOMMENDATION_LABEL,
    evidence_polarity_label,
    format_display_timestamp,
    is_sentinel_recommendation,
    provenance_label,
    sentinel_non_concurrence_statement,
)


def test_format_display_timestamp_converts_naive_utc_to_america_chicago_summer_cdt():
    assert (
        format_display_timestamp(datetime.datetime(2026, 8, 21, 19, 45, 0))
        == "2026-08-21 14:45 CDT"
    )


def test_format_display_timestamp_converts_naive_utc_to_america_chicago_winter_cst():
    assert (
        format_display_timestamp(datetime.datetime(2026, 1, 8, 15, 40, 0))
        == "2026-01-08 09:40 CST"
    )


def _make_view(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionView(**defaults)


def _make_entry(**overrides):
    defaults = dict(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        attached_at=datetime.datetime(2026, 8, 4, 12, 5, 0),
    )
    defaults.update(overrides)
    return EvidenceEntry(**defaults)


def _make_governance_entry(**overrides):
    defaults = dict(
        policy_id="pol-001",
        enabled=True,
        evaluated_at=datetime.datetime(2026, 8, 4, 12, 6, 0),
    )
    defaults.update(overrides)
    return GovernanceEntry(**defaults)


def _make_approval_entry(**overrides):
    defaults = dict(
        approval_id="apr-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        approved_at=datetime.datetime(2026, 8, 4, 12, 7, 0),
    )
    defaults.update(overrides)
    return ApprovalEntry(**defaults)


def _make_audit_entry(**overrides):
    defaults = dict(
        event_id="evt-001",
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
        payload={"decision_id": "dec-001"},
    )
    defaults.update(overrides)
    return AuditEntry(**defaults)


def test_decision_list_area_reports_empty_state_when_no_decisions():
    area = DecisionListArea(decisions=[])

    assert area.is_empty is True
    assert area.empty_state_message == "No decisions recorded yet."


def test_decision_list_area_reports_not_empty_with_decisions():
    area = DecisionListArea(decisions=[_make_view()])

    assert area.is_empty is False
    assert area.empty_state_message is None


def test_decision_list_area_is_immutable():
    area = DecisionListArea(decisions=[])
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.decisions = [_make_view()]


def test_decision_detail_area_reports_empty_when_no_decision_selected():
    area = DecisionDetailArea(decision=None)

    assert area.is_empty is True
    assert area.confidence_display is None
    assert area.status_display is None
    assert area.timestamp_display is None


def test_decision_detail_area_formats_confidence_as_a_percentage():
    area = DecisionDetailArea(decision=_make_view(confidence=0.78))

    assert area.confidence_display == "78%"


def test_decision_detail_area_formats_status_as_title_case_words():
    area = DecisionDetailArea(decision=_make_view(status=DecisionState.DECISION_CREATED))

    assert area.status_display == "Decision Created"


def test_decision_detail_area_formats_timestamp():
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 8, 4, 12, 30, 0))
    )

    assert area.timestamp_display == "2026-08-04 07:30 CDT"


def test_decision_detail_area_formats_timestamp_in_america_chicago_summer_cdt():
    """P1 UI-only timestamp fix: all Decision Center timestamps are stored
    as naive-but-UTC (see format_display_timestamp's own docstring) and
    must display converted to America/Chicago, DST-aware. August is CDT
    (UTC-5)."""
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 8, 21, 19, 45, 0))
    )

    assert area.timestamp_display == "2026-08-21 14:45 CDT"


def test_decision_detail_area_formats_timestamp_in_america_chicago_winter_cst():
    """Same conversion, but January is CST (UTC-6) -- proves the DST
    transition is honored automatically, not a fixed offset."""
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 1, 8, 15, 40, 0))
    )

    assert area.timestamp_display == "2026-01-08 09:40 CST"


def test_decision_detail_area_defaults_to_no_evidence():
    area = DecisionDetailArea(decision=_make_view())

    assert area.evidence == ()


def test_decision_detail_area_carries_evidence_entries():
    entry = _make_entry()
    area = DecisionDetailArea(decision=_make_view(), evidence=(entry,))

    assert area.evidence == (entry,)


def test_decision_detail_area_with_evidence_still_formats_core_decision_fields():
    entry = _make_entry()
    area = DecisionDetailArea(
        decision=_make_view(confidence=0.78, status=DecisionState.DECISION_CREATED),
        evidence=(entry,),
    )

    assert area.confidence_display == "78%"
    assert area.status_display == "Decision Created"
    assert area.timestamp_display == "2026-08-04 07:00 CDT"


def test_decision_detail_area_is_immutable_including_evidence():
    area = DecisionDetailArea(decision=_make_view())
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.evidence = (_make_entry(),)


def test_decision_detail_area_defaults_to_no_governance():
    area = DecisionDetailArea(decision=_make_view())

    assert area.governance == ()


def test_decision_detail_area_carries_governance_entries():
    entry = _make_governance_entry()
    area = DecisionDetailArea(decision=_make_view(), governance=(entry,))

    assert area.governance == (entry,)


def test_decision_detail_area_defaults_to_no_approvals():
    area = DecisionDetailArea(decision=_make_view())

    assert area.approvals == ()


def test_decision_detail_area_carries_approval_entries():
    entry = _make_approval_entry()
    area = DecisionDetailArea(decision=_make_view(), approvals=(entry,))

    assert area.approvals == (entry,)


def test_decision_detail_area_is_immutable_including_governance_and_approvals():
    area = DecisionDetailArea(decision=_make_view())
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.governance = (_make_governance_entry(),)
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.approvals = (_make_approval_entry(),)


def test_decision_detail_area_with_governance_and_approvals_still_formats_core_decision_fields():
    area = DecisionDetailArea(
        decision=_make_view(confidence=0.78, status=DecisionState.DECISION_CREATED),
        governance=(_make_governance_entry(),),
        approvals=(_make_approval_entry(),),
    )

    assert area.confidence_display == "78%"
    assert area.status_display == "Decision Created"


def test_decision_detail_area_defaults_to_no_audit_trail():
    area = DecisionDetailArea(decision=_make_view())

    assert area.audit_trail == ()


def test_decision_detail_area_carries_audit_entries():
    entry = _make_audit_entry()
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(entry,))

    assert area.audit_trail == (entry,)


def test_decision_detail_area_preserves_audit_entry_order():
    first = _make_audit_entry(event_type="DECISION_CREATED")
    second = _make_audit_entry(event_type="EVIDENCE_ATTACHED")
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(first, second))

    assert area.audit_trail == (first, second)


def test_decision_detail_area_is_immutable_including_audit_trail():
    area = DecisionDetailArea(decision=_make_view())
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.audit_trail = (_make_audit_entry(),)


def test_empty_audit_trail_and_errored_audit_trail_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), audit_trail=())
    errored = DecisionDetailArea(
        decision=_make_view(), audit_trail=(), audit_trail_status=ReadStatus.ERROR
    )

    assert empty.audit_trail_status is ReadStatus.OK
    assert errored.audit_trail_status is ReadStatus.ERROR


def test_decision_detail_area_defaults_every_read_status_to_ok():
    area = DecisionDetailArea(decision=None)

    assert area.decision_status is ReadStatus.OK
    assert area.evidence_status is ReadStatus.OK
    assert area.governance_status is ReadStatus.OK
    assert area.approvals_status is ReadStatus.OK
    assert area.audit_trail_status is ReadStatus.OK


def test_missing_decision_and_errored_decision_are_distinguishable():
    missing = DecisionDetailArea(decision=None)
    errored = DecisionDetailArea(decision=None, decision_status=ReadStatus.ERROR)

    assert missing.decision_status is ReadStatus.OK
    assert errored.decision_status is ReadStatus.ERROR
    assert missing.decision_status != errored.decision_status


def test_empty_evidence_and_errored_evidence_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), evidence=())
    errored = DecisionDetailArea(
        decision=_make_view(), evidence=(), evidence_status=ReadStatus.ERROR
    )

    assert empty.evidence == () and empty.evidence_status is ReadStatus.OK
    assert errored.evidence == () and errored.evidence_status is ReadStatus.ERROR


def test_empty_governance_and_errored_governance_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), governance=())
    errored = DecisionDetailArea(
        decision=_make_view(), governance=(), governance_status=ReadStatus.ERROR
    )

    assert empty.governance_status is ReadStatus.OK
    assert errored.governance_status is ReadStatus.ERROR


def test_empty_approvals_and_errored_approvals_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), approvals=())
    errored = DecisionDetailArea(
        decision=_make_view(), approvals=(), approvals_status=ReadStatus.ERROR
    )

    assert empty.approvals_status is ReadStatus.OK
    assert errored.approvals_status is ReadStatus.ERROR


def test_decision_detail_area_read_status_fields_are_immutable():
    area = DecisionDetailArea(decision=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.decision_status = ReadStatus.ERROR


def test_decision_detail_area_defaults_evidence_and_risk_reference_to_none():
    area = DecisionDetailArea(decision=_make_view())

    assert area.evidence_reference is None
    assert area.risk_reference is None


def test_decision_detail_area_carries_raw_evidence_and_risk_reference():
    area = DecisionDetailArea(
        decision=_make_view(), evidence_reference="evidence-001", risk_reference="risk-001",
    )

    assert area.evidence_reference == "evidence-001"
    assert area.risk_reference == "risk-001"


def test_decision_center_screen_composes_list_and_detail_areas():
    view = _make_view()
    list_area = DecisionListArea(decisions=[view])
    detail_area = DecisionDetailArea(decision=view)

    screen = DecisionCenterScreen(list_area=list_area, detail_area=detail_area)

    assert screen.list_area is list_area
    assert screen.detail_area is detail_area


# ===========================================================================
# ADR-070 Sprint 3 Batch 2 -- recommendation-surfacing presentation semantics.
# ===========================================================================

# Words/phrases that must never describe the confidence number. ("calibrated"
# is checked separately below -- "uncalibrated" legitimately contains it and
# is exactly the disclaimer ADR-070 §8 requires.)
_FORBIDDEN_CONFIDENCE_WORDS = (
    "probability", "likelihood", "certainty",
    "win probability", "chance of success", "confidence in success",
    "recommendation confidence", "probability of success",
    "calibrated confidence",
)
# Wording that would make the inert WAIT line imply a future event / urgency.
_FORBIDDEN_WAIT_WORDS = (
    "check back", "watch this", "opportunity", "wait for", "reassess",
    "will change", "later", "soon", "timer", "notification", "alert",
    "schedule", "re-evaluat", "reevaluat", "act now", "don't miss", "coming",
)


# --- provenance terminology (ADR-070 §6) ------------------------------------

def test_provenance_label_sentinel_is_a_sentinel_recommendation():
    assert provenance_label("SENTINEL") == "Sentinel recommendation"
    assert SENTINEL_RECOMMENDATION_LABEL == "Sentinel recommendation"


def test_provenance_label_strategy_is_an_interpreted_strategy_decision():
    assert provenance_label("STRATEGY") == "interpreted strategy decision"
    assert INTERPRETED_STRATEGY_DECISION_LABEL == "interpreted strategy decision"


def test_provenance_label_none_is_an_interpreted_strategy_decision():
    assert provenance_label(None) == "interpreted strategy decision"


def test_provenance_label_unexpected_value_is_an_interpreted_strategy_decision():
    for unexpected in ("sentinel", "Sentinel", "SENTINEL ", "AI", "", "STRATEGY_V2"):
        assert provenance_label(unexpected) == "interpreted strategy decision"


def test_is_sentinel_recommendation_is_exact_literal_only():
    assert is_sentinel_recommendation("SENTINEL") is True
    for other in ("STRATEGY", None, "sentinel", "SENTINEL ", "unknown"):
        assert is_sentinel_recommendation(other) is False


def test_provenance_is_not_inferred_from_action():
    """A BUY (or a WAIT) with no Sentinel provenance is still an interpreted
    strategy decision -- action never implies authorship."""
    buy_strategy = DecisionDetailArea(decision=_make_view(action="BUY", action_source="STRATEGY"))
    wait_legacy = DecisionDetailArea(decision=_make_view(action="WAIT", action_source=None))

    assert buy_strategy.recommendation_provenance_display == "interpreted strategy decision"
    assert buy_strategy.is_sentinel_recommendation is False
    assert wait_legacy.recommendation_provenance_display == "interpreted strategy decision"
    assert wait_legacy.is_sentinel_recommendation is False


def test_detail_area_provenance_display_none_when_no_decision():
    area = DecisionDetailArea(decision=None)
    assert area.recommendation_provenance_display is None
    assert area.is_sentinel_recommendation is False


def test_detail_area_sentinel_buy_is_a_sentinel_recommendation():
    area = DecisionDetailArea(decision=_make_view(action="BUY", action_source="SENTINEL"))
    assert area.recommendation_provenance_display == "Sentinel recommendation"
    assert area.is_sentinel_recommendation is True


# --- Sentinel WAIT (ADR-070 §7) -------------------------------------------

def test_sentinel_wait_produces_the_exact_inert_statement():
    area = DecisionDetailArea(decision=_make_view(action="WAIT", action_source="SENTINEL"))
    assert area.sentinel_non_concurrence_display == "Sentinel does not concur at this time."
    assert SENTINEL_NON_CONCURRENCE_STATEMENT == "Sentinel does not concur at this time."


def test_strategy_wait_does_not_get_the_sentinel_wait_wording():
    area = DecisionDetailArea(decision=_make_view(action="WAIT", action_source="STRATEGY"))
    assert area.sentinel_non_concurrence_display is None


def test_legacy_wait_does_not_get_the_sentinel_wait_wording():
    area = DecisionDetailArea(decision=_make_view(action="WAIT", action_source=None))
    assert area.sentinel_non_concurrence_display is None


def test_unexpected_provenance_wait_does_not_get_the_sentinel_wait_wording():
    area = DecisionDetailArea(decision=_make_view(action="WAIT", action_source="sentinel"))
    assert area.sentinel_non_concurrence_display is None


def test_sentinel_buy_gets_no_non_concurrence_statement():
    area = DecisionDetailArea(decision=_make_view(action="BUY", action_source="SENTINEL"))
    assert area.sentinel_non_concurrence_display is None


def test_sentinel_wait_helper_matches_the_property():
    assert sentinel_non_concurrence_statement("WAIT", "SENTINEL") == (
        "Sentinel does not concur at this time."
    )
    assert sentinel_non_concurrence_statement("BUY", "SENTINEL") is None
    assert sentinel_non_concurrence_statement("WAIT", "STRATEGY") is None
    assert sentinel_non_concurrence_statement("WAIT", None) is None


def test_sentinel_wait_statement_contains_no_scheduling_or_future_language():
    text = SENTINEL_NON_CONCURRENCE_STATEMENT.lower()
    for banned in _FORBIDDEN_WAIT_WORDS:
        assert banned not in text
    # It is a single, present-tense sentence -- nothing more.
    assert SENTINEL_NON_CONCURRENCE_STATEMENT == "Sentinel does not concur at this time."


# --- confidence semantics (ADR-070 §8) -----------------------------------

def test_confidence_numeric_value_is_preserved_exactly():
    area = DecisionDetailArea(decision=_make_view(confidence=0.78))
    assert area.confidence_display == "78%"  # unchanged from before Batch 2


def test_confidence_qualifier_is_the_uncalibrated_ensemble_score_wording():
    area = DecisionDetailArea(decision=_make_view(confidence=0.78))
    assert area.confidence_qualifier == "Uncalibrated ensemble model score"
    assert CONFIDENCE_QUALIFIER == "Uncalibrated ensemble model score"


def test_confidence_qualifier_is_none_when_no_decision():
    assert DecisionDetailArea(decision=None).confidence_qualifier is None


def test_confidence_qualifier_uses_no_probability_or_certainty_language():
    text = CONFIDENCE_QUALIFIER.lower()
    for banned in _FORBIDDEN_CONFIDENCE_WORDS:
        assert banned not in text
    # It must disclaim calibration, never claim it: the only permitted
    # occurrence of "calibrated" is inside "uncalibrated".
    assert "calibrated" not in text.replace("uncalibrated", "")
    assert "uncalibrated" in text


def test_confidence_display_and_qualifier_do_not_add_a_second_number():
    area = DecisionDetailArea(decision=_make_view(confidence=0.6123))
    # Only confidence_display carries a number; the qualifier is pure words.
    assert area.confidence_display == "61%"
    assert not any(ch.isdigit() for ch in area.confidence_qualifier)


# --- evidence polarity (ADR-070 §9) ------------------------------------

def test_evidence_polarity_label_supporting():
    assert evidence_polarity_label("SUPPORTING") == "Supported the BUY"


def test_evidence_polarity_label_contradicting():
    assert evidence_polarity_label("CONTRADICTING") == "Contradicted the BUY"


def test_evidence_polarity_label_none_missing_or_unknown_is_unavailable():
    for value in (None, "", "HOLD", "NEUTRAL", "supporting", "SUPPORTING "):
        assert evidence_polarity_label(value) == "Polarity unavailable"


def test_evidence_polarity_rows_are_per_record_and_keep_identity():
    area = DecisionDetailArea(
        decision=_make_view(action="BUY", action_source="SENTINEL"),
        evidence=(
            _make_entry(evidence_id="ev-xgb", source="xgboost", polarity="SUPPORTING"),
            _make_entry(evidence_id="ev-lstm", source="lstm", polarity="CONTRADICTING"),
            _make_entry(evidence_id="ev-fin", source="finbert", polarity=None),
        ),
    )

    rows = area.evidence_polarity_rows

    assert rows == (
        EvidencePolarityRow("ev-xgb", "xgboost", "Supported the BUY"),
        EvidencePolarityRow("ev-lstm", "lstm", "Contradicted the BUY"),
        EvidencePolarityRow("ev-fin", "finbert", "Polarity unavailable"),
    )
    # One row per evidence record -- nothing collapsed, nothing added.
    assert len(rows) == 3


def test_evidence_polarity_rows_empty_when_no_evidence():
    area = DecisionDetailArea(decision=_make_view())
    assert area.evidence_polarity_rows == ()


def test_detail_area_exposes_no_polarity_aggregate():
    """No count / majority / unanimity / net polarity / score / vote is
    reachable on the view-model, by attribute or by the polarity rows."""
    area = DecisionDetailArea(
        decision=_make_view(action="BUY", action_source="SENTINEL"),
        evidence=(
            _make_entry(evidence_id="ev-1", source="xgboost", polarity="SUPPORTING"),
            _make_entry(evidence_id="ev-2", source="lstm", polarity="SUPPORTING"),
            _make_entry(evidence_id="ev-3", source="finbert", polarity="CONTRADICTING"),
        ),
    )

    for forbidden in (
        "supporting_count", "contradicting_count", "polarity_count",
        "net_polarity", "polarity_score", "evidence_score", "corroboration",
        "corroboration_score", "unanimity", "unanimity_score", "majority",
        "vote", "vote_tally", "models_agree", "support_percentage",
        "recommendation_strength", "signal_strength",
    ):
        assert not hasattr(area, forbidden)

    rows = area.evidence_polarity_rows
    # The rows are plain per-record labels: only the three defined phrasings.
    assert {row.polarity_label for row in rows} <= {
        "Supported the BUY", "Contradicted the BUY", "Polarity unavailable",
    }
    # No row carries a numeric or aggregate field.
    for row in rows:
        assert set(vars(row).keys()) == {"evidence_id", "source", "polarity_label"}


# --- regression / boundary ---------------------------------------------

def test_batch2_properties_do_not_disturb_existing_core_formatting():
    area = DecisionDetailArea(
        decision=_make_view(
            action="WAIT", action_source="SENTINEL",
            confidence=0.78, status=DecisionState.DECISION_CREATED,
        ),
        evidence=(_make_entry(polarity="SUPPORTING"),),
    )

    # Pre-Batch-2 behavior, unchanged:
    assert area.confidence_display == "78%"
    assert area.status_display == "Decision Created"
    assert area.timestamp_display == "2026-08-04 07:00 CDT"
    # Batch 2 additions, alongside:
    assert area.recommendation_provenance_display == "Sentinel recommendation"
    assert area.sentinel_non_concurrence_display == "Sentinel does not concur at this time."
    assert area.confidence_qualifier == "Uncalibrated ensemble model score"


# --- Sprint 4 Item #3: decision_created_display (event-timeline enrichment) ---


def test_decision_created_display_is_none_when_no_decision_selected():
    area = DecisionDetailArea(decision=None)

    assert area.decision_created_display is None


def test_decision_created_display_is_none_when_timeline_has_no_events():
    """Missing optional timeline information is reported honestly -- never
    fabricated from updated_at or invented."""
    area = DecisionDetailArea(decision=_make_view(), audit_trail=())

    assert area.decision_created_display is None


def test_decision_created_display_is_none_when_timeline_has_no_decision_created_entry():
    other = _make_audit_entry(event_type="EVIDENCE_ATTACHED")
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(other,))

    assert area.decision_created_display is None


def test_decision_created_display_uses_the_decision_created_entry_timestamp():
    entry = _make_audit_entry(
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 21, 19, 45, 0),  # naive-UTC
    )
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(entry,))

    assert area.decision_created_display == "2026-08-21 14:45 CDT"


def test_decision_created_display_winter_timestamp_converts_to_cst():
    entry = _make_audit_entry(
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 1, 8, 15, 40, 0),
    )
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(entry,))

    assert area.decision_created_display == "2026-01-08 09:40 CST"


def test_decision_created_display_is_the_event_time_not_the_decision_updated_at():
    """The decision's updated_at is a different value with a different
    meaning -- decision_created_display must read the DECISION_CREATED
    event's own created_at, never updated_at."""
    view = _make_view(updated_at=datetime.datetime(2026, 8, 21, 23, 0, 0))  # -> 18:00 CDT
    entry = _make_audit_entry(
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 21, 19, 45, 0),  # -> 14:45 CDT
    )
    area = DecisionDetailArea(decision=view, audit_trail=(entry,))

    assert area.decision_created_display == "2026-08-21 14:45 CDT"
    assert area.timestamp_display == "2026-08-21 18:00 CDT"


def test_decision_created_display_takes_the_first_decision_created_entry_deterministically():
    first = _make_audit_entry(
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 21, 19, 45, 0),
    )
    second = _make_audit_entry(
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 21, 20, 30, 0),
    )
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(first, second))

    assert area.decision_created_display == "2026-08-21 14:45 CDT"


def test_decision_created_display_does_not_disturb_provenance_or_polarity():
    entry = _make_audit_entry(event_type="DECISION_CREATED")
    area = DecisionDetailArea(
        decision=_make_view(action_source="SENTINEL"),
        evidence=(_make_entry(polarity="CONTRADICTING"),),
        audit_trail=(entry,),
    )

    assert area.decision_created_display is not None
    assert area.recommendation_provenance_display == "Sentinel recommendation"
    assert area.evidence_polarity_rows[0].polarity_label == "Contradicted the BUY"


def test_batch2_presentation_helpers_are_pure_and_import_no_execution_deps():
    import applications.trading_intelligence.ui.decision_center.screen as screen_mod

    # Check import statements only -- the module docstring legitimately names
    # some of these words when stating the boundary it keeps.
    import_lines = [
        line for line in inspect.getsource(screen_mod).splitlines()
        if line.startswith(("import ", "from "))
    ]
    joined = "\n".join(import_lines)
    for banned in ("import bot", "from bot", "alpaca", "PaperExecutor",
                   "RiskManager", "recommendation_adapter",
                   "import sentinel_engine", "from sentinel_engine",
                   "dashboard", "ledger"):
        assert banned not in joined
