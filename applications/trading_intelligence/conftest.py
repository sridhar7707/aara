"""Shared pytest fixtures for the AARA Trading Intelligence test suite.

`neutralize_trades_db_snapshot` (autouse) forces
`applications.trading_intelligence.bootstrap.fetch_trades_db_snapshot` to
return ``None`` for every test by default, so the suite never performs a
real HuggingFace download and every existing test keeps the deterministic
"no snapshot -> honest-unavailable / illustrative fallback" behavior it
was written against (the same state CI sees, where no ``HF_TOKEN`` is
set). Tests that specifically exercise the ADR-055 snapshot path
(``test_trades_db_snapshot.py``,
``test_bootstrap_trades_db_snapshot_wiring.py``) opt back in by
monkeypatching ``bootstrap.fetch_trades_db_snapshot`` themselves.
"""
import pytest


@pytest.fixture(autouse=True)
def neutralize_trades_db_snapshot(monkeypatch):
    try:
        from applications.trading_intelligence import bootstrap
    except Exception:
        return
    monkeypatch.setattr(bootstrap, "fetch_trades_db_snapshot", lambda: None)
