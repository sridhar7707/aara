"""Snapshot-specific wiring helpers for ``bootstrap.py``'s Trading
Intelligence composition root.

Extracted so the ADR-055 ``trades.db``-snapshot plumbing does not grow
``bootstrap.py`` further. These are behavior-identical to the inline
versions they replaced; the fetch itself lives in
``adapters/trades_db_snapshot.py``.
"""
from functools import partial
from typing import Callable, Dict, Optional, TypeVar

_ScreenT = TypeVar("_ScreenT")


def legacy_source_kwargs(db_path: Optional[str]) -> Dict[str, str]:
    """Constructor kwargs for the five ``legacy_*_source.py`` adapters.

    A real ``db_path`` string (the runtime ``trades.db`` snapshot fetched
    per ADR-055) makes the adapters read that product-owned copy; ``None``
    (no snapshot -- local dev, CI, or a Space where the fetch failed or is
    not applicable) yields ``{}`` so the adapters keep their own
    ``"trades.db"`` default, leaving a developer machine that already has
    ``trades.db`` unaffected and the deployed Space on its existing
    honest-unavailable states.
    """
    return {"db_path": db_path} if db_path else {}


def snapshot_bound_provider(
    screen_builder: Callable[[Optional[str]], _ScreenT], db_path: Optional[str]
) -> Callable[[], _ScreenT]:
    """Bind ``screen_builder`` to ``db_path`` for a screen's
    ``screen_provider`` slot. The provider is called with no args on every
    ``demo.load()`` / Refresh and re-reads the already-fetched snapshot
    file, so the snapshot is pulled once per process, not once per
    refresh.
    """
    return partial(screen_builder, db_path)
