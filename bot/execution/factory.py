"""Phase 1A Sprint 5 -- get_executor() selects the execution backend via
the EXECUTION_BACKEND env var. Default (alpaca_paper) is today's unchanged
behavior -- flipping to paper_ledger, supervised, or live is opt-in only.
supervised is architecture-only (REQ-200/202): it never places a real order.
"""
from __future__ import annotations

import os

from config import ALPACA_BASE_URL
from bot.execution.base import Executor


def get_executor() -> Executor:
    backend = os.getenv("EXECUTION_BACKEND", "alpaca_paper")
    if backend == "alpaca_paper":
        from bot.execution.alpaca_client import AlpacaClient
        return AlpacaClient()
    if backend == "paper_ledger":
        from bot.execution.paper_executor import PaperExecutor
        return PaperExecutor()
    if backend == "supervised":
        # Architecture only (REQ-200/202) -- every order-placing method is a
        # structural no-op until Phase 2+ builds real approval-queue execution.
        from bot.execution.supervised import SupervisedExecutor
        return SupervisedExecutor()
    if backend == "live":
        if "paper" in ALPACA_BASE_URL:
            raise ValueError(
                "EXECUTION_BACKEND=live but ALPACA_BASE_URL still points at Alpaca's paper "
                "endpoint -- refusing to proceed with a mismatched configuration. Set "
                "ALPACA_BASE_URL to the live endpoint too, or use EXECUTION_BACKEND=alpaca_paper."
            )
        from bot.execution.alpaca_client import AlpacaClient
        return AlpacaClient()
    raise ValueError(
        f"Unknown EXECUTION_BACKEND={backend!r} "
        "(expected alpaca_paper, paper_ledger, supervised, or live)"
    )
