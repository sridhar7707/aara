"""Tests for applications.trading_intelligence.contracts.read_error."""
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError


def test_trading_intelligence_read_error_is_a_runtime_error():
    assert issubclass(TradingIntelligenceReadError, RuntimeError)


def test_trading_intelligence_read_error_carries_a_message():
    error = TradingIntelligenceReadError("could not read decision dec-001")
    assert str(error) == "could not read decision dec-001"


def test_trading_intelligence_read_error_preserves_the_original_exception_as_cause():
    original = ValueError("sqlite busy")
    try:
        try:
            raise original
        except ValueError as exc:
            raise TradingIntelligenceReadError("read failed") from exc
    except TradingIntelligenceReadError as caught:
        assert caught.__cause__ is original
