"""Tests for applications.trading_intelligence.adapters.alpaca_paper_source.

alpaca.trading.client.TradingClient is monkeypatched everywhere here --
these tests must never make a real network call to Alpaca.
"""
import ast
import inspect

from applications.trading_intelligence.adapters.alpaca_paper_source import AlpacaPaperSource


class _FakeAccount:
    def __init__(self, equity=100018.33, cash=59869.06, buying_power=351894.19, portfolio_value=100018.33):
        self.equity = equity
        self.cash = cash
        self.buying_power = buying_power
        self.portfolio_value = portfolio_value


class _FakeSide:
    def __init__(self, value):
        self.value = value


class _FakePosition:
    def __init__(self, symbol, qty, avg_entry_price, current_price, market_value,
                 unrealized_pl, unrealized_plpc, side="long"):
        self.symbol = symbol
        self.qty = qty
        self.avg_entry_price = avg_entry_price
        self.current_price = current_price
        self.market_value = market_value
        self.unrealized_pl = unrealized_pl
        self.unrealized_plpc = unrealized_plpc
        self.side = _FakeSide(side)


class _FakeTradingClient:
    def __init__(self, key, secret, paper, account=None, positions=None, raise_on=None):
        assert paper is True, "adapter must always request paper=True"
        self._account = account
        self._positions = positions if positions is not None else []
        self._raise_on = raise_on or set()

    def get_account(self):
        if "get_account" in self._raise_on:
            raise ConnectionError("simulated network failure")
        return self._account

    def get_all_positions(self):
        if "get_all_positions" in self._raise_on:
            raise ConnectionError("simulated network failure")
        return self._positions


def _patch_client(monkeypatch, **kwargs):
    def _factory(key, secret, paper):
        return _FakeTradingClient(key, secret, paper, **kwargs)

    monkeypatch.setattr("alpaca.trading.client.TradingClient", _factory)


def test_get_account_returns_a_real_snapshot_on_success(monkeypatch):
    _patch_client(monkeypatch, account=_FakeAccount())
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    snapshot = source.get_account()

    assert snapshot.equity == 100018.33
    assert snapshot.cash == 59869.06
    assert snapshot.buying_power == 351894.19
    assert snapshot.portfolio_value == 100018.33


def test_get_positions_returns_every_position_sorted_by_symbol(monkeypatch):
    positions = [
        _FakePosition("GOOGL", 34.68, 347.41, 340.5, 11809.78, -239.66, -0.0199, "long"),
        _FakePosition("AAPL", 19.11, 315.01, 310.21, 5928.53, -91.78, -0.0152, "long"),
    ]
    _patch_client(monkeypatch, positions=positions)
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    result = source.get_positions()

    assert [p.symbol for p in result] == ["AAPL", "GOOGL"]
    assert result[0].quantity == 19.11
    assert result[0].avg_entry_price == 315.01
    assert result[0].current_price == 310.21
    assert result[0].market_value == 5928.53
    assert result[0].unrealized_pl == -91.78
    assert result[0].unrealized_plpc == -0.0152
    assert result[0].side == "long"


def test_get_positions_returns_empty_tuple_for_a_flat_account(monkeypatch):
    """A paper account with zero open positions is a legitimate real
    result, distinct from an unavailable/failed call."""
    _patch_client(monkeypatch, positions=[])
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    assert source.get_positions() == ()


def test_get_account_returns_none_when_credentials_are_missing(monkeypatch):
    source = AlpacaPaperSource(api_key="", api_secret="", base_url="https://paper-api.alpaca.markets")

    assert source.get_account() is None


def test_get_positions_returns_none_when_credentials_are_missing(monkeypatch):
    source = AlpacaPaperSource(api_key="", api_secret="", base_url="https://paper-api.alpaca.markets")

    assert source.get_positions() is None


def test_get_account_returns_none_when_base_url_is_not_confirmed_paper(monkeypatch):
    """Environment must be explicitly confirmed paper -- an unrecognized
    or live-looking base_url must never silently proceed."""
    _patch_client(monkeypatch, account=_FakeAccount())
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://api.alpaca.markets")

    assert source.get_account() is None


def test_get_positions_returns_none_when_base_url_is_not_confirmed_paper(monkeypatch):
    _patch_client(monkeypatch, positions=[])
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://api.alpaca.markets")

    assert source.get_positions() is None


def test_client_is_always_constructed_with_paper_true_regardless_of_url(monkeypatch):
    """Even given a confirmed-paper URL, the SDK client itself must be
    hard-coded paper=True -- _FakeTradingClient's own constructor asserts
    this; a regression here would fail every test in this module, but
    this test names the guarantee explicitly."""
    _patch_client(monkeypatch, account=_FakeAccount())
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    assert source.get_account() is not None


def test_get_account_returns_none_on_network_failure(monkeypatch):
    _patch_client(monkeypatch, raise_on={"get_account"})
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    assert source.get_account() is None


def test_get_positions_returns_none_on_network_failure(monkeypatch):
    _patch_client(monkeypatch, raise_on={"get_all_positions"})
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    assert source.get_positions() is None


def test_get_account_returns_none_on_malformed_response(monkeypatch):
    """A response missing an expected attribute must fail safe, not
    crash -- e.g. a provider schema change or partial response."""
    class _Malformed:
        equity = 100.0
        # cash/buying_power/portfolio_value deliberately absent

    _patch_client(monkeypatch, account=_Malformed())
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    assert source.get_account() is None


def test_get_positions_returns_none_when_a_position_is_malformed(monkeypatch):
    class _Malformed:
        symbol = "AAPL"
        # every other field deliberately absent

    _patch_client(monkeypatch, positions=[_Malformed()])
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    assert source.get_positions() is None


def test_credentials_are_never_present_in_module_source():
    """Regression lock: the adapter's own source must never format,
    concatenate, or log the key/secret values themselves -- only pass
    them straight through to the SDK constructor."""
    import applications.trading_intelligence.adapters.alpaca_paper_source as module

    source = inspect.getsource(module)
    assert "print(" not in source
    assert "logger" not in source
    assert "logging" not in source


def test_module_never_calls_an_order_placing_method():
    """Regression lock: this adapter's actual CODE (not its explanatory
    module docstring, which discusses these methods by name precisely to
    disclaim them) must never call submit_order, cancel_order,
    replace_order, or any other write/execution method -- it is
    read-only observation only."""
    import applications.trading_intelligence.adapters.alpaca_paper_source as module

    source = inspect.getsource(module)
    code_only = source.split('"""', 2)[-1]
    for forbidden in ("submit_order", "cancel_order", "replace_order", "close_position", "close_all_positions"):
        assert forbidden not in code_only, f"adapter source must never reference {forbidden!r}"


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger -- it builds its own
    independent Alpaca client rather than importing
    bot.execution.alpaca_client (which also implements order execution)."""
    import applications.trading_intelligence.adapters.alpaca_paper_source as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(forbidden), (
                f"forbidden import from {module_name!r}"
            )
