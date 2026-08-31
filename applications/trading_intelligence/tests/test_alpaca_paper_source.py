"""Tests for applications.trading_intelligence.adapters.alpaca_paper_source.

alpaca.trading.client.TradingClient is monkeypatched everywhere here --
these tests must never make a real network call to Alpaca.

Post-ADR-061: get_account() / get_positions() return ReadResult[T]. A
HEALTHY result carries a real value (an empty positions tuple for a flat
account is a legitimate HEALTHY result); a non-HEALTHY result carries
value=None plus an IntegrationHealth naming the reason. "genuine empty"
(HEALTHY + ()) and "unavailable" (non-HEALTHY + None) are never conflated.
"""
import ast
import inspect

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.alpaca_paper_source import AlpacaPaperSource

_PAPER_URL = "https://paper-api.alpaca.markets"


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


def _source(**kwargs):
    kwargs.setdefault("api_key", "k")
    kwargs.setdefault("api_secret", "s")
    kwargs.setdefault("base_url", _PAPER_URL)
    return AlpacaPaperSource(**kwargs)


# --- happy path ----------------------------------------------------------

def test_get_account_returns_a_healthy_result_with_a_real_snapshot(monkeypatch):
    _patch_client(monkeypatch, account=_FakeAccount())

    result = _source().get_account()

    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    snapshot = result.value
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

    result = _source().get_positions()

    assert result.health.status is IntegrationStatus.HEALTHY
    parsed = result.value
    assert [p.symbol for p in parsed] == ["AAPL", "GOOGL"]
    assert parsed[0].quantity == 19.11
    assert parsed[0].avg_entry_price == 315.01
    assert parsed[0].current_price == 310.21
    assert parsed[0].market_value == 5928.53
    assert parsed[0].unrealized_pl == -91.78
    assert parsed[0].unrealized_plpc == -0.0152
    assert parsed[0].side == "long"


def test_get_positions_flat_account_is_healthy_with_an_empty_tuple(monkeypatch):
    """A paper account with zero open positions is a legitimate HEALTHY
    result -- distinct from an unavailable/failed read (non-HEALTHY, None)."""
    _patch_client(monkeypatch, positions=[])

    result = _source().get_positions()

    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == ()


# --- NOT_CONFIGURED --------------------------------------------------

def test_get_account_is_not_configured_when_credentials_are_missing(monkeypatch):
    result = AlpacaPaperSource(api_key="", api_secret="", base_url=_PAPER_URL).get_account()

    assert result.value is None
    assert result.health.status is IntegrationStatus.NOT_CONFIGURED


def test_get_positions_is_not_configured_when_credentials_are_missing(monkeypatch):
    result = AlpacaPaperSource(api_key="", api_secret="", base_url=_PAPER_URL).get_positions()

    assert result.value is None
    assert result.health.status is IntegrationStatus.NOT_CONFIGURED


def test_non_paper_base_url_is_not_configured_never_healthy_or_auth_failed(monkeypatch):
    """ADR-054 invariant, carried into the health contract: an
    unconfirmed / live-looking base_url must report NOT_CONFIGURED and can
    NEVER become HEALTHY or AUTH_FAILED."""
    _patch_client(monkeypatch, account=_FakeAccount(), positions=[])
    source = AlpacaPaperSource(api_key="k", api_secret="s", base_url="https://api.alpaca.markets")

    for result in (source.get_account(), source.get_positions()):
        assert result.value is None
        assert result.health.status is IntegrationStatus.NOT_CONFIGURED
        assert result.health.status is not IntegrationStatus.HEALTHY
        assert result.health.status is not IntegrationStatus.AUTH_FAILED


def test_client_is_always_constructed_with_paper_true_regardless_of_url(monkeypatch):
    """Even given a confirmed-paper URL, the SDK client itself must be
    hard-coded paper=True -- _FakeTradingClient's own constructor asserts
    this; a regression here would fail every test in this module, but
    this test names the guarantee explicitly."""
    _patch_client(monkeypatch, account=_FakeAccount())

    assert _source().get_account().health.status is IntegrationStatus.HEALTHY


# --- UNAVAILABLE ---------------------------------------------------

def test_get_account_is_unavailable_on_network_failure(monkeypatch):
    _patch_client(monkeypatch, raise_on={"get_account"})

    result = _source().get_account()

    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_get_positions_is_unavailable_on_network_failure(monkeypatch):
    _patch_client(monkeypatch, raise_on={"get_all_positions"})

    result = _source().get_positions()

    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


# --- API_ERROR ---------------------------------------------------

def test_get_account_is_api_error_on_malformed_response(monkeypatch):
    """A response missing an expected attribute must fail safe with a
    classified reason, not crash -- e.g. a provider schema change."""
    class _Malformed:
        equity = 100.0
        # cash/buying_power/portfolio_value deliberately absent

    _patch_client(monkeypatch, account=_Malformed())

    result = _source().get_account()

    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_get_positions_is_api_error_when_a_position_is_malformed(monkeypatch):
    class _Malformed:
        symbol = "AAPL"
        # every other field deliberately absent

    _patch_client(monkeypatch, positions=[_Malformed()])

    result = _source().get_positions()

    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


# --- credential hygiene (ADR-061 Section 2.9) -------------------

def test_credential_values_never_appear_in_integration_health(monkeypatch):
    _patch_client(monkeypatch, raise_on={"get_account"})
    source = AlpacaPaperSource(api_key="SECRET-KEY-123", api_secret="SECRET-SECRET-456", base_url=_PAPER_URL)

    health = source.get_account().health

    assert "SECRET-KEY-123" not in repr(health)
    assert "SECRET-SECRET-456" not in repr(health)


# --- regression locks (unchanged) --------------------------------

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


def test_module_imports_cleanly_when_top_level_config_is_unavailable():
    """Regression lock for a real production incident: the deployed
    Trading Intelligence HF Space stages only applications/,
    sentinel_engine/, and brand/logos/ (see
    .github/workflows/deploy_trading_intelligence.yml) -- top-level
    config.py is never present there. A module-level `from config import
    ...` with no fallback previously crashed the entire Space at import
    time. Run in an isolated subprocess (rather than mutating
    sys.modules/builtins.__import__ in-process, which would leave a
    second AlpacaPaperSource class object behind and silently break every
    other test in this suite that imports/patches the real one) so this
    simulation can never pollute the rest of the test run."""
    import subprocess
    import sys

    script = (
        "import builtins\n"
        "_orig = builtins.__import__\n"
        "def _blocked(name, globals=None, locals=None, fromlist=(), level=0):\n"
        "    if name == 'config' and level == 0:\n"
        "        raise ImportError('simulated: config not staged in HF Space')\n"
        "    return _orig(name, globals, locals, fromlist, level)\n"
        "builtins.__import__ = _blocked\n"
        "from applications.platform.integrations import IntegrationStatus\n"
        "from applications.trading_intelligence.adapters.alpaca_paper_source import (\n"
        "    ALPACA_KEY, ALPACA_SECRET, AlpacaPaperSource,\n"
        ")\n"
        "assert ALPACA_KEY == ''\n"
        "assert ALPACA_SECRET == ''\n"
        "source = AlpacaPaperSource()\n"
        "acc = source.get_account()\n"
        "pos = source.get_positions()\n"
        "assert acc.value is None and acc.health.status is IntegrationStatus.NOT_CONFIGURED\n"
        "assert pos.value is None and pos.health.status is IntegrationStatus.NOT_CONFIGURED\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
