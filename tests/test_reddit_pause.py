"""ADR-094: Reddit sentiment is paused by default; no Reddit call is made while paused."""
import importlib

import pytest


def _module(monkeypatch, enabled):
    if enabled is None:
        monkeypatch.delenv("REDDIT_SENTIMENT_ENABLED", raising=False)
    else:
        monkeypatch.setenv("REDDIT_SENTIMENT_ENABLED", enabled)
    import bot.strategy.reddit_sentiment as rs
    return importlib.reload(rs)


def test_paused_by_default_and_never_touches_reddit(monkeypatch):
    rs = _module(monkeypatch, None)
    assert rs.REDDIT_SENTIMENT_ENABLED is False

    def must_not_call():
        raise AssertionError("Reddit must not be reached while paused")

    monkeypatch.setattr(rs, "_get_reddit", must_not_call)
    assert rs.get_wsb_sentiment("AAPL") == {"mentions": 0, "sentiment": 0.0}


def test_enabled_only_when_explicitly_switched_on(monkeypatch):
    rs = _module(monkeypatch, "1")
    assert rs.REDDIT_SENTIMENT_ENABLED is True
    _module(monkeypatch, None)  # restore the default for other tests
