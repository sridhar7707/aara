"""Tests for applications.trading_intelligence.adapters.trades_db_snapshot.

Covers the ADR-055 Section 2 contract for the read-only, consumer-only
`trades.db` HuggingFace dataset snapshot pull:

  - a successful `hf_hub_download` yields a product-owned `.runtime` path,
  - the copy target is that runtime path, never `./trades.db` / cwd,
  - every failure mode (generic exception, 404 / entry-not-found,
    `huggingface_hub` not importable, missing token, missing repo id,
    zero-byte download, copy error) fails closed with `None`,
  - the module performs no HF write/upload/commit of any kind,
  - the module imports nothing under bot/ dashboard/ scheduler/ database/
    ledger/.

`hf_hub_download` is faked (no network); the runtime directory is
redirected to a tmp path so the real working tree is never touched.
"""
import ast
import fnmatch
import inspect
import pathlib
import sys

import pytest

from applications.trading_intelligence.adapters import trades_db_snapshot
from applications.trading_intelligence.adapters.trades_db_snapshot import (
    fetch_trades_db_snapshot,
)

_MODULE_SRC = inspect.getsource(trades_db_snapshot)


@pytest.fixture
def runtime_dir(tmp_path, monkeypatch):
    """Redirect the module's product-owned runtime path into tmp."""
    rt = tmp_path / ".runtime"
    snap = rt / "trades_snapshot.db"
    monkeypatch.setattr(trades_db_snapshot, "_RUNTIME_DIR", rt)
    monkeypatch.setattr(trades_db_snapshot, "_SNAPSHOT_PATH", snap)
    return snap


@pytest.fixture
def hf_config(monkeypatch):
    """A configured, non-empty HF dataset identity + token."""
    monkeypatch.setattr("config.HF_DB_REPO_ID", "ksri77/ai-trading-bot-db")
    monkeypatch.setattr("config.HF_TOKEN", "test-token")


def _fake_download_factory(tmp_path, *, contents=b"SQLite format 3\x00rest-of-file"):
    """Returns a fake hf_hub_download that writes `contents` to a cache
    file and returns its path, recording the kwargs it was called with."""
    calls = []

    def _fake(**kwargs):
        calls.append(kwargs)
        cache_file = tmp_path / "hf_cache" / "trades.db"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(contents)
        return str(cache_file)

    _fake.calls = calls
    return _fake


def test_success_returns_product_runtime_snapshot_path(
    tmp_path, monkeypatch, runtime_dir, hf_config
):
    fake = _fake_download_factory(tmp_path)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake)

    result = fetch_trades_db_snapshot()

    assert result == str(runtime_dir)
    assert pathlib.Path(result).exists()
    assert pathlib.Path(result).stat().st_size > 0
    # exactly one download, for the one dataset file, as a dataset repo
    assert len(fake.calls) == 1
    assert fake.calls[0]["filename"] == "trades.db"
    assert fake.calls[0]["repo_type"] == "dataset"
    assert fake.calls[0]["repo_id"] == "ksri77/ai-trading-bot-db"


def test_copy_target_is_runtime_path_never_cwd_trades_db(
    tmp_path, monkeypatch, runtime_dir, hf_config
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download", _fake_download_factory(tmp_path)
    )

    result = fetch_trades_db_snapshot()

    resolved = pathlib.Path(result).resolve()
    # never the bot's working file / a cwd-relative trades.db
    assert resolved != (tmp_path / "trades.db").resolve()
    assert not (tmp_path / "trades.db").exists()
    assert resolved.name != "trades.db"
    # basename is still covered by .gitignore's `trades*.db`
    assert fnmatch.fnmatch(resolved.name, "trades*.db")
    assert resolved.parent.name == ".runtime"


def test_default_snapshot_path_is_inside_the_product_runtime_area():
    # No download -- just the location contract of the unpatched module.
    path = pathlib.Path(trades_db_snapshot._snapshot_path())
    assert path.name == "trades_snapshot.db"
    assert path.name != "trades.db"
    assert fnmatch.fnmatch(path.name, "trades*.db")
    parts = path.parts
    assert parts[-2] == ".runtime"
    assert parts[-3] == "trading_intelligence"
    assert parts[-4] == "applications"


def test_generic_download_exception_fails_closed(
    tmp_path, monkeypatch, runtime_dir, hf_config
):
    def _boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _boom)
    assert fetch_trades_db_snapshot() is None


def test_404_entry_not_found_fails_closed(
    tmp_path, monkeypatch, runtime_dir, hf_config
):
    def _not_found(**kwargs):
        raise Exception("404 Client Error. Entry Not Found for url: .../trades.db")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _not_found)
    assert fetch_trades_db_snapshot() is None


def test_huggingface_hub_not_importable_fails_closed(
    monkeypatch, runtime_dir, hf_config
):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    assert fetch_trades_db_snapshot() is None


def test_missing_token_skips_download_and_fails_closed(
    monkeypatch, runtime_dir
):
    monkeypatch.setattr("config.HF_DB_REPO_ID", "ksri77/ai-trading-bot-db")
    monkeypatch.setattr("config.HF_TOKEN", "")

    def _must_not_be_called(**kwargs):
        raise AssertionError("hf_hub_download must not run without a token")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _must_not_be_called)
    assert fetch_trades_db_snapshot() is None


def test_missing_repo_id_fails_closed(monkeypatch, runtime_dir):
    monkeypatch.setattr("config.HF_DB_REPO_ID", "")
    monkeypatch.setattr("config.HF_TOKEN", "test-token")

    def _must_not_be_called(**kwargs):
        raise AssertionError("hf_hub_download must not run without a repo id")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _must_not_be_called)
    assert fetch_trades_db_snapshot() is None


def test_zero_byte_download_fails_closed(
    tmp_path, monkeypatch, runtime_dir, hf_config
):
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download",
        _fake_download_factory(tmp_path, contents=b""),
    )
    assert fetch_trades_db_snapshot() is None
    assert not runtime_dir.exists() or runtime_dir.stat().st_size == 0


def test_copy_error_fails_closed(tmp_path, monkeypatch, runtime_dir, hf_config):
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download", _fake_download_factory(tmp_path)
    )

    def _copy_boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(trades_db_snapshot.shutil, "copy", _copy_boom)
    assert fetch_trades_db_snapshot() is None


def test_module_performs_no_hf_write_upload_or_commit():
    # AST identifiers only -- the module docstring legitimately *names*
    # these operations to say it never performs them, so a substring scan
    # would false-positive on its own compliance notes.
    forbidden = {
        "upload_file",
        "upload_folder",
        "create_commit",
        "create_repo",
        "delete_file",
        "delete_repo",
        "HfApi",
        "CommitOperationAdd",
        "push_to_hub",
        "hf_hub_upload",
    }
    tree = ast.parse(_MODULE_SRC)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            used.update(alias.name for alias in node.names)
    assert not (used & forbidden), f"snapshot module references {used & forbidden!r}"


def test_module_only_uses_hf_hub_download_from_huggingface_hub():
    tree = ast.parse(_MODULE_SRC)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "huggingface_hub"
        ):
            imported.extend(alias.name for alias in node.names)
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("huggingface_hub"), (
                    "import only the single download symbol, not the package"
                )
    assert imported == ["hf_hub_download"]


def test_module_imports_no_protected_packages():
    tree = ast.parse(_MODULE_SRC)
    protected = {"bot", "dashboard", "scheduler", "database", "ledger"}
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for dotted in names:
            top = dotted.split(".")[0]
            assert top not in protected, f"must not import protected package {top!r}"
