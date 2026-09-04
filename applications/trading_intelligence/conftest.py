"""Shared pytest fixtures for the AARA Trading Intelligence test suite.

`neutralize_trades_db_snapshot` (autouse) forces
`applications.trading_intelligence.bootstrap.fetch_trades_db_snapshot` to
return a NOT_CONFIGURED ``ReadResult`` (value ``None``) for every test by
default, so the suite never performs a real HuggingFace download and every
existing test keeps the deterministic "no snapshot -> honest-unavailable /
illustrative fallback" behavior it was written against (the same state CI
sees, where no ``HF_TOKEN`` is set). Post-ADR-061 (Category A / Amendment
1) `fetch_trades_db_snapshot` returns a `ReadResult`; `bootstrap` unwraps
its `.value`, so the stub must return a `ReadResult` whose value is
``None`` -- not a bare ``None``. Tests that specifically exercise the
ADR-055 snapshot path (``test_trades_db_snapshot.py``,
``test_bootstrap_trades_db_snapshot_wiring.py``) opt back in by
monkeypatching ``bootstrap.fetch_trades_db_snapshot`` themselves.
"""
import pytest

from applications.platform.integrations import IntegrationHealth, ReadResult


@pytest.fixture(autouse=True)
def neutralize_trades_db_snapshot(monkeypatch):
    # Import unguarded: if bootstrap cannot import, every test that would
    # reach fetch_trades_db_snapshot must fail loudly here, not silently
    # fall through to a live HuggingFace download.
    from applications.trading_intelligence import bootstrap

    monkeypatch.setattr(
        bootstrap,
        "fetch_trades_db_snapshot",
        lambda: ReadResult.failed(
            IntegrationHealth.not_configured("hf_trades_db_snapshot")
        ),
    )
    # Wave 3C: same defence for the ADR-064 Trust Ledger snapshot fetch
    # (already SPACE_ID-gated + fail-closed, but pinned here so a stray
    # SPACE_ID in some environment can never trigger a real download).
    # Tests that exercise the fetch itself monkeypatch it back.
    monkeypatch.setattr(
        bootstrap,
        "fetch_trust_ledger_db_snapshot",
        lambda: ReadResult.failed(
            IntegrationHealth.not_configured("hf_trust_ledger_db_snapshot")
        ),
    )
