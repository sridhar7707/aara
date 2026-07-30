"""Tests for bot/eval/ablation.py: component ablation + hard-gate analysis.

Expected values are hand-computed from the real WEIGHTS/BUY_THRESHOLD/
BUY_FRACTION constants (imported, not hardcoded) so assertions stay
independent of the module's own implementation.
"""
from __future__ import annotations

import pandas as pd
import pytest

from bot.eval import ablation
from bot.strategy.ensemble import WEIGHTS, BUY_THRESHOLD, BUY_FRACTION
from config import ENTRY_REGIMES

_IN_REGIME = next(iter(ENTRY_REGIMES))
_OUT_OF_REGIME = "ZZZ_NOT_A_REAL_REGIME"


def _trade(**overrides) -> dict:
    row = {
        "xgb_prob": 0.60, "lstm_prob": 0.80, "sentiment_score": 0.20,
        "macro_score": 0.50, "regime": _IN_REGIME,
        "realized_pnl": 100.0, "notional": 5000.0, "portfolio_value": 100_000.0,
    }
    row.update(overrides)
    return row


def test_simulate_empty_trades_returns_empty_copy():
    empty = pd.DataFrame(columns=["xgb_prob"])
    out = ablation.simulate(empty)
    assert out.empty
    assert out is not empty


def test_simulate_filters_out_of_regime_trades_by_default():
    df = pd.DataFrame([_trade(regime=_IN_REGIME), _trade(regime=_OUT_OF_REGIME)])
    out = ablation.simulate(df)
    assert list(out["regime"]) == [_IN_REGIME]


def test_simulate_disable_regime_gate_keeps_out_of_regime_trades():
    df = pd.DataFrame([_trade(regime=_IN_REGIME), _trade(regime=_OUT_OF_REGIME)])
    out = ablation.simulate(df, disable_regime_gate=True)
    assert len(out) == 2


def test_simulate_xgb_ablation_keeps_trade_that_still_clears_threshold():
    # neutral xgb (0.5) + real lstm 0.80 + real sentiment 0.20 (-> norm 0.60)
    # score = 0.65*0.50 + 0.175*0.80 + 0.175*0.60 + 0.0*macro
    expected = WEIGHTS["xgb"] * 0.50 + WEIGHTS["lstm"] * 0.80 + WEIGHTS["sentiment"] * 0.60
    assert expected >= BUY_THRESHOLD  # sanity: this trade should survive

    df = pd.DataFrame([_trade(xgb_prob=0.60, lstm_prob=0.80, sentiment_score=0.20)])
    out = ablation.simulate(df, disabled={"xgb"})
    assert len(out) == 1
    assert out.loc[0, "ablated_score"] == pytest.approx(expected)


def test_simulate_xgb_ablation_drops_trade_that_falls_below_threshold():
    # same formula, but weaker lstm/sentiment push the recomputed score under BUY_THRESHOLD
    expected = WEIGHTS["xgb"] * 0.50 + WEIGHTS["lstm"] * 0.30 + WEIGHTS["sentiment"] * 0.30
    assert expected < BUY_THRESHOLD  # sanity: this trade should be excluded

    df = pd.DataFrame([_trade(xgb_prob=0.90, lstm_prob=0.30, sentiment_score=-0.40)])
    out = ablation.simulate(df, disabled={"xgb"})
    assert out.empty


def test_simulate_lstm_ablation_redistributes_weight_and_lifts_veto():
    # lstm disabled: xgb/sentiment weights renormalised over (xgb+sentiment) since macro weight is 0
    total_w = WEIGHTS["xgb"] + WEIGHTS["sentiment"] + WEIGHTS["macro"]
    w_xgb = WEIGHTS["xgb"] / total_w
    w_sent = WEIGHTS["sentiment"] / total_w
    expected = w_xgb * 0.60 + w_sent * 0.50  # sentiment_score=0.0 -> norm 0.50

    # lstm_prob=0.10 would trigger the live veto (indet=False, lstm<0.50) if lstm weren't disabled
    df = pd.DataFrame([_trade(xgb_prob=0.60, lstm_prob=0.10, sentiment_score=0.0)])
    out = ablation.simulate(df, disabled={"lstm"})
    assert len(out) == 1  # veto lifted because lstm is disabled
    assert out.loc[0, "ablated_score"] == pytest.approx(expected)


def test_simulate_lstm_veto_blocks_trade_when_lstm_not_disabled():
    # lstm_prob=0.10 is a confirmed low (non-indeterminate) signal -> veto fires
    # even though xgb-ablation alone would otherwise let the trade through.
    df = pd.DataFrame([_trade(xgb_prob=0.60, lstm_prob=0.10, sentiment_score=0.20)])
    out = ablation.simulate(df, disabled={"xgb"})
    assert out.empty


def test_simulate_flat_sizing_rescales_realized_pnl():
    flat_notional = BUY_FRACTION * 100_000.0
    expected_flat_pnl = 100.0 * (flat_notional / 5000.0)

    df = pd.DataFrame([_trade(realized_pnl=100.0, notional=5000.0, portfolio_value=100_000.0)])
    out = ablation.simulate(df, flat_sizing=True)
    assert out.loc[0, "flat_realized_pnl"] == pytest.approx(expected_flat_pnl)


def test_simulate_flat_sizing_skipped_without_required_columns():
    df = pd.DataFrame([{"xgb_prob": 0.6, "regime": _IN_REGIME}])
    out = ablation.simulate(df, flat_sizing=True)
    assert "flat_realized_pnl" not in out.columns


def test_gate_analysis_empty_signal_log_returns_empty_dict():
    assert ablation.gate_analysis(pd.DataFrame()) == {}


def test_gate_analysis_counts_regime_blocked_buy_signals():
    df = pd.DataFrame([
        {"ensemble_action": "BUY", "regime": _IN_REGIME},
        {"ensemble_action": "STRONG_BUY", "regime": _OUT_OF_REGIME},
        {"ensemble_action": "HOLD", "regime": _OUT_OF_REGIME},
        {"ensemble_action": "SELL", "regime": _IN_REGIME},
    ])
    result = ablation.gate_analysis(df)
    assert result["total_buy_signals"] == 2
    assert result["blocked_by_regime"] == 1
    assert result["pct_blocked_by_regime"] == pytest.approx(0.5)


def test_gate_analysis_without_regime_column_reports_zero_blocked():
    df = pd.DataFrame([{"ensemble_action": "BUY"}])
    result = ablation.gate_analysis(df)
    assert result["blocked_by_regime"] == 0


def test_lstm_veto_active_true_for_confirmed_low_signal():
    assert ablation._lstm_veto_active(pd.Series({"lstm_prob": 0.10})) is True


def test_lstm_veto_active_false_for_indeterminate_signal():
    assert ablation._lstm_veto_active(pd.Series({"lstm_prob": 0.50})) is False


def test_lstm_veto_active_false_for_confirmed_high_signal():
    assert ablation._lstm_veto_active(pd.Series({"lstm_prob": 0.90})) is False
