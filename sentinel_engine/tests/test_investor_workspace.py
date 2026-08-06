"""Tests for sentinel_engine.application.investor_workspace.InvestorWorkspaceFacade."""
from sentinel_engine.application.investor_workspace import InvestorWorkspaceFacade


class _FakeMorningBriefQuery:
    def __init__(self, result):
        self._result = result
        self.call_count = 0

    def get_brief(self):
        self.call_count += 1
        return self._result


class _FakeDecisionQuery:
    def __init__(self, result):
        self._result = result
        self.received_decision_id = None

    def get_decision_timeline(self, decision_id):
        self.received_decision_id = decision_id
        return self._result


class _FakeDecisionCenterQuery:
    def __init__(self, result):
        self._result = result
        self.received_decision_id = None

    def get_decision_center(self, decision_id):
        self.received_decision_id = decision_id
        return self._result


def _make_facade(morning_brief_result=None, decision_history_result=None, decision_center_result=None):
    morning_brief_query = _FakeMorningBriefQuery(morning_brief_result)
    decision_query = _FakeDecisionQuery(decision_history_result)
    decision_center_query = _FakeDecisionCenterQuery(decision_center_result)
    facade = InvestorWorkspaceFacade(morning_brief_query, decision_query, decision_center_query)
    return facade, morning_brief_query, decision_query, decision_center_query


def test_get_morning_brief_delegates_to_morning_brief_query_unchanged():
    sentinel_result = object()
    facade, morning_brief_query, _, _ = _make_facade(morning_brief_result=sentinel_result)

    result = facade.get_morning_brief()

    assert result is sentinel_result
    assert morning_brief_query.call_count == 1


def test_get_decision_history_delegates_with_decision_id_unchanged():
    sentinel_result = object()
    facade, _, decision_query, _ = _make_facade(decision_history_result=sentinel_result)

    result = facade.get_decision_history("dec-001")

    assert result is sentinel_result
    assert decision_query.received_decision_id == "dec-001"


def test_get_decision_center_delegates_with_decision_id_unchanged():
    sentinel_result = object()
    facade, _, _, decision_center_query = _make_facade(decision_center_result=sentinel_result)

    result = facade.get_decision_center("dec-001")

    assert result is sentinel_result
    assert decision_center_query.received_decision_id == "dec-001"


def test_facade_works_with_plain_fakes_and_no_repositories_or_services():
    class _BareMorningBriefQuery:
        def get_brief(self):
            return "brief"

    class _BareDecisionQuery:
        def get_decision_timeline(self, decision_id):
            return f"timeline-for-{decision_id}"

    class _BareDecisionCenterQuery:
        def get_decision_center(self, decision_id):
            return f"center-for-{decision_id}"

    facade = InvestorWorkspaceFacade(
        _BareMorningBriefQuery(), _BareDecisionQuery(), _BareDecisionCenterQuery()
    )

    assert facade.get_morning_brief() == "brief"
    assert facade.get_decision_history("dec-042") == "timeline-for-dec-042"
    assert facade.get_decision_center("dec-042") == "center-for-dec-042"
