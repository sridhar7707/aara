#!/usr/bin/env python3
"""Run the GDELT shadow logger over the most recent GKG files (ADR-090).

Usage: python scripts/gdelt_shadow_run.py [--files N]
Default N = 96 (one day of 15-minute files). Output goes to logs/gdelt_shadow.jsonl.
Shadow only: nothing here feeds a trading decision.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics.gdelt_shadow import (  # noqa: E402
    SHADOW_ALIASES,
    ShadowRun,
    coverage,
    gkg_urls_from_index,
)

MASTER_LIST = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--files", type=int, default=96)
    args = parser.parse_args(argv)
    if args.files < 1:
        # [-0:] is the whole list, so 0 would download every GKG file ever published.
        parser.error("--files must be at least 1")
    master = _get(MASTER_LIST).decode("utf-8", errors="replace")
    urls = gkg_urls_from_index(master)[-args.files:]
    rows = ShadowRun(_get, SHADOW_ALIASES, sleep=time.sleep).run(urls)
    ok = [r for r in rows if r["status"] == "ok"]
    totals: dict[str, int] = defaultdict(int)
    for r in ok:
        totals[r["ticker"]] += r["n_articles"] or 0
    print(f"files: {len(urls)} | rows: {len(rows)} | failed: {sum(r['status'] == 'failed' for r in rows)}")
    print("articles by ticker:", dict(sorted(totals.items())))
    print(f"coverage this run (per covered name; not a verdict): {coverage(rows):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
