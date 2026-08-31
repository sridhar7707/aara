"""Tests for applications.trading_intelligence.adapters.trades_db_snapshot.

Covers the ADR-055 Section 2 contract for the read-only, consumer-only
`trades.db` HuggingFace dataset snapshot pull, plus the ADR-061 Category A
health contract:

  - the fetch runs only inside a HuggingFace Space (gated on SPACE_ID);
    with no SPACE_ID it returns a NOT_CONFIGURED ReadResult with no
    config/hub import, no network;
  - inside a Space it attempts the download even with an empty HF_TOKEN
    (public dataset repo), passing token=None;
  - HF_DB_REPO_ID is still a required configuration guard (NOT_CONFIGURED);
  - the download + copy run in a daemon thread joined with a hard
    20-second timeout; on timeout the call returns an UNAVAILABLE
    ReadResult and does not block, and a late-finishing worker can never
    leave a partial snapshot (atomic os.replace of a per-process temp
    file);
  - the copy target is the product-owned `.runtime` path, never
    `./trades.db` / cwd;
  - every failure mode fails closed with value=None and a classified
    IntegrationHealth;
  - the module performs no HF write/upload/commit and imports nothing
    under bot/ dashboard/ scheduler/ database/ ledger/.

`hf_hub_download` is always faked -- no network. Timing tests drive a
worker that blocks on a test-controlled event, with the join timeout
monkeypatched down, so they stay fast and deterministic.
"""
import ast
import fnmatch
import inspect
import pathlib
import sys
import threading
import time

import pytest

from applications.platform.integrations import IntegrationStatus, ReadResult
from applications.trading_intelligence.adapters import trades_db_snapshot
from applications.trading_intelligence.adapters.trades_db_snapshot import (
    fetch_trades_db_snapshot,
)

_MODULE_SRC = inspect.getsource(trades_db_snapshot)

_SQLITE_BYTES = b"SQLite format 3\x00" + b"rest-of-file-padding"


@pytest.fixture
def runtime_dir(tmp_path, monkeypatch):
    """Redirect the module's product-owned runtime area into tmp."""
    rt = tmp_path / ".runtime"
    snap = rt / "trades_snapshot.db"
    monkeypatch.setattr(trades_db_snapshot, "_RUNTIME_DIR", rt)
    monkeypatch.setattr(trades_db_snapshot, "_SNAPSHOT_PATH", snap)
    return snap


@pytest.fixture
def in_space(monkeypatch):
    monkeypatch.setenv("SPACE_ID", "ksri77/aara-trading-intelligence")


@pytest.fixture
def repo_configured(monkeypatch):
    monkeypatch.setattr("config.HF_DB_REPO_ID", "ksri77/ai-trading-bot-db")
    monkeypatch.setattr("config.HF_TOKEN", "test-token")


def _fake_download_factory(tmp_path, *, contents=_SQLITE_BYTES):
    calls = []

    def _fake(**kwargs):
        calls.append(kwargs)
        cache_file = tmp_path / "hf_cache" / "trades.db"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(contents)
        return str(cache_file)

    _fake.calls = calls
    return _fake


def _forbidden_download(**kwargs):
    raise AssertionError("hf_hub_download must not be called in this path")


def _assert_failed(result, status):
    assert isinstance(result, ReadResult)
    assert result.value is None
    assert result.health.status is status


# --- SPACE_ID gate --------------------------------------------------------

def test_not_in_space_is_not_configured_without_download(monkeypatch, runtime_dir):
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", _forbidden_download)
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.NOT_CONFIGURED)


def test_in_space_success_is_healthy_with_the_runtime_path(
    tmp_path, monkeypatch, runtime_dir, in_space, repo_configured
):
    fake = _fake_download_factory(tmp_path)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake)

    result = fetch_trades_db_snapshot()

    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == str(runtime_dir)
    assert pathlib.Path(result.value).exists()
    assert pathlib.Path(result.value).stat().st_size > 0
    assert len(fake.calls) == 1
    assert fake.calls[0]["filename"] == "trades.db"
    assert fake.calls[0]["repo_type"] == "dataset"
    assert fake.calls[0]["repo_id"] == "ksri77/ai-trading-bot-db"
    assert "force_download" not in fake.calls[0]


def test_in_space_empty_token_still_attempts_public_repo(
    tmp_path, monkeypatch, runtime_dir, in_space
):
    monkeypatch.setattr("config.HF_DB_REPO_ID", "ksri77/ai-trading-bot-db")
    monkeypatch.setattr("config.HF_TOKEN", "")
    fake = _fake_download_factory(tmp_path)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake)

    result = fetch_trades_db_snapshot()

    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == str(runtime_dir)
    assert len(fake.calls) == 1
    assert fake.calls[0]["token"] is None  # empty HF_TOKEN -> token=None


def test_missing_repo_id_is_not_configured(monkeypatch, runtime_dir, in_space):
    monkeypatch.setattr("config.HF_DB_REPO_ID", "")
    monkeypatch.setattr("config.HF_TOKEN", "test-token")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", _forbidden_download)
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.NOT_CONFIGURED)


# --- copy target / path contract ---------------------------------------

def test_copy_target_is_runtime_path_never_cwd_trades_db(
    tmp_path, monkeypatch, runtime_dir, in_space, repo_configured
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download", _fake_download_factory(tmp_path)
    )

    resolved = pathlib.Path(fetch_trades_db_snapshot().value).resolve()

    assert resolved != (tmp_path / "trades.db").resolve()
    assert not (tmp_path / "trades.db").exists()
    assert resolved.name != "trades.db"
    assert fnmatch.fnmatch(resolved.name, "trades*.db")
    assert resolved.parent.name == ".runtime"


def test_default_snapshot_path_is_inside_the_product_runtime_area():
    path = pathlib.Path(trades_db_snapshot._snapshot_path())
    assert path.name == "trades_snapshot.db"
    assert path.name != "trades.db"
    assert fnmatch.fnmatch(path.name, "trades*.db")
    parts = path.parts
    assert parts[-2] == ".runtime"
    assert parts[-3] == "trading_intelligence"
    assert parts[-4] == "applications"


# --- fail-closed paths -------------------------------------------------

def test_generic_download_exception_fails_closed(
    monkeypatch, runtime_dir, in_space, repo_configured
):
    def _boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _boom)

    result = fetch_trades_db_snapshot()
    assert result.value is None
    assert result.health.status is not IntegrationStatus.HEALTHY


def test_404_entry_not_found_is_api_error(
    monkeypatch, runtime_dir, in_space, repo_configured
):
    def _not_found(**kwargs):
        raise Exception("404 Client Error. Entry Not Found for url: .../trades.db")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _not_found)
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.API_ERROR)


def test_auth_rejected_download_is_auth_failed(
    monkeypatch, runtime_dir, in_space, repo_configured
):
    class _Resp:
        status_code = 401

    class _AuthError(Exception):
        response = _Resp()

    def _rejected(**kwargs):
        raise _AuthError("401 Unauthorized for private dataset")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _rejected)
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.AUTH_FAILED)


def test_huggingface_hub_not_importable_is_not_configured(
    monkeypatch, runtime_dir, in_space, repo_configured
):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.NOT_CONFIGURED)


def test_zero_byte_download_is_api_error(
    tmp_path, monkeypatch, runtime_dir, in_space, repo_configured
):
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download",
        _fake_download_factory(tmp_path, contents=b""),
    )
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.API_ERROR)
    assert not runtime_dir.exists()  # no snapshot written


def test_copy_error_is_api_error(
    tmp_path, monkeypatch, runtime_dir, in_space, repo_configured
):
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download", _fake_download_factory(tmp_path)
    )

    def _copy_boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(trades_db_snapshot.shutil, "copy", _copy_boom)
    _assert_failed(fetch_trades_db_snapshot(), IntegrationStatus.API_ERROR)


# --- timeout / abandoned worker --------------------------------------

def test_download_timeout_is_unavailable_and_does_not_block(
    tmp_path, monkeypatch, runtime_dir, in_space, repo_configured
):
    monkeypatch.setattr(trades_db_snapshot, "_FETCH_TIMEOUT_SECONDS", 0.3)
    release = threading.Event()

    def _slow(**kwargs):
        release.wait(timeout=5)
        cache_file = tmp_path / "hf_cache" / "trades.db"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(_SQLITE_BYTES)
        return str(cache_file)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _slow)

    started = time.monotonic()
    result = fetch_trades_db_snapshot()
    elapsed = time.monotonic() - started
    release.set()

    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE
    assert elapsed < 2.0  # returned on the 0.3s join, not the 5s worker


def test_abandoned_slow_worker_cannot_leave_a_partial_snapshot(
    tmp_path, monkeypatch, runtime_dir, in_space, repo_configured
):
    monkeypatch.setattr(trades_db_snapshot, "_FETCH_TIMEOUT_SECONDS", 0.3)
    release = threading.Event()
    source = tmp_path / "hf_cache" / "trades.db"

    def _slow(**kwargs):
        release.wait(timeout=5)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_SQLITE_BYTES)
        return str(source)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _slow)

    result = fetch_trades_db_snapshot()
    assert result.value is None
    # nothing published, and no visible partial, while the worker is still blocked
    assert not runtime_dir.exists()
    if runtime_dir.parent.exists():
        assert list(runtime_dir.parent.iterdir()) == []

    # let the abandoned worker finish; it must publish atomically
    release.set()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not runtime_dir.exists():
        time.sleep(0.02)
    assert runtime_dir.exists()
    assert runtime_dir.read_bytes() == _SQLITE_BYTES  # whole file, not torn
    leftovers = [p.name for p in runtime_dir.parent.glob(".trades_snapshot.*.part")]
    assert leftovers == []


# --- static safety guarantees --------------------------------------

def test_module_performs_no_hf_write_upload_or_commit():
    forbidden = {
        "upload_file", "upload_folder", "create_commit", "create_repo",
        "delete_file", "delete_repo", "HfApi", "CommitOperationAdd",
        "push_to_hub", "hf_hub_upload",
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
