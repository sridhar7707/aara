"""Tests for applications.trading_intelligence.adapters.alpaca_news_source.

alpaca.data.historical.news.NewsClient is monkeypatched everywhere here --
these tests must never make a real network call to Alpaca.
"""
import ast
import inspect

from applications.trading_intelligence.adapters.alpaca_news_source import (
    AlpacaNewsSource,
    HoldingsNewsItem,
    OvernightHoldingsNews,
)


class _FakeArticle:
    def __init__(self, headline, symbols, source="Benzinga", url="https://example.test/a",
                 created_at="2026-08-27T02:00:00+00:00"):
        self.headline = headline
        self.symbols = symbols
        self.source = source
        self.url = url
        self.created_at = created_at


class _FakeNewsSet:
    """Mirrors alpaca-py's NewsSet: a .data dict keyed by "news"."""

    def __init__(self, articles):
        self.data = {"news": list(articles)}


class _FakeNewsClient:
    def __init__(self, key, secret, response=None, raise_on_get=False):
        self._response = response
        self._raise_on_get = raise_on_get
        self.last_request = None

    def get_news(self, request_params):
        self.last_request = request_params
        if self._raise_on_get:
            raise ConnectionError("simulated network failure")
        return self._response


def _patch_client(monkeypatch, **kwargs):
    created = {}

    def _factory(key, secret):
        client = _FakeNewsClient(key, secret, **kwargs)
        created["client"] = client
        return client

    monkeypatch.setattr("alpaca.data.historical.news.NewsClient", _factory)
    return created


def _source(**kwargs):
    kwargs.setdefault("api_key", "k")
    kwargs.setdefault("api_secret", "s")
    return AlpacaNewsSource(**kwargs)


def test_returns_items_for_valid_news_filtered_to_current_holdings(monkeypatch):
    response = _FakeNewsSet([
        _FakeArticle("Apple ships a thing", ["AAPL"], created_at="2026-08-27T05:00:00+00:00"),
        _FakeArticle("Microsoft cloud update", ["MSFT", "GOOGL"], created_at="2026-08-27T06:00:00+00:00"),
        _FakeArticle("Tesla unrelated headline", ["TSLA"], created_at="2026-08-27T07:00:00+00:00"),
    ])
    _patch_client(monkeypatch, response=response)

    result = _source().get_overnight_holdings_news(("AAPL", "MSFT"))

    assert isinstance(result, OvernightHoldingsNews)
    headlines = [item.headline for item in result.items]
    assert headlines == ["Microsoft cloud update", "Apple ships a thing"]  # newest first
    assert all(isinstance(item, HoldingsNewsItem) for item in result.items)
    # only the holdings symbols are retained on each item
    assert result.items[0].symbols == ("MSFT",)
    assert result.items[1].symbols == ("AAPL",)
    assert "TSLA" not in headlines[0] and "Tesla" not in " ".join(headlines)


def test_articles_with_no_overlap_with_holdings_are_filtered_out(monkeypatch):
    response = _FakeNewsSet([_FakeArticle("Tesla only", ["TSLA"])])
    _patch_client(monkeypatch, response=response)

    result = _source().get_overnight_holdings_news(("AAPL",))

    assert result == OvernightHoldingsNews(items=())
    assert result.is_empty


def test_empty_holdings_returns_empty_result_and_makes_no_network_call(monkeypatch):
    def _explode(key, secret):
        raise AssertionError("client must not be built when there are no holdings")

    monkeypatch.setattr("alpaca.data.historical.news.NewsClient", _explode)

    result = _source().get_overnight_holdings_news(())

    assert result == OvernightHoldingsNews(items=())
    assert result.is_empty


def test_successful_fetch_with_no_matching_article_returns_empty_not_none(monkeypatch):
    _patch_client(monkeypatch, response=_FakeNewsSet([]))

    result = _source().get_overnight_holdings_news(("AAPL", "MSFT"))

    assert result == OvernightHoldingsNews(items=())
    assert result is not None


def test_returns_none_on_malformed_provider_response_shape(monkeypatch):
    class _Garbage:
        data = "not-a-dict"

    _patch_client(monkeypatch, response=_Garbage())

    assert _source().get_overnight_holdings_news(("AAPL",)) is None


def test_returns_none_when_news_key_is_not_a_list(monkeypatch):
    class _Weird:
        data = {"news": "should-be-a-list"}

    _patch_client(monkeypatch, response=_Weird())

    assert _source().get_overnight_holdings_news(("AAPL",)) is None


def test_returns_none_when_credentials_are_missing(monkeypatch):
    def _explode(key, secret):
        raise AssertionError("client must not be built without credentials")

    monkeypatch.setattr("alpaca.data.historical.news.NewsClient", _explode)

    assert AlpacaNewsSource(api_key="", api_secret="").get_overnight_holdings_news(("AAPL",)) is None


def test_returns_none_on_network_or_api_failure(monkeypatch):
    _patch_client(monkeypatch, raise_on_get=True)

    assert _source().get_overnight_holdings_news(("AAPL",)) is None


def test_request_is_built_with_the_holdings_symbols(monkeypatch):
    created = _patch_client(monkeypatch, response=_FakeNewsSet([]))

    _source().get_overnight_holdings_news(("AAPL", "MSFT"))

    request = created["client"].last_request
    assert "AAPL" in request.symbols and "MSFT" in request.symbols
    assert request.start is not None  # bounded lookback window, not an unbounded scan


def test_holdings_symbols_are_deduped_and_uppercased(monkeypatch):
    created = _patch_client(monkeypatch, response=_FakeNewsSet([
        _FakeArticle("Apple headline", ["AAPL"]),
    ]))

    result = _source().get_overnight_holdings_news(("aapl", "AAPL", "msft"))

    request = created["client"].last_request
    assert request.symbols.count("AAPL") == 1
    assert "MSFT" in request.symbols
    assert [item.headline for item in result.items] == ["Apple headline"]


def test_headline_text_is_passed_through_unmodified(monkeypatch):
    _patch_client(monkeypatch, response=_FakeNewsSet([
        _FakeArticle("  Verbatim provider headline  ", ["AAPL"]),
    ]))

    result = _source().get_overnight_holdings_news(("AAPL",))

    assert result.items[0].headline == "Verbatim provider headline"


def test_articles_missing_a_headline_are_skipped_not_fatal(monkeypatch):
    _patch_client(monkeypatch, response=_FakeNewsSet([
        _FakeArticle("", ["AAPL"]),
        _FakeArticle("Real one", ["AAPL"]),
    ]))

    result = _source().get_overnight_holdings_news(("AAPL",))

    assert [item.headline for item in result.items] == ["Real one"]


def test_raw_dict_response_is_also_accepted(monkeypatch):
    _patch_client(monkeypatch, response={"news": [
        {"headline": "Dict-shaped article", "symbols": ["AAPL"], "source": "X",
         "url": "u", "created_at": "2026-08-27T01:00:00+00:00"},
    ]})

    result = _source().get_overnight_holdings_news(("AAPL",))

    assert [item.headline for item in result.items] == ["Dict-shaped article"]


def test_result_is_capped_at_max_items(monkeypatch):
    articles = [_FakeArticle(f"H{i}", ["AAPL"], created_at=f"2026-08-27T0{i}:00:00+00:00")
               for i in range(1, 6)]
    _patch_client(monkeypatch, response=_FakeNewsSet(articles))

    result = _source(max_items=2).get_overnight_holdings_news(("AAPL",))

    assert len(result.items) == 2


def test_module_imports_no_protected_package():
    """AST-level regression lock: this adapter must never import bot,
    dashboard, database, scheduler, or ledger."""
    import applications.trading_intelligence.adapters.alpaca_news_source as module

    tree = ast.parse(inspect.getsource(module))
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), f"forbidden import {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(forbidden), (
                f"forbidden import from {node.module!r}"
            )


def test_module_never_writes_and_never_places_orders():
    """Regression lock: read-only observation only -- the adapter's CODE
    (not its explanatory docstring) must never open a DB connection, run a
    mutating SQL statement, commit, or call any order-placing method."""
    import applications.trading_intelligence.adapters.alpaca_news_source as module

    code_only = inspect.getsource(module).split('"""', 2)[-1]
    for forbidden in (
        "submit_order", "cancel_order", "replace_order", "close_position",
        "close_all_positions", "sqlite3", ".execute(", ".commit(",
        "INSERT ", "UPDATE ", "DELETE ",
    ):
        assert forbidden not in code_only, f"adapter source must never reference {forbidden!r}"


def test_module_source_never_logs_or_formats_credentials():
    import applications.trading_intelligence.adapters.alpaca_news_source as module

    source = inspect.getsource(module)
    assert "print(" not in source
    assert "logger" not in source
    assert "logging" not in source


def test_module_imports_cleanly_when_top_level_config_is_unavailable():
    """Regression lock: the deployed Trading Intelligence HF Space does not
    stage top-level config.py. A module-level `from config import ...` with
    no fallback would crash the whole Space at import time. Run in an
    isolated subprocess so the simulated import block cannot pollute the
    rest of the test run."""
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
        "from applications.trading_intelligence.adapters.alpaca_news_source import (\n"
        "    ALPACA_KEY, ALPACA_SECRET, AlpacaNewsSource,\n"
        ")\n"
        "assert ALPACA_KEY == ''\n"
        "assert ALPACA_SECRET == ''\n"
        "assert AlpacaNewsSource().get_overnight_holdings_news(('AAPL',)) is None\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
