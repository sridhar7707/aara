"""Coverage for risk-gate and ensemble paths that were previously unexercised.

Backlog P0 items 2 and 3: sector_check's blocking branch, check_trailing_stop,
and the indeterminate-LSTM weight transfer, each asserted against a case
where a regression would change the outcome (not a case that passes either way).
"""
import pytest

from bot.risk.risk_manager import RiskManager
from bot.strategy.ensemble import _reweight_score, WEIGHTS
from config import MAX_SECTOR_POSITIONS, ATR_TRAIL_MULTIPLIER


# ── sector_check ─────────────────────────────────────────────────────────────

def test_sector_check_blocks_when_sector_is_full():
    rm = RiskManager()
    # AAPL and MSFT are both Technology; the limit is MAX_SECTOR_POSITIONS (2).
    open_positions = {"AAPL": object(), "MSFT": object()}
    assert MAX_SECTOR_POSITIONS == 2
    assert rm.sector_check("NVDA", open_positions) is False


def test_sector_check_allows_different_sector_when_one_is_full():
    rm = RiskManager()
    open_positions = {"AAPL": object(), "MSFT": object()}
    # JPM is financial; the technology sector being full must not block it.
    assert rm.sector_check("JPM", open_positions) is True


def test_sector_check_allows_when_under_limit():
    rm = RiskManager()
    assert rm.sector_check("NVDA", {"AAPL": object()}) is True


def test_sector_check_broad_etf_always_allowed():
    rm = RiskManager()
    open_positions = {"SPY": object(), "QQQ": object(), "IWM": object()}
    assert rm.sector_check("SPY", open_positions) is True


# ── check_trailing_stop ──────────────────────────────────────────────────────

def test_trailing_stop_triggers_at_trail_price():
    rm = RiskManager()
    hwm, atr = 100.0, 2.0
    trail_price = hwm - ATR_TRAIL_MULTIPLIER * atr  # 95.0 with 2.5×ATR
    assert rm.check_trailing_stop("AAPL", trail_price, hwm, atr) is True


def test_trailing_stop_does_not_trigger_just_above_trail():
    rm = RiskManager()
    hwm, atr = 100.0, 2.0
    trail_price = hwm - ATR_TRAIL_MULTIPLIER * atr
    assert rm.check_trailing_stop("AAPL", trail_price + 0.01, hwm, atr) is False


def test_trailing_stop_inert_without_valid_atr_or_hwm():
    rm = RiskManager()
    assert rm.check_trailing_stop("AAPL", 50.0, 100.0, 0.0) is False
    assert rm.check_trailing_stop("AAPL", 50.0, 0.0, 2.0) is False


# ── ensemble indeterminate-LSTM weight transfer ─────────────────────────────

def test_indeterminate_lstm_transfers_weight_to_xgb():
    """With lstm=0.5 (indeterminate) and xgb=0.9, the transfer must raise the
    score relative to the non-transfer split. A deleted transfer would make
    both calls return the same value and fail this test."""
    args = dict(xgb_prob=0.9, lstm_prob=0.5, sentiment_norm=0.5, macro_score=0.5)
    transferred = _reweight_score(**args, lstm_indeterminate=True)
    unchanged   = _reweight_score(**args, lstm_indeterminate=False)

    expected_transferred = (WEIGHTS["xgb"] + WEIGHTS["lstm"]) * 0.9 + WEIGHTS["sentiment"] * 0.5 + WEIGHTS["macro"] * 0.5
    expected_unchanged   = WEIGHTS["xgb"] * 0.9 + WEIGHTS["lstm"] * 0.5 + WEIGHTS["sentiment"] * 0.5 + WEIGHTS["macro"] * 0.5

    assert transferred == pytest.approx(expected_transferred)
    assert unchanged == pytest.approx(expected_unchanged)
    assert transferred > unchanged + 0.05  # the transfer is material, not a rounding artifact
