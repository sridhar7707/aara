"""Tests for dashboard.components.loss_explanation."""
import pytest

from bot._main_db import init_db, log_trade
import dashboard.components.loss_explanation as le


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "loss_test.db")
    con = init_db(db_path)
    monkeypatch.setattr(le, "DB_PATH", db_path)
    return con


def test_empty_state_when_no_closed_trades(db):
    html = le.render_loss_explanation()
    assert "No closed trades yet" in html


def test_empty_state_when_no_losses(db):
    log_trade(db, "AAPL", "BUY", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "AAPL", "SELL_TIME_EXIT", 5.0, 110.0, 550.0, "TRENDING_UP", 10000.0, 0.10)
    html = le.render_loss_explanation()
    assert "No losses yet" in html


def test_lists_only_losses_not_wins(db):
    log_trade(db, "AAPL", "BUY", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.0,
              xgb_prob=0.6, lstm_prob=0.6)
    log_trade(db, "AAPL", "SELL_TIME_EXIT", 5.0, 110.0, 550.0, "TRENDING_UP", 10000.0, 0.10)
    log_trade(db, "MSFT", "BUY", 5.0, 200.0, 1000.0, "TRENDING_UP", 10000.0, 0.0,
              xgb_prob=0.6, lstm_prob=0.6)
    log_trade(db, "MSFT", "SELL_STOP", 5.0, 190.0, 950.0, "TRENDING_UP", 10000.0, -0.05)
    html = le.render_loss_explanation()
    assert "MSFT" in html
    assert "AAPL" not in html
    assert "1 of 2 completed trades" in html


def test_excludes_sell_reconcile_and_sell_trim(db):
    """Both must stay invisible here too — inherited for free from loader.py's fix."""
    log_trade(db, "GOOGL", "BUY", 1.0, 300.0, 300.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "GOOGL", "SELL_RECONCILE", 1.0, 100.0, 100.0, "reconcile", 10000.0, -0.6667)
    html = le.render_loss_explanation()
    assert "No closed trades yet" in html


def test_below_baseline_shows_needs_more_data_instead_of_a_verdict(db):
    """Fewer than _MIN_FOR_BASELINE closed trades -> no confidence claim, just a note."""
    log_trade(db, "AAPL", "BUY", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.0,
              xgb_prob=0.6, lstm_prob=0.6)
    log_trade(db, "AAPL", "SELL_STOP", 5.0, 95.0, 475.0, "TRENDING_UP", 10000.0, -0.05)
    html = le.render_loss_explanation()
    assert "Bad decision" not in html
    assert "Bad luck" not in html
    assert "baseline" in html.lower()


def test_below_average_confidence_labeled_bad_decision(db):
    # 4 wins at a high confidence (xgb=lstm=0.75 -> ensemble ~0.706), 1 loss at a
    # much lower confidence (xgb=lstm=0.45 -> ensemble ~0.459) -> clearly below average.
    for i in range(4):
        log_trade(db, f"WIN{i}", "BUY", 1.0, 100.0, 100.0, "TRENDING_UP", 10000.0, 0.0,
                  xgb_prob=0.75, lstm_prob=0.75)
        log_trade(db, f"WIN{i}", "SELL_TIME_EXIT", 1.0, 105.0, 105.0, "TRENDING_UP", 10000.0, 0.05)
    log_trade(db, "WEAK", "BUY", 1.0, 100.0, 100.0, "TRENDING_UP", 10000.0, 0.0,
              xgb_prob=0.45, lstm_prob=0.45)
    log_trade(db, "WEAK", "SELL_STOP", 1.0, 95.0, 95.0, "TRENDING_UP", 10000.0, -0.05)
    html = le.render_loss_explanation()
    assert "Bad decision" in html


def test_above_average_confidence_labeled_bad_luck(db):
    # 4 wins at a low confidence (xgb=lstm=0.45 -> ensemble ~0.459), 1 loss at a
    # much higher confidence (xgb=lstm=0.75 -> ensemble ~0.706) -> clearly above average.
    for i in range(4):
        log_trade(db, f"WIN{i}", "BUY", 1.0, 100.0, 100.0, "TRENDING_UP", 10000.0, 0.0,
                  xgb_prob=0.45, lstm_prob=0.45)
        log_trade(db, f"WIN{i}", "SELL_TIME_EXIT", 1.0, 105.0, 105.0, "TRENDING_UP", 10000.0, 0.05)
    log_trade(db, "STRONG", "BUY", 1.0, 100.0, 100.0, "TRENDING_UP", 10000.0, 0.0,
              xgb_prob=0.75, lstm_prob=0.75)
    log_trade(db, "STRONG", "SELL_STOP", 1.0, 95.0, 95.0, "TRENDING_UP", 10000.0, -0.05)
    html = le.render_loss_explanation()
    assert "Bad luck" in html
