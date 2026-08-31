"""Tests for applications.trading_intelligence.adapters.alpaca_paper_orders_source.

alpaca.trading.client.TradingClient is monkeypatched everywhere here --
these tests must never make a real network call to Alpaca. The real
alpaca-py request/enum classes ARE exercised (GetOrdersRequest,
QueryOrderStatus, Sort) since constructing them is offline and pure.

Post-ADR-061: get_recent_orders() returns ReadResult[AlpacaOrdersSnapshot].
A HEALTHY result carries a real snapshot (an empty snapshot -- "connected,
no recent orders" -- is a legitimate HEALTHY result); a non-HEALTHY result
carries value=None plus an IntegrationHealth naming the reason.
"""
import ast
import inspect
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters.alpaca_paper_orders_source import (
    AlpacaPaperOrdersSource,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    AlpacaOrder,
    AlpacaOrdersSnapshot,
)

_PAPER_URL = "https://paper-api.alpaca.markets"


class _Enumish:
    def __init__(self, value):
        self.value = value


class _FakeOrder:
    def __init__(
        self,
        id="ord-1",
        symbol="AAPL",
        side="buy",
        status="filled",
        order_type="market",
        qty="10",
        filled_qty="10",
        limit_price=None,
        submitted_at=None,
        filled_at=None,
    ):
        self.id = id
        self.symbol = symbol
        self.side = _Enumish(side)
        self.status = _Enumish(status)
        self.order_type = _Enumish(order_type)
        self.type = self.order_type
        self.qty = qty
        self.filled_qty = filled_qty
        self.limit_price = limit_price
        self.submitted_at = (
            submitted_at
            if submitted_at is not None
            else datetime(2026, 8, 27, 14, 0, tzinfo=timezone.utc)
        )
        self.filled_at = filled_at
        # Fields the projection must never carry through -- present on the
        # provider row, deliberately not read.
        self.client_order_id = "client-" + str(id)
        self.order_class = _Enumish("simple")
        self.legs = None


class _FakeTradingClient:
    def __init__(self, key, secret, paper, open_orders=None, closed_orders=None, raise_on=None):
        assert paper is True, "adapter must always request paper=True"
        self._open = list(open_orders) if open_orders is not None else []
        self._closed = list(closed_orders) if closed_orders is not None else []
        self._raise_on = raise_on or set()
        self.requests = []

    def get_orders(self, filter=None):
        self.requests.append(filter)
        status_value = getattr(getattr(filter, "status", None), "value", None)
        if status_value == "open":
            if "open" in self._raise_on:
                raise ConnectionError("simulated network failure (open)")
            return list(self._open)
        if "closed" in self._raise_on:
            raise ConnectionError("simulated network failure (closed)")
        return list(self._closed)


def _patch_client(monkeypatch, **kwargs):
    created = {}

    def _factory(key, secret, paper):
        client = _FakeTradingClient(key, secret, paper, **kwargs)
        created["client"] = client
        return client

    monkeypatch.setattr("alpaca.trading.client.TradingClient", _factory)
    return created


def _source(**kwargs):
    kwargs.setdefault("api_key", "k")
    kwargs.setdefault("api_secret", "s")
    kwargs.setdefault("base_url", _PAPER_URL)
    return AlpacaPaperOrdersSource(**kwargs)


def _orders(result):
    assert isinstance(result, ReadResult)
    assert result.health.status is IntegrationStatus.HEALTHY
    return result.value


# --- happy path -------------------------------------------------------------


def test_returns_a_healthy_typed_snapshot_merging_open_and_closed(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="open-1", status="new")],
        closed_orders=[_FakeOrder(id="closed-1", status="filled")],
    )

    snapshot = _orders(_source().get_recent_orders())

    assert isinstance(snapshot, AlpacaOrdersSnapshot)
    assert {o.order_id for o in snapshot.orders} == {"open-1", "closed-1"}
    assert all(isinstance(o, AlpacaOrder) for o in snapshot.orders)
    assert snapshot.truncated is False


def test_client_is_always_constructed_with_paper_true(monkeypatch):
    _patch_client(monkeypatch, open_orders=[_FakeOrder()])

    assert _source().get_recent_orders().health.status is IntegrationStatus.HEALTHY


def test_empty_result_is_a_healthy_empty_snapshot_not_unavailable(monkeypatch):
    _patch_client(monkeypatch, open_orders=[], closed_orders=[])

    result = _source().get_recent_orders()

    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == AlpacaOrdersSnapshot(orders=(), truncated=False)
    assert result.value.is_empty


# --- NOT_CONFIGURED ----------------------------------------------------


def test_not_configured_when_credentials_are_missing(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("client must not be built without credentials")

    monkeypatch.setattr("alpaca.trading.client.TradingClient", _explode)

    result = AlpacaPaperOrdersSource(api_key="", api_secret="", base_url=_PAPER_URL).get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.NOT_CONFIGURED


def test_non_paper_base_url_is_not_configured_never_healthy_or_auth_failed(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("client must not be built for an unconfirmed environment")

    monkeypatch.setattr("alpaca.trading.client.TradingClient", _explode)

    result = AlpacaPaperOrdersSource(
        api_key="k", api_secret="s", base_url="https://api.alpaca.markets"
    ).get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.NOT_CONFIGURED
    assert result.health.status is not IntegrationStatus.HEALTHY
    assert result.health.status is not IntegrationStatus.AUTH_FAILED


def test_not_configured_when_sdk_client_construction_raises_importerror(monkeypatch):
    def _raises(*args, **kwargs):
        raise ImportError("simulated alpaca-py not installed")

    monkeypatch.setattr("alpaca.trading.client.TradingClient", _raises)

    result = _source().get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.NOT_CONFIGURED


# --- UNAVAILABLE -----------------------------------------------------


def test_unavailable_when_the_open_call_fails(monkeypatch):
    _patch_client(monkeypatch, raise_on={"open"}, closed_orders=[_FakeOrder(id="c")])

    result = _source().get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_unavailable_when_the_closed_call_fails(monkeypatch):
    _patch_client(monkeypatch, raise_on={"closed"}, open_orders=[_FakeOrder(id="o")])

    result = _source().get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


# --- API_ERROR -----------------------------------------------------


@pytest.mark.parametrize(
    "bad_order",
    [
        _FakeOrder(id="", symbol="AAPL"),
        _FakeOrder(id="x", symbol=""),
        _FakeOrder(id="x", submitted_at="2026-08-27T14:00:00Z"),  # str, not a datetime
        _FakeOrder(id="x", submitted_at=1_756_303_200),  # int epoch, not a datetime
        _FakeOrder(id="x", side=""),
        _FakeOrder(id="x", status=""),
        _FakeOrder(id="x", filled_at="2026-08-27T15:00:00Z"),  # malformed filled_at
    ],
)
def test_a_single_malformed_row_makes_the_whole_result_api_error(monkeypatch, bad_order):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="good-1")],
        closed_orders=[bad_order],
    )

    result = _source().get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


def test_malformed_row_in_the_open_call_also_makes_the_whole_result_api_error(monkeypatch):
    _patch_client(monkeypatch, open_orders=[_FakeOrder(id="x", symbol="")])

    result = _source().get_recent_orders()
    assert result.value is None
    assert result.health.status is IntegrationStatus.API_ERROR


# --- merge / dedupe / ordering -----------------------------------------


def test_dedupes_by_order_id_with_the_open_row_winning(monkeypatch):
    """An order present in both the open and closed responses appears once,
    and keeps the open-query's working flag."""
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="dup", status="new")],
        closed_orders=[_FakeOrder(id="dup", status="canceled")],
    )

    snapshot = _orders(_source().get_recent_orders())

    assert [o.order_id for o in snapshot.orders] == ["dup"]
    only = snapshot.orders[0]
    assert only.status == "new"  # open-query row won
    assert only.is_working is True


def test_orders_are_sorted_newest_first_with_order_id_tiebreak(monkeypatch):
    t_early = datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 8, 27, 16, 0, tzinfo=timezone.utc)
    _patch_client(
        monkeypatch,
        open_orders=[
            _FakeOrder(id="b", status="new", submitted_at=t_early),
            _FakeOrder(id="a", status="new", submitted_at=t_late),
        ],
        closed_orders=[
            _FakeOrder(id="d", submitted_at=t_late),
            _FakeOrder(id="c", submitted_at=t_late),
        ],
    )

    snapshot = _orders(_source().get_recent_orders())

    # t_late group first, order_id descending within equal timestamps; then t_early.
    assert [o.order_id for o in snapshot.orders] == ["d", "c", "a", "b"]


# --- cap / truncation -------------------------------------------------


def test_truncated_is_true_when_the_open_call_hits_the_cap(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id=f"o{i}", status="new") for i in range(2)],
    )

    snapshot = _orders(_source(per_call_cap=2).get_recent_orders())

    assert snapshot.truncated is True
    assert len(snapshot.orders) == 2


def test_truncated_is_true_when_the_closed_call_hits_the_cap(monkeypatch):
    _patch_client(
        monkeypatch,
        closed_orders=[_FakeOrder(id=f"c{i}") for i in range(3)],
    )

    snapshot = _orders(_source(per_call_cap=3).get_recent_orders())

    assert snapshot.truncated is True


def test_truncated_is_false_when_both_calls_are_under_the_cap(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="o1", status="new")],
        closed_orders=[_FakeOrder(id="c1")],
    )

    snapshot = _orders(_source(per_call_cap=50).get_recent_orders())

    assert snapshot.truncated is False


# --- working / pending handling -------------------------------------


def test_every_open_query_row_is_flagged_working_regardless_of_status(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="o", status="a-status-not-in-any-known-set")],
    )

    snapshot = _orders(_source().get_recent_orders())

    assert snapshot.orders[0].is_working is True
    assert snapshot.orders[0].status == "a-status-not-in-any-known-set"  # still verbatim


def test_closed_query_rows_are_flagged_working_only_for_live_statuses(monkeypatch):
    _patch_client(
        monkeypatch,
        closed_orders=[
            _FakeOrder(id="live", status="pending_new"),
            _FakeOrder(id="done", status="filled"),
        ],
    )

    snapshot = _orders(_source().get_recent_orders())

    by_id = {o.order_id: o for o in snapshot.orders}
    assert by_id["live"].is_working is True
    assert by_id["done"].is_working is False


def test_partially_filled_is_treated_as_working(monkeypatch):
    _patch_client(monkeypatch, closed_orders=[_FakeOrder(id="p", status="partially_filled")])

    snapshot = _orders(_source().get_recent_orders())

    assert snapshot.orders[0].is_working is True


# --- field contract ------------------------------------------------


def test_side_and_status_are_broker_verbatim(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="o", side="sell", status="partially_filled")],
    )

    order = _orders(_source().get_recent_orders()).orders[0]

    assert order.side == "sell"
    assert order.status == "partially_filled"


def test_optional_numeric_fields_pass_through_as_strings(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[
            _FakeOrder(id="o", status="new", qty="5", filled_qty="0", limit_price="123.45"),
        ],
    )

    order = _orders(_source().get_recent_orders()).orders[0]

    assert order.quantity == "5"
    assert order.filled_quantity == "0"
    assert order.limit_price == "123.45"


def test_absent_limit_price_and_filled_at_are_not_fatal(monkeypatch):
    _patch_client(
        monkeypatch,
        open_orders=[_FakeOrder(id="o", status="new", limit_price=None, filled_at=None)],
    )

    order = _orders(_source().get_recent_orders()).orders[0]

    assert order.limit_price == ""
    assert order.filled_at is None


def test_projection_never_carries_strategy_metadata(monkeypatch):
    _patch_client(monkeypatch, open_orders=[_FakeOrder(id="o", status="new")])

    order = _orders(_source().get_recent_orders()).orders[0]

    for forbidden in ("client_order_id", "order_class", "legs", "notes", "strategy"):
        assert not hasattr(order, forbidden), f"{forbidden!r} must not appear on AlpacaOrder"


def test_order_id_is_stringified_from_a_uuid(monkeypatch):
    real_uuid = uuid.uuid4()
    _patch_client(monkeypatch, open_orders=[_FakeOrder(id=real_uuid, status="new")])

    order = _orders(_source().get_recent_orders()).orders[0]

    assert order.order_id == str(real_uuid)
    assert isinstance(order.order_id, str)


# --- request shape ------------------------------------------------


def test_both_calls_use_a_defensive_cap_and_the_closed_call_is_bounded_to_14_days(monkeypatch):
    created = _patch_client(monkeypatch, open_orders=[], closed_orders=[])

    _source().get_recent_orders()

    requests = created["client"].requests
    assert len(requests) == 2

    by_status = {getattr(r.status, "value", None): r for r in requests}
    open_req = by_status["open"]
    closed_req = by_status["closed"]

    assert open_req.limit == 50
    assert open_req.after is None  # OPEN: no time filter

    assert closed_req.limit == 50
    assert closed_req.after is not None
    assert closed_req.after.tzinfo is not None
    window = datetime.now(timezone.utc) - closed_req.after
    assert timedelta(days=13, hours=23) < window < timedelta(days=14, hours=1)


def test_does_not_build_a_client_when_environment_is_not_paper(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "alpaca.trading.client.TradingClient",
        lambda *a, **k: calls.append((a, k)),
    )

    AlpacaPaperOrdersSource(api_key="k", api_secret="s", base_url="").get_recent_orders()

    assert calls == []


# --- regression locks ------------------------------------------------


def test_module_never_references_an_execution_or_history_method():
    """The adapter's CODE (not its explanatory docstring, which names these
    methods precisely to disclaim them) must never call any order-placing/
    cancelling method, get_account_activities, get_portfolio_history, or any
    DB write."""
    import applications.trading_intelligence.adapters.alpaca_paper_orders_source as module

    code_only = inspect.getsource(module).split('"""', 2)[-1]
    for forbidden in (
        "submit_order", "cancel_order", "replace_order", "close_position",
        "close_all_positions", "get_account_activities", "get_portfolio_history",
        "sqlite3", ".execute(", ".commit(", "INSERT ", "UPDATE ", "DELETE ",
    ):
        assert forbidden not in code_only, f"adapter code must never reference {forbidden!r}"


def test_module_imports_no_protected_or_cross_adapter_package():
    """AST-level lock: never import bot, dashboard, database, scheduler,
    ledger, sentinel_engine, or the sibling alpaca_paper_source adapter --
    the recent-orders channel builds its own independent client and its
    availability is independent of the account/positions channel."""
    import applications.trading_intelligence.adapters.alpaca_paper_orders_source as module

    tree = ast.parse(inspect.getsource(module))
    forbidden = ("bot", "dashboard", "database", "scheduler", "ledger", "sentinel_engine")

    def _check(name):
        assert not name.startswith(forbidden), f"forbidden import {name!r}"
        assert "alpaca_paper_source" not in name, f"must not import the account adapter ({name!r})"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check(alias.name)
        elif isinstance(node, ast.ImportFrom):
            _check(node.module or "")


def test_module_source_never_logs_or_formats_credentials():
    import applications.trading_intelligence.adapters.alpaca_paper_orders_source as module

    source = inspect.getsource(module)
    assert "print(" not in source
    assert "logger" not in source
    assert "logging" not in source


def test_module_imports_cleanly_when_top_level_config_is_unavailable():
    """Regression lock for the same production incident as the other two
    Alpaca adapters: the deployed Trading Intelligence HF Space does not
    stage top-level config.py. A module-level `from config import ...` with
    no fallback would crash the whole Space at import time. Run in an
    isolated subprocess so the simulated import block cannot pollute the
    rest of the test run."""
    script = (
        "import builtins\n"
        "_orig = builtins.__import__\n"
        "def _blocked(name, globals=None, locals=None, fromlist=(), level=0):\n"
        "    if name == 'config' and level == 0:\n"
        "        raise ImportError('simulated: config not staged in HF Space')\n"
        "    return _orig(name, globals, locals, fromlist, level)\n"
        "builtins.__import__ = _blocked\n"
        "from applications.platform.integrations import IntegrationStatus\n"
        "from applications.trading_intelligence.adapters.alpaca_paper_orders_source import (\n"
        "    ALPACA_KEY, ALPACA_SECRET, AlpacaPaperOrdersSource,\n"
        ")\n"
        "assert ALPACA_KEY == ''\n"
        "assert ALPACA_SECRET == ''\n"
        "r = AlpacaPaperOrdersSource().get_recent_orders()\n"
        "assert r.value is None and r.health.status is IntegrationStatus.NOT_CONFIGURED\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
