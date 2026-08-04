"""Tests for sentinel_engine.repositories.projection_repository.ProjectionRepository."""
import datetime

import pytest

from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.projections.decision_projection import DecisionProjection


def _make_projection(decision_id="dec-001", **overrides):
    defaults = dict(
        decision_id=decision_id,
        symbol="AAPL",
        action="BUY",
        status="DECISION_CREATED",
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


class _InMemoryProjectionRepository(ProjectionRepository):
    """Minimal conforming implementation used only to exercise the contract."""

    def __init__(self):
        self._projections = {}

    def save(self, projection):
        self._projections[projection.decision_id] = projection

    def get(self, decision_id):
        return self._projections.get(decision_id)


def test_projection_repository_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ProjectionRepository()


def test_get_returns_none_when_projection_not_found():
    repository = _InMemoryProjectionRepository()

    assert repository.get("missing-decision") is None


def test_save_then_get_returns_the_saved_projection():
    repository = _InMemoryProjectionRepository()
    projection = _make_projection()

    repository.save(projection)

    assert repository.get("dec-001") == projection


def test_save_overwrites_the_projection_for_the_same_decision_id():
    repository = _InMemoryProjectionRepository()
    original = _make_projection(status="DECISION_CREATED")
    updated = _make_projection(status="DECISION_EXECUTED")

    repository.save(original)
    repository.save(updated)

    assert repository.get("dec-001").status == "DECISION_EXECUTED"


def test_incomplete_projection_repository_subclass_cannot_be_instantiated():
    class _Incomplete(ProjectionRepository):
        def save(self, projection):
            pass
        # get deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
