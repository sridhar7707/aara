"""GDELT tone shadow logger (ADR-086). Logs only: feeds no trading decision.

Source: GDELT 2.0 Global Knowledge Graph (GKG) bulk files, published every 15 minutes at
data.gdeltproject.org. They are free to use, including commercially, with attribution.

Why bulk files and not the DOC API: the DOC API answered every request from this network
with HTTP 429, including a one-result query, and the bulk host answered with HTTP 200.

GKG layout used (tab-separated, 27 columns; verified on a real file, 2026-11-08):
- column 13: Organizations, semicolon-separated;
- column 15: V2Tone, comma-separated; the first value is the document's average tone.

Shadow only: nothing in this module reads or writes a trading decision. Kill criteria, set
before collecting (ML expert review, 2026-11-07): abandon if coverage (ticker-files with at
least MIN_ARTICLES matching articles) is below 80%, or if the out-of-sample rank correlation
of tone with next-day return is indistinguishable from zero. Expect about 90 trading days
before a test has power.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
ORGANIZATIONS_COL = 13
TONE_COL = 15
MIN_ARTICLES = 3            # a tone average over fewer articles is noise
COVERAGE_KILL_THRESHOLD = 0.80
LOG_PATH = Path("logs") / "gdelt_shadow.jsonl"
DOWNLOAD_GAP_SECONDS = 1.0  # polite pacing between file downloads

# Shadow universe: the screened names that GKG covers with usable volume. Aliases are the
# organization strings GKG actually writes (found by scanning 16 files, 2026-11-08). Names
# with no matches (Home Depot, Apple, UPS, Honeywell, ...) are deliberately left out: the
# source cannot score them. Financial-expert selection; ml-expert to verify before use.
SHADOW_ALIASES: dict[str, list[str]] = {
    "MSFT": ["microsoft", "microsoft corporation"],
    "DIS": ["disney"],
    "AXP": ["american express"],
    "BLK": ["blackrock", "blackrock inc"],
    "GOOGL": ["google"],
    "SBUX": ["starbucks"],
    "BA": ["boeing"],
}


def gkg_urls_from_index(index_text: str) -> list[str]:
    """Return the GKG zip URLs listed in lastupdate.txt (one line per file)."""
    urls = []
    for line in index_text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].endswith(".gkg.csv.zip"):
            urls.append(parts[2])
    return urls


def parse_gkg_rows(text: str, names: dict[str, list[str]]) -> dict[str, tuple[int, float]]:
    """For each ticker, count matching articles and sum their tone.

    names maps ticker -> a list of aliases, as GKG writes them (short forms such as
    "nvidia", "microsoft", "tesla inc"). A row matches when one of its semicolon-separated
    organizations equals an alias exactly. Substring matching is not used: it would match
    unrelated phrases. Returns {ticker: (article_count, tone_sum)}. Malformed rows are
    skipped; the file-level outcome is logged by the caller.
    """
    totals: dict[str, list[float]] = {t: [0, 0.0] for t in names}
    aliases = {t: {a.strip().lower() for a in alist if a.strip()} for t, alist in names.items()}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) <= TONE_COL:
            continue
        orgs = {o.strip().lower() for o in fields[ORGANIZATIONS_COL].split(";") if o.strip()}
        if not orgs:
            continue
        try:
            tone = float(fields[TONE_COL].split(",")[0])
        except ValueError:
            continue
        for ticker, alias_set in aliases.items():
            if alias_set & orgs:
                totals[ticker][0] += 1
                totals[ticker][1] += tone
    return {t: (int(c), s) for t, (c, s) in totals.items()}


def mean_tone(count: int, tone_sum: float) -> float | None:
    if count < MIN_ARTICLES:
        return None
    return tone_sum / count


def _fetch_zip_text(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        name = z.namelist()[0]
        return z.open(name).read().decode("utf-8", errors="replace")


class ShadowRun:
    """Process a list of GKG files for a ticker->organization-name map and log one row per
    (file, ticker). Failures are logged, never skipped. http_get(url) -> bytes, injected."""

    def __init__(self, http_get, names: dict[str, list[str]], path: Path = LOG_PATH, sleep=None):
        self._get = http_get
        self._names = names
        self._path = path
        self._sleep = sleep

    def _write(self, row: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    def run(self, urls: list[str]) -> list[dict]:
        rows = []
        for i, url in enumerate(urls):
            if i and self._sleep:
                self._sleep(DOWNLOAD_GAP_SECONDS)
            fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                blob = self._get(url)
                text = _fetch_zip_text(blob)
                totals = parse_gkg_rows(text, self._names)
                digest = hashlib.sha256(blob).hexdigest()
                for ticker, (count, tone_sum) in totals.items():
                    row = {"fetched_at_utc": fetched, "file": url, "zip_sha256": digest,
                           "ticker": ticker, "n_articles": count,
                           "mean_tone": mean_tone(count, tone_sum), "status": "ok", "error": None}
                    self._write(row)
                    rows.append(row)
            except Exception as exc:  # every failure is logged, never skipped
                row = {"fetched_at_utc": fetched, "file": url, "zip_sha256": None,
                       "ticker": None, "n_articles": None, "mean_tone": None,
                       "status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                self._write(row)
                rows.append(row)
        return rows


def coverage(rows: list[dict]) -> float:
    """Share of ticker-file rows with at least MIN_ARTICLES matching articles."""
    ticker_rows = [r for r in rows if r.get("ticker")]
    if not ticker_rows:
        return 0.0
    return sum(1 for r in ticker_rows if r.get("mean_tone") is not None) / len(ticker_rows)


def coverage_breached(rows: list[dict]) -> bool:
    return coverage(rows) < COVERAGE_KILL_THRESHOLD
