"""Position-fetch guard used before startup reconcile — extracted from bot/main.py."""
from __future__ import annotations

import sqlite3
import time

from loguru import logger

_RECONCILE_REVERIFY_ATTEMPTS = 2
_RECONCILE_REVERIFY_DELAY_SECS = 2.0


def _fetch_positions_for_reconcile(client, con: sqlite3.Connection) -> dict:
    """Fetch live positions; re-verify before trusting an empty result if the DB
    expects open ones. A single empty get_all_positions() read has previously
    been a transient Alpaca API glitch, not a real "everything sold externally"
    event — _reconcile_positions has no way to tell the difference on its own
    and would log a SELL_RECONCILE (with a stale/wrong portfolio_value) for
    every DB position, corrupting portfolio history.
    """
    positions = client.get_positions()
    if positions:
        return positions
    expected = {r[0] for r in con.execute("SELECT symbol FROM position_state").fetchall()}
    if not expected:
        return positions
    for attempt in range(_RECONCILE_REVERIFY_ATTEMPTS):
        logger.warning(
            f"get_positions() empty but DB expects {sorted(expected)} "
            f"(re-verify {attempt + 1}/{_RECONCILE_REVERIFY_ATTEMPTS}) — possible transient API glitch"
        )
        time.sleep(_RECONCILE_REVERIFY_DELAY_SECS)
        positions = client.get_positions()
        if positions:
            logger.info(f"Re-verify recovered positions {list(positions.keys())} — was transient")
            return positions
    logger.error(
        f"get_positions() confirmed empty after {_RECONCILE_REVERIFY_ATTEMPTS} re-verifications "
        f"— proceeding to reconcile {sorted(expected)} as genuinely closed"
    )
    return positions
