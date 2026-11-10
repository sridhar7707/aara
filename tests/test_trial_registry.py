"""Tests for analytics/trial_registry.py."""
import json

from analytics.trial_registry import load_trials, record_trial, trial_summary


def test_record_appends_and_counts(tmp_path):
    path = tmp_path / "trials.jsonl"
    record_trial("xgb_threshold", {"threshold": 0.60}, metric=0.4, path=path)
    record_trial("xgb_threshold", {"threshold": 0.52}, metric=0.6, path=path)
    rows = load_trials(path)
    assert len(rows) == 2
    assert rows[0]["params"] == {"threshold": 0.60}


def test_variance_and_backfill_count(tmp_path):
    path = tmp_path / "trials.jsonl"
    record_trial("a", {"k": 1}, metric=1.0, path=path)
    record_trial("b", {"k": 2}, metric=3.0, path=path)
    record_trial("c", {"k": 3}, metric=None, source="backfill_from_notes", path=path)
    s = trial_summary(path)
    assert s["n_trials"] == 3
    assert s["n_with_metric"] == 2
    assert s["var_trials"] == 2.0  # sample variance of 1.0 and 3.0
    assert s["backfilled"] == 1


def test_same_params_same_hash(tmp_path):
    path = tmp_path / "trials.jsonl"
    a = record_trial("x", {"p": 1, "q": 2}, path=path)
    b = record_trial("x", {"q": 2, "p": 1}, path=path)
    assert a["params_hash"] == b["params_hash"]


def test_missing_file_is_empty(tmp_path):
    s = trial_summary(tmp_path / "none.jsonl")
    assert s == {"n_trials": 0, "n_with_metric": 0, "var_trials": None, "backfilled": 0}


def test_file_is_valid_jsonl(tmp_path):
    path = tmp_path / "trials.jsonl"
    record_trial("x", {"p": 1}, path=path)
    for line in path.read_text(encoding="utf-8").splitlines():
        json.loads(line)
