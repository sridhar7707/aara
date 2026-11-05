"""ADR-080 §6: live-loop check through the real bot.main.run() cycle (Alpaca,
yfinance, sentiment and model calls are stubbed; entry gates and fills are real)."""
from types import SimpleNamespace
import numpy as np, pandas as pd
import bot.main as m
import bot._main_market as mk
from config import ENTRY_REGIMES
from bot.trust_ledger.connection import get_ledger_conn as _real_ledger

REGIME = sorted(ENTRY_REGIMES)[0]

class _Regime:
    def predict(self, row): return 0
    def regime_name(self, code): return REGIME

class _XGB:
    model = object()
    def predict_proba(self, row): return 0.9
    def calibrated_proba(self, row, raw_prob=None): return 0.9
    def explain(self, row): return []

class _LSTM:
    model = object()
    is_degraded = False
    val_loss = 0.5
    def predict_proba(self, bars): return 0.9

def _bars(n, seed=0, start="2026-11-02 14:00", freq="5min"):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                         "close": close, "volume": rng.integers(1e5, 2e5, n).astype(float)}, index=idx)

def _yf_download(syms, **kw):
    frames = {}
    for i, s in enumerate(list(syms) if not isinstance(syms, str) else [syms]):
        d = _bars(520, seed=i, start="2024-11-01", freq="1D").copy()
        d.index = d.index.tz_localize(None)
        frames[s] = d
    return pd.concat(frames, axis=1)

class _Client:
    api = None
    def __init__(self): self.buys = []
    def get_account(self): return SimpleNamespace(portfolio_value="100000", cash="50000")
    def get_account_summary(self): return {}
    def get_positions(self): return {}
    def get_open_order_symbols(self): return set(), set()
    def get_bars(self, symbol, timeframe="5Min", limit=100): return _bars(300)
    def get_latest_price(self, symbol): return 100.0
    def buy(self, symbol, notional, limit_price=None):
        self.buys.append(symbol); return {"order_id": f"ord-{symbol}"}
    def wait_for_fill(self, order_id, timeout_secs=15): return 10.0
    def get_fill_price(self, order_id): return 100.0
    def sell(self, *a, **k): return None
    def sell_market(self, *a, **k): return None

"""ADR-080 §6: live-loop check through the real bot.main.run() cycle (Alpaca,
yfinance, sentiment and model calls are stubbed; entry gates and fills are real)."""

def test_live_loop_places_a_buy(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "TRADE_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(m, "_HALT_FILE", str(tmp_path / "HALT"))
    monkeypatch.setattr(m, "get_ledger_conn", lambda: _real_ledger(str(tmp_path / "ledger.db")))
    monkeypatch.setattr(m, "_is_market_hours", lambda api: True)
    monkeypatch.setattr(m, "_load_today_universe", lambda: (["AAPL", "MSFT"], {}))
    monkeypatch.setattr(m, "_import_screener_picks", lambda con, p: None)
    monkeypatch.setattr(m, "batch_sentiment_scores", lambda *a, **k: {})
    monkeypatch.setattr(m, "get_wsb_sentiment", lambda *a, **k: 0.0)
    monkeypatch.setattr(m.tg, "_send", lambda *a, **k: None)
    monkeypatch.setattr(mk.yf, "download", _yf_download)
    client = _Client()
    m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    assert client.buys, "live loop placed no buys"

NON_TECH = ["JPM", "XOM", "UNH", "KO", "PG", "WMT", "CAT"]

def test_live_loop_respects_position_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "TRADE_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(m, "_HALT_FILE", str(tmp_path / "HALT"))
    monkeypatch.setattr(m, "get_ledger_conn", lambda: _real_ledger(str(tmp_path / "ledger.db")))
    monkeypatch.setattr(m, "_is_market_hours", lambda api: True)
    monkeypatch.setattr(m, "_load_today_universe", lambda: (["AAPL", "MSFT", "NVDA"], {}))
    monkeypatch.setattr(m, "_import_screener_picks", lambda con, p: None)
    monkeypatch.setattr(m, "batch_sentiment_scores", lambda *a, **k: {})
    monkeypatch.setattr(m, "get_wsb_sentiment", lambda *a, **k: 0.0)
    monkeypatch.setattr(m.tg, "_send", lambda *a, **k: None)
    monkeypatch.setattr(mk.yf, "download", _yf_download)
    client = _Client()
    pos = {s: SimpleNamespace(symbol=s, qty=10, market_value=1000.0, avg_entry_price=100.0,
                              unrealized_plpc=0.0, current_price=100.0) for s in NON_TECH}
    client.get_positions = lambda: pos
    m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    assert len(client.buys) <= 1, f"cap breached in live loop: {client.buys}"
