"""Tests for scripts/load_model_hf.py — HuggingFace pull list."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _patch_hf_env(monkeypatch):
    """Provide minimal env so pull() does not raise on startup."""
    import scripts.load_model_hf as mod
    monkeypatch.setattr(mod, "HF_TOKEN", "test-token")
    monkeypatch.setattr(mod, "HF_REPO_ID", "test/repo")


def test_pull_requests_xgb_predictor_meta_json(monkeypatch, tmp_path):
    import scripts.load_model_hf as mod

    requested_filenames = []

    def _fake_download(repo_id, filename, token):
        requested_filenames.append(filename)
        cached = tmp_path / filename
        cached.write_text("{}")
        return str(cached)

    with patch("scripts.load_model_hf.hf_hub_download", side_effect=_fake_download), \
         patch("scripts.load_model_hf.shutil.copy"):
        mod.pull()

    assert "xgb_predictor.meta.json" in requested_filenames, (
        "pull() must request xgb_predictor.meta.json from HuggingFace"
    )
