"""ADR-082: forward-test log rules, append-only behaviour and evaluation on a synthetic log."""
import numpy as np
import pandas as pd
import pytest

from scripts import forward_log as fl


def _closes(n=300, cols=("A", "B"), seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({c: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))) for c in cols}, index=idx)


def test_momentum_is_12_minus_1_month():
    c = _closes()
    s = fl.momentum_score(c)
    expected = c["A"].iloc[-1 - 21] / c["A"].iloc[-1 - 252] - 1
    assert s["A"] == pytest.approx(expected)


def test_momentum_refuses_short_history():
    with pytest.raises(ValueError):
        fl.momentum_score(_closes(n=100))


def test_trend_on_is_above_trailing_mean():
    c = pd.DataFrame({"UP": np.linspace(50, 150, 300), "DN": np.linspace(150, 50, 300)},
                     index=pd.bdate_range("2024-01-01", periods=300))
    t = fl.trend_on(c)
    assert bool(t["UP"]) is True
    assert bool(t["DN"]) is False


def test_snapshot_refuses_a_date_already_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(fl, "LOG_DIR", tmp_path)
    (tmp_path).mkdir(exist_ok=True)
    pd.DataFrame({"date": ["2026-11-06"], "symbol": ["A"], "score_momentum": [0.1], "trend_on": [None]}).to_csv(
        tmp_path / "scores.csv", index=False)
    with pytest.raises(fl.SkipDay, match="append-only"):
        fl.snapshot(today="2026-11-06", members=["A"])


def test_evaluate_recovers_a_planted_signal(tmp_path, monkeypatch):
    """A log where momentum truly predicts forward excess return should evaluate with a positive IC."""
    monkeypatch.setattr(fl, "LOG_DIR", tmp_path)
    rng = np.random.default_rng(3)
    days = pd.bdate_range("2020-01-01", periods=500)
    names = [f"S{i}" for i in range(40)]
    score = rng.normal(size=(len(days), len(names)))
    step = score * 0.004 + rng.normal(0, 0.01, (len(days), len(names)))   # score drives next-day return
    px = 100 * np.exp(np.cumsum(step, axis=0))
    spy = 100 * np.exp(np.cumsum(rng.normal(0, 0.005, len(days))))
    rows_p, rows_s = [], []
    for i, d in enumerate(days):
        for j, n in enumerate(names):
            rows_p.append((d.date().isoformat(), n, px[i, j]))
            rows_s.append((d.date().isoformat(), n, score[i, j], np.nan))
        rows_p.append((d.date().isoformat(), "SPY", spy[i]))
    pd.DataFrame(rows_p, columns=["date", "symbol", "close"]).to_csv(tmp_path / "prices.csv", index=False)
    pd.DataFrame(rows_s, columns=["date", "symbol", "score_momentum", "trend_on"]).to_csv(tmp_path / "scores.csv", index=False)
    r = fl.evaluate()
    assert r["days"] > 400
    assert r["full"].mean_ic > 0
