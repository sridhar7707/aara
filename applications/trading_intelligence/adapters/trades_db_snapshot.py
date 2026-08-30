"""Read-only, consumer-only acquisition of the published ``trades.db``
HuggingFace *dataset* snapshot for the Trading Intelligence Space.

Authorized by ADR-055 (Accepted) Section 2: Trading Intelligence "may
obtain a read-only, ephemeral local snapshot of ``trades.db`` from the
existing published HuggingFace *dataset* repository, as a consumer only."
The runtime placement used here (fetch at Space runtime, inside
``applications/trading_intelligence/``) is the option ADR-055 Section 2
states "requires no ADR-002 exception".

ADR-055 Section 2 compliance, point by point:
  1. Source -- the existing published dataset repo identified by
     ``config.HF_DB_REPO_ID`` (today ``ksri77/ai-trading-bot-db``), file
     ``trades.db``, ``repo_type="dataset"``. No new repo is created.
  2. Mechanism -- ``huggingface_hub.hf_hub_download(...)`` for that one
     file, copied to a path INSIDE this product's own runtime area
     (``applications/trading_intelligence/.runtime/``). Never the bot's
     working ``trades.db`` path, and never ``./trades.db``.
  3. Consumer only -- this module never calls ``upload_file``,
     ``upload_folder``, ``create_commit``, ``HfApi``, or any write/delete
     operation against any HuggingFace repo, and never uses
     ``HF_REPO_ID`` as a push target. The bot
     (``bot/monitor/sync_db.py``) remains the sole producer/publisher.
  4. Fail closed -- any failure (``config`` unavailable, no repo id,
     ``huggingface_hub`` not importable, missing token, network error,
     404 / entry-not-found, malformed or empty file, filesystem error)
     yields ``None``. The five ``legacy_*_source.py`` adapters then keep
     returning ``None`` and every section stays on its existing
     honest-unavailable / illustrative fallback. A failed or absent
     snapshot is never substituted with fabricated data.
  5. Read-only open, no WAL sync -- downstream adapters open the local
     copy with ``mode=ro`` exactly as they do today. No ``-wal``/``-shm``
     handling, no ``PRAGMA journal_mode``, and no checkpoint are
     introduced here.
  6. Staleness stays visible -- this module never inspects, compares, or
     rewrites row contents or timestamps; adapters keep rendering the
     persisted ``screened_at`` / regime / ``updated_at`` values verbatim.
  7. Ephemerality -- the local copy is a cache for the running process
     only; it is overwritten on the next successful fetch and carries no
     persistence guarantee.

The download primitive is *duplicated* here, not imported from
``dashboard/data.py`` or ``scheduler/startup_job.py`` (both
ADR-002-protected) -- per ADR-055 Section 3 alternative 2 (rejected) and
this product's standing "duplicate the primitive, never import the
protected package" convention. This module imports nothing under
``bot/``, ``dashboard/``, ``scheduler/``, ``database/``, or ``ledger/``.

The ``HF_TOKEN`` gate mirrors the existing sibling precedent in
``scheduler/startup_job.py`` ("HF_TOKEN not set -- skipping db sync"):
without a token the fetch is skipped entirely, so local development and
CI stay offline and deterministic while the deployed Space (which is
provided ``HF_TOKEN``) fetches the real snapshot.
"""
import pathlib
import shutil
from typing import Optional

_RUNTIME_DIR = pathlib.Path(__file__).resolve().parent.parent / ".runtime"

# Basename matches ``.gitignore``'s ``trades*.db`` pattern, so a fetched
# snapshot can never be committed. Deliberately NOT ``trades.db``.
_SNAPSHOT_PATH = _RUNTIME_DIR / "trades_snapshot.db"

_DATASET_FILENAME = "trades.db"


def _snapshot_path() -> str:
    """The product-owned runtime path a successful fetch copies to."""
    return str(_SNAPSHOT_PATH)


def fetch_trades_db_snapshot() -> Optional[str]:
    """Download the published ``trades.db`` dataset snapshot and return the
    path to a product-owned local copy, or ``None`` on any failure.

    ADR-055 Section 2.4 -- fail closed. Every failure mode returns
    ``None``; no exception propagates to the caller, and no fabricated or
    partial file is ever handed back.
    """
    try:
        from config import HF_DB_REPO_ID, HF_TOKEN
    except Exception:
        return None

    if not HF_TOKEN or not HF_DB_REPO_ID:
        return None

    try:
        from huggingface_hub import hf_hub_download
    except Exception:
        return None

    try:
        cached = hf_hub_download(
            repo_id=HF_DB_REPO_ID,
            filename=_DATASET_FILENAME,
            repo_type="dataset",
            token=HF_TOKEN or None,
            force_download=True,
        )
    except Exception:
        return None

    try:
        _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(cached, _SNAPSHOT_PATH)
    except Exception:
        return None

    try:
        if _SNAPSHOT_PATH.stat().st_size <= 0:
            return None
    except OSError:
        return None

    return _snapshot_path()
