"""Append-only registry of every configuration tried (feeds the deflated Sharpe ratio).

Why: a Sharpe ratio from the best of many configurations is inflated by search. The
honest trial count and the variance of trial results are needed to deflate it
(analytics/stat_tests.py). Entries are never edited or deleted. A count is only a
lower bound if some trials were never recorded, so backfilled entries are marked.

File: logs/trial_registry.jsonl (logs/* is gitignored).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import variance

DEFAULT_PATH = Path("logs") / "trial_registry.jsonl"


def _params_hash(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def record_trial(name: str, params: dict, metric: float | None = None,
                 source: str = "live", path: Path = DEFAULT_PATH) -> dict:
    """Append one trial. metric is the per-period Sharpe (or None if not computed)."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": name,
        "params_hash": _params_hash(params),
        "params": params,
        "metric": metric,
        "source": source,  # "live", or "backfill_from_notes" for reconstructed entries
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
    return entry


def load_trials(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def trial_summary(path: Path = DEFAULT_PATH) -> dict:
    """Count of trials and variance of recorded metrics, for the deflated Sharpe ratio."""
    rows = load_trials(path)
    metrics = [r["metric"] for r in rows if r.get("metric") is not None]
    return {
        "n_trials": len(rows),
        "n_with_metric": len(metrics),
        "var_trials": variance(metrics) if len(metrics) >= 2 else None,
        "backfilled": sum(1 for r in rows if r.get("source") == "backfill_from_notes"),
    }
