import os
import stat
from unittest.mock import patch
from bot.monitor.sync_db import push_db, pull_db, push_ledger_db, pull_ledger_db


def test_push_db_skips_when_no_token():
    with patch("bot.monitor.sync_db._get_cfg", return_value=("trades.db", "repo/id", "")):
        result = push_db()
    assert result is False


def test_push_db_skips_when_no_repo():
    with patch("bot.monitor.sync_db._get_cfg", return_value=("trades.db", "", "token")):
        result = push_db()
    assert result is False


def test_push_db_skips_when_db_missing(tmp_path):
    missing = str(tmp_path / "nonexistent.db")
    with patch("bot.monitor.sync_db._get_cfg", return_value=(missing, "repo/id", "token")):
        result = push_db()
    assert result is False


def test_pull_db_skips_when_no_repo():
    with patch("bot.monitor.sync_db._get_cfg", return_value=("trades.db", "", "token")):
        result = pull_db()
    assert result is False


def test_pull_db_returns_true_for_fresh_local_db(tmp_path):
    db = tmp_path / "trades.db"
    db.touch()
    with patch("bot.monitor.sync_db._get_cfg", return_value=(str(db), "repo/id", "token")):
        result = pull_db(force=False)
    assert result is True


def test_push_ledger_db_skips_when_no_token():
    with patch("bot.monitor.sync_db._get_ledger_cfg", return_value=("data/trust_ledger.db", "repo/id", "")):
        result = push_ledger_db()
    assert result is False


def test_push_ledger_db_skips_when_no_repo():
    with patch("bot.monitor.sync_db._get_ledger_cfg", return_value=("data/trust_ledger.db", "", "token")):
        result = push_ledger_db()
    assert result is False


def test_push_ledger_db_skips_when_db_missing(tmp_path):
    missing = str(tmp_path / "nonexistent.db")
    with patch("bot.monitor.sync_db._get_ledger_cfg", return_value=(missing, "repo/id", "token")):
        result = push_ledger_db()
    assert result is False


def test_pull_ledger_db_skips_when_no_repo():
    with patch("bot.monitor.sync_db._get_ledger_cfg", return_value=("data/trust_ledger.db", "", "token")):
        result = pull_ledger_db()
    assert result is False


def test_pull_ledger_db_returns_true_for_fresh_local_db(tmp_path):
    db = tmp_path / "trust_ledger.db"
    db.touch()
    with patch("bot.monitor.sync_db._get_ledger_cfg", return_value=(str(db), "repo/id", "token")):
        result = pull_ledger_db(force=False)
    assert result is True


def test_push_db_and_push_ledger_db_use_different_repo_filenames(tmp_path):
    """Both files share one HF dataset repo -- confirms they don't collide
    on path_in_repo (which would silently overwrite one with the other)."""
    trades = tmp_path / "trades.db"
    trades.touch()
    ledger = tmp_path / "trust_ledger.db"
    ledger.touch()
    uploaded = []

    class _FakeApi:
        def __init__(self, token=None):
            pass

        def repo_info(self, repo_id, repo_type):
            return object()

        def upload_file(self, path_or_fileobj, path_in_repo, repo_id, repo_type, commit_message):
            uploaded.append(path_in_repo)

    with patch("bot.monitor.sync_db._get_cfg", return_value=(str(trades), "repo/id", "token")), \
         patch("bot.monitor.sync_db._get_ledger_cfg", return_value=(str(ledger), "repo/id", "token")), \
         patch("huggingface_hub.HfApi", _FakeApi):
        push_db()
        push_ledger_db()

    assert "trades.db" in uploaded
    assert "trust_ledger.db" in uploaded


def test_pull_db_self_heals_an_already_readonly_destination(tmp_path):
    """TD-018/TD-019 regression. The first TD-018 fix (shutil.copy ->
    copyfile) only covers a destination being CREATED fresh -- it still
    raises PermissionError trying to open an EXISTING read-only
    destination for writing. That's exactly what let TD-018 recur in
    production: trade.yml's cache restore-keys (a prefix match) kept
    restoring the most recent prior run's already-read-only trades.db,
    re-poisoning itself every run regardless of copy()/copyfile(). The
    real fix chmods an existing destination writable before copying --
    this test pre-creates a read-only destination (simulating a restored
    poisoned cache entry) and asserts the sync still succeeds and leaves
    the file writable, not just that it doesn't raise."""
    dest = tmp_path / "trades.db"
    dest.write_text("STALE POISONED CONTENT")
    os.chmod(dest, stat.S_IREAD)

    fresh_source = tmp_path / "fresh_from_hf.db"
    fresh_source.write_text("fresh content")

    with patch("bot.monitor.sync_db._get_cfg", return_value=(str(dest), "repo/id", "token")), \
         patch("huggingface_hub.hf_hub_download", return_value=str(fresh_source)):
        result = pull_db(force=True)

    assert result is True
    assert dest.read_text() == "fresh content"
    assert os.access(dest, os.W_OK)
