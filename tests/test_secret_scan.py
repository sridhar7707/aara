"""scripts/hooks/secret_scan.py: blocks staged secrets, passes clean and non-cp1252 content, fails closed."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "hooks" / "secret_scan.py"


# Git hooks export GIT_DIR / GIT_INDEX_FILE. If they leak in, these tests would stage files
# in the real repository's index. Each test must touch only its own temporary repository.
_CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=_CLEAN_ENV)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def _scan(cwd):
    env = {**_CLEAN_ENV, "GIT_CEILING_DIRECTORIES": str(Path(cwd).parent)}
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=60)


def _stage(repo, name, text):
    (repo / name).write_bytes(text.encode("utf-8"))
    _git(repo, "add", name)


def test_staged_fake_key_is_blocked(repo):
    fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"                # built at runtime so this file is not itself flagged
    _stage(repo, "config.txt", f"aws = {fake_key}\n")
    done = _scan(repo)
    assert done.returncode == 1
    assert "AWS access key" in done.stderr and "config.txt:1" in done.stderr
    assert fake_key not in done.stderr                      # the report never echoes the secret


def test_clean_file_passes(repo):
    _stage(repo, "notes.txt", "nothing secret here\n")
    assert _scan(repo).returncode == 0


def test_non_cp1252_utf8_content_does_not_crash(repo):
    # em dash is mappable in cp1252; U+0401 encodes to bytes d0 81, and 0x81 is undefined in cp1252
    _stage(repo, "text.txt", "dash — and cyrillic Ё and cjk 中\n")
    done = _scan(repo)
    assert done.returncode == 0, done.stderr
    assert "Traceback" not in done.stderr


def test_secret_next_to_non_cp1252_text_is_still_blocked(repo):
    fake_key = "gh" + "p_" + "A" * 36
    _stage(repo, "mixed.txt", f"Ё — {fake_key}\n")
    assert _scan(repo).returncode == 1


def test_env_file_is_blocked(repo):
    _stage(repo, ".env", "X=1\n")
    done = _scan(repo)
    assert done.returncode == 1 and "environment file" in done.stderr


def test_scan_error_fails_closed(tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    done = _scan(not_a_repo)
    assert done.returncode == 1
    assert "Commit blocked" in done.stderr


def test_words_containing_sk_dash_are_not_flagged(repo):
    # Regression: an unanchored "sk-" pattern blocked ordinary words such as "risk-management-...".
    _stage(repo, "policy.txt", "the risk-management-policy-approval-threshold value\n"
                               "from desk-quantitative-signals-engine import x\n")
    done = _scan(repo)
    assert done.returncode == 0, done.stderr
