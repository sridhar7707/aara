"""Read-only, consumer-only acquisition of the published ``trust_ledger.db``
HuggingFace *dataset* snapshot for the Trading Intelligence Space.

Authorized by ADR-064 (Accepted) Section 2: Trading Intelligence "may
consume the already-published ``trust_ledger.db`` dataset artifact as a
read-only, ephemeral local snapshot, for the sole purpose of a Decision
Ledger Inspection surface". ADR-064 grants a narrow exception to ADR-055
Section 5.6 for this exact scope only; ADR-055 itself is unchanged and
every other clause of it remains in force.

This is a **duplicated** product-owned primitive (ADR-064 Section 2.1):
the ADR-055 read-only HuggingFace *dataset* snapshot pattern -- SPACE_ID
gate, hard-timeout daemon thread, atomic ``os.replace`` finalize,
fail-closed ``ReadResult`` / ``IntegrationHealth`` -- reimplemented here
for the published ``trust_ledger.db`` filename and a distinct
product-owned local path. It is duplicated, never imported, from any
sibling snapshot primitive or any ``bot/`` / ``dashboard/`` /
``scheduler/`` module. This module imports nothing under ``bot/``,
top-level ``ledger/``, ``scheduler/``, ``dashboard/``, ``database/``, or
``sentinel_engine/``.

Local vs. deployed
------------------
The fetch runs **only inside a HuggingFace Space**, gated on ``SPACE_ID``
(HF injects it into every running Space container). With no ``SPACE_ID``
the call returns a NOT_CONFIGURED ``ReadResult`` immediately -- no
``config`` import, no ``huggingface_hub`` import, no network. This is the
state local development and CI see.

Runtime placement only
----------------------
ADR-064 Section 2.1 item 6: this authorization covers the Space-runtime
fetch only. Staging a ``trust_ledger.db`` pull into any
``.github/workflows/*.yml`` at deploy time is explicitly out of scope and
would require separate governance review.

Fail closed (ADR-064 Section 10)
--------------------------------
Every failure mode -- missing artifact, download failure, timeout,
unavailable HF runtime identity, empty / torn file, copy error -- yields a
non-HEALTHY ``ReadResult`` (``value=None``) with a classified
``IntegrationHealth``. No exception propagates, the call never blocks
longer than ``_FETCH_TIMEOUT_SECONDS``, and no partial file is ever handed
back (a per-process temp file is finalised with an atomic ``os.replace``).
There is **no** fallback to the bot's working ledger file, to a stale
copy, or to any other database.

Consumer only (ADR-064 Section 2.1 item 3)
------------------------------------------
This module never calls ``upload_file``, ``upload_folder``,
``create_commit``, ``HfApi``, or any mutating operation against any
HuggingFace repo. The bot's own sync mechanism remains the sole
producer/publisher of ``trust_ledger.db``; that mechanism is not modified
and not imported here.

Source configuration is the identity already authorized by ADR-055:
``config.HF_DB_REPO_ID`` (today ``ksri77/ai-trading-bot-db``),
``repo_type="dataset"``. The bot publishes ``trust_ledger.db`` into that
same dataset repo; this fetches that one file.
"""
import os
import pathlib
import shutil
import threading
from typing import List, Optional

from applications.platform.integrations import (
    IntegrationHealth,
    ReadResult,
    classify_exception,
)

_PROVIDER = "hf_trust_ledger_db_snapshot"

_RUNTIME_DIR = pathlib.Path(__file__).resolve().parent.parent / ".runtime"

# Basename lives under the gitignored ``.runtime/`` directory, so a fetched
# snapshot (and its per-process temp file) can never be committed.
# Deliberately distinct from the published filename, and never the bot's
# own working ledger file under ``data/``.
_SNAPSHOT_PATH = _RUNTIME_DIR / "trust_ledger_snapshot.db"

_DATASET_FILENAME = "trust_ledger.db"

# Hard cap on how long the Space startup path may wait for the transfer
# (ADR-064 Section 3); the ADR-055 snapshot primitive uses the same 20s.
_FETCH_TIMEOUT_SECONDS = 20


def _snapshot_path() -> str:
    """The product-owned runtime path a successful fetch copies to."""
    return str(_SNAPSHOT_PATH)


def fetch_trust_ledger_db_snapshot() -> "ReadResult[str]":
    """Fetch the published ``trust_ledger.db`` dataset snapshot (Space only)
    and return a ``ReadResult`` over the path to a product-owned local copy.

    ADR-064 Section 10 -- fail closed. Every failure mode yields a
    non-HEALTHY ``ReadResult`` (``value=None``); no exception propagates to
    the caller, the call never blocks longer than
    ``_FETCH_TIMEOUT_SECONDS``, and no fabricated or partial file is ever
    handed back. There is no fallback to any other database.
    """
    if not os.environ.get("SPACE_ID"):
        return ReadResult.failed(
            IntegrationHealth.not_configured(
                _PROVIDER, detail="not running inside a HuggingFace Space"
            )
        )

    try:
        from config import HF_DB_REPO_ID, HF_TOKEN
    except Exception:
        return ReadResult.failed(
            IntegrationHealth.not_configured(
                _PROVIDER, detail="config module is not importable"
            )
        )

    if not HF_DB_REPO_ID:
        return ReadResult.failed(
            IntegrationHealth.not_configured(_PROVIDER, detail="HF_DB_REPO_ID is not set")
        )

    try:
        from huggingface_hub import hf_hub_download
    except Exception:
        return ReadResult.failed(
            IntegrationHealth.not_configured(
                _PROVIDER, detail="huggingface_hub is not importable"
            )
        )

    result: List[Optional[str]] = [None]
    download_error: List[Optional[BaseException]] = [None]
    finalize_error: List[Optional[BaseException]] = [None]
    torn: List[bool] = [False]

    def _download() -> None:
        try:
            cached = hf_hub_download(
                repo_id=HF_DB_REPO_ID,
                filename=_DATASET_FILENAME,
                repo_type="dataset",
                token=HF_TOKEN or None,
            )
        except Exception as exc:
            download_error[0] = exc
            return

        try:
            _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _RUNTIME_DIR / f".trust_ledger_snapshot.{os.getpid()}.part"
            shutil.copy(cached, tmp)
            if tmp.stat().st_size <= 0:
                tmp.unlink(missing_ok=True)
                torn[0] = True
                return
            os.replace(tmp, _SNAPSHOT_PATH)
        except Exception as exc:
            finalize_error[0] = exc
            return

        result[0] = _snapshot_path()

    worker = threading.Thread(target=_download, daemon=True)
    worker.start()
    worker.join(timeout=_FETCH_TIMEOUT_SECONDS)

    if worker.is_alive():
        # Transfer did not finish in time -- fail closed. The daemon thread
        # is abandoned (it dies with the process); if it completes later it
        # will os.replace() a whole file for the next start.
        return ReadResult.failed(
            IntegrationHealth.unavailable(
                _PROVIDER, detail="snapshot fetch did not finish within the timeout"
            )
        )

    if download_error[0] is not None:
        return ReadResult.failed(classify_exception(_PROVIDER, download_error[0]))

    if torn[0]:
        return ReadResult.failed(
            IntegrationHealth.api_error(
                _PROVIDER, detail="downloaded snapshot was empty"
            )
        )

    if finalize_error[0] is not None:
        return ReadResult.failed(
            IntegrationHealth.api_error(
                _PROVIDER, detail=type(finalize_error[0]).__name__
            )
        )

    if result[0] is None:
        return ReadResult.failed(
            IntegrationHealth.api_error(
                _PROVIDER, detail="snapshot fetch produced no local file"
            )
        )

    return ReadResult.healthy(result[0], _PROVIDER)
