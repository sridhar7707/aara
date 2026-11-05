"""Tests for dashboard/components/models.py's LSTM retirement display (ADR-078)."""
import json

import pytest

from dashboard.components.models import render_validation_report, _model_quality_fallback


def _write_report(tmp_path, monkeypatch, **overrides):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "models").mkdir()
    report = {
        "xgb_val_auc": 0.552,
        "lstm_val_loss": 1.0,
        "training_rows": 1000,
        "training_symbols": 10,
        "train_cutoff": "2026-10-01",
        "date_range": {"from": "2020-01-01", "to": "2026-10-01"},
        "generated_at": "2026-11-05T00:00:00",
    }
    report.update(overrides)
    (tmp_path / "models" / "validation_report.json").write_text(json.dumps(report))


def test_render_validation_report_shows_retired_not_a_number(tmp_path, monkeypatch):
    _write_report(tmp_path, monkeypatch, lstm_retired=True)
    html = render_validation_report()
    assert "Retired (ADR-077)" in html
    assert "1.0000" not in html


def test_render_validation_report_unchanged_when_not_retired(tmp_path, monkeypatch):
    """lstm_retired absent -- the numeric value cell is unchanged. The static
    help text always explains what "Retired" would mean (added by this ADR),
    so this checks the LSTM Val Loss value itself, not a bare substring of
    the whole page."""
    _write_report(tmp_path, monkeypatch, lstm_val_loss=0.62)
    html = render_validation_report()
    assert "0.6200" in html
    assert ">Retired (ADR-077)<" not in html


def test_model_quality_fallback_shows_retired_not_a_number(tmp_path, monkeypatch):
    _write_report(tmp_path, monkeypatch, lstm_retired=True)
    html = _model_quality_fallback()
    assert "Retired" in html
    assert "1.0000" not in html


def test_model_quality_fallback_unchanged_when_not_retired(tmp_path, monkeypatch):
    _write_report(tmp_path, monkeypatch, lstm_val_loss=0.62)
    html = _model_quality_fallback()
    assert "0.6200" in html
    assert "Retired" not in html
