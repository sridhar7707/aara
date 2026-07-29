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
    assert uploaded[0] != uploaded[1]
