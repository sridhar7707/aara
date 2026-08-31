"""Read-only, consumer-only acquisition of the published ``trades.db``
HuggingFace *dataset* snapshot for the Trading Intelligence Space.

Authorized by ADR-055 (Accepted) Section 2: Trading Intelligence "may
obtain a read-only, ephemeral local snapshot of ``trades.db`` from the
existing published HuggingFace *dataset* repository, as a consumer only."
The runtime placement used here (fetch at Space runtime, inside
``applications/trading_intelligence/``) is the option ADR-055 Section 2
states "requires no ADR-002 exception".

Local vs. deployed
------------------
The fetch runs **only inside a HuggingFace Space**, gated on the
``SPACE_ID`` environment variable that HF injects into every running
Space container. This is the same "Space-only" discriminator
``bot/monitor/dashboard_data.py::refresh_db_from_hf`` already uses.

  - No ``SPACE_ID`` (local development, CI): ``fetch_trades_db_snapshot()``
    returns ``None`` immediately -- no ``config`` import, no
    ``huggingface_hub`` import, no network. The five ``legacy_*_source.py``
    adapters then keep their own ``"trades.db"`` default, so a developer
    machine that already has a local ``trades.db`` is unaffected and CI
    stays offline and deterministic. To exercise the Space path locally,
    set ``SPACE_ID=<owner>/<space>`` by hand.
  - ``SPACE_ID`` set (deployed Space): the snapshot is fetched as
    described below. ``HF_TOKEN`` is not required (a public dataset repo
    works with ``token=None``); a private repo without a token simply
    fails closed.

Timeout / non-blocking
----------------------
``fetch_trades_db_snapshot()`` is called once, synchronously, from
``bootstrap.build_trading_intelligence_app()`` on the Space startup path.
The actual ``hf_hub_download`` + copy run inside a ``daemon`` thread
joined with a hard 20-second timeout (matching
``bot/monitor/sync_db.py::_download``). If the transfer has not finished
by then the function returns ``None`` and app construction continues; the
abandoned daemon thread dies with the process. A late-finishing worker
writes a *complete* file via ``os.replace`` (see below), so it can never
leave a torn snapshot for the next process.

ADR-055 Section 2 compliance, point by point:
  1. Source -- the existing published dataset repo identified by
     ``config.HF_DB_REPO_ID`` (today ``ksri77/ai-trading-bot-db``), file
     ``trades.db``, ``repo_type="dataset"``. No new repo is created.
  2. Mechanism -- ``huggingface_hub.hf_hub_download(...)`` for that one
     file (no ``force_download``: normal HF Hub ETag revalidation reuses
     the cache when the bot has not re-published, and transfers only when
     it has), copied to a path INSIDE this product's own runtime area
     (``applications/trading_intelligence/.runtime/``). Never the bot's
     working ``trades.db`` path, and never ``./trades.db``.
  3. Consumer only -- this module never calls ``upload_file``,
     ``upload_folder``, ``create_commit``, ``HfApi``, or any write/delete
     operation against any HuggingFace repo, and never uses
     ``HF_REPO_ID`` as a push target. The bot
     (``bot/monitor/sync_db.py``) remains the sole producer/publisher.
  4. Fail closed -- any failure (not in a Space, ``config`` unavailable,
     no repo id, ``huggingface_hub`` not importable, network error,
     404 / entry-not-found, timeout, malformed or empty file, filesystem
     error) yields ``None``. The five ``legacy_*_source.py`` adapters
     then keep returning ``None`` and every section stays on its existing
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
     only; it is remade from the hub cache on the next process start and
     carries no persistence guarantee.

The download primitive is *duplicated* here, not imported from
``dashboard/data.py`` or ``scheduler/startup_job.py`` (both
ADR-002-protected) -- per ADR-055 Section 3 alternative 2 (rejected) and
this product's standing "duplicate the primitive, never import the
protected package" convention. This module imports nothing under
``bot/``, ``dashboard/``, ``scheduler/``, ``database/``, or ``ledger/``.
"""
import os
import pathlib
import shutil
import threading
from typing import Optional

_RUNTIME_DIR = pathlib.Path(__file__).resolve().parent.parent / ".runtime"

# Basename matches ``.gitignore``'s ``trades*.db`` pattern, and the whole
# ``.runtime/`` directory is gitignored, so a fetched snapshot (and its
# per-process temp file) can never be committed. Deliberately NOT
# ``trades.db``.
_SNAPSHOT_PATH = _RUNTIME_DIR / "trades_snapshot.db"

_DATASET_FILENAME = "trades.db"

# Hard cap on how long the Space startup path may wait for the transfer,
# matching ``bot/monitor/sync_db.py::_download``'s ``t.join(timeout=20)``.
_FETCH_TIMEOUT_SECONDS = 20


def _snapshot_path() -> str:
    """The product-owned runtime path a successful fetch copies to."""
    return str(_SNAPSHOT_PATH)


def fetch_trades_db_snapshot() -> Optional[str]:
    """Fetch the published ``trades.db`` dataset snapshot (Space only) and
    return the path to a product-owned local copy, or ``None`` on any
    failure or when not running inside a HuggingFace Space.

    ADR-055 Section 2.4 -- fail closed. Every failure mode returns
    ``None``; no exception propagates to the caller, the call never blocks
    longer than ``_FETCH_TIMEOUT_SECONDS``, and no fabricated or partial
    file is ever handed back.
    """
    if not os.environ.get("SPACE_ID"):
        return None

    try:
        from config import HF_DB_REPO_ID, HF_TOKEN
    except Exception:
        return None

    if not HF_DB_REPO_ID:
        return None

    try:
        from huggingface_hub import hf_hub_download
    except Exception:
        return None

    result: list[Optional[str]] = [None]

    def _download() -> None:
        try:
            cached = hf_hub_download(
                repo_id=HF_DB_REPO_ID,
                filename=_DATASET_FILENAME,
                repo_type="dataset",
                token=HF_TOKEN or None,
            )
        except Exception:
            return

        try:
            _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _RUNTIME_DIR / f".trades_snapshot.{os.getpid()}.part"
            shutil.copy(cached, tmp)
            if tmp.stat().st_size <= 0:
                tmp.unlink(missing_ok=True)
                return
            os.replace(tmp, _SNAPSHOT_PATH)
        except Exception:
            return

        result[0] = _snapshot_path()

    worker = threading.Thread(target=_download, daemon=True)
    worker.start()
    worker.join(timeout=_FETCH_TIMEOUT_SECONDS)

    if worker.is_alive():
        # Transfer did not finish in time -- fail closed. The daemon
        # thread is abandoned (it dies with the process); if it completes
        # later it will os.replace() a whole file for the next start.
        return None

    return result[0]
