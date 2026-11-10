"""Tests for analytics/gdelt_shadow.py (GKG bulk files; no network: fetch is injected)."""
import io
import json
import zipfile

import pytest

from analytics.gdelt_shadow import (
    MIN_ARTICLES,
    ShadowRun,
    coverage,
    coverage_breached,
    gkg_urls_from_index,
    mean_tone,
    parse_gkg_rows,
)


def _row(orgs: str, tone: float) -> str:
    fields = [""] * 27
    fields[0] = "20261108000000-0"
    fields[13] = orgs
    fields[15] = f"{tone},1.0,2.0,3.0,4.0,5.0,100"
    return "\t".join(fields)


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("20261108000000.gkg.csv", text)
    return buf.getvalue()


NAMES = {"AAPL": ["apple inc", "apple"], "TSLA": ["tesla", "tesla inc"]}


def test_index_yields_only_gkg_urls():
    idx = ("1 a http://x/20261108.export.CSV.zip\n"
           "2 b http://x/20261108.gkg.csv.zip\n"
           "3 c http://x/20261108.mentions.CSV.zip\n")
    assert gkg_urls_from_index(idx) == ["http://x/20261108.gkg.csv.zip"]


def test_parse_counts_matching_orgs_and_sums_tone():
    text = "\n".join([_row("apple inc;foo", -2.0), _row("tesla", 4.0), _row("tesla;apple inc", 1.0)])
    totals = parse_gkg_rows(text, NAMES)
    assert totals["AAPL"] == (2, -1.0)
    assert totals["TSLA"] == (2, 5.0)


def test_mean_tone_needs_minimum_articles():
    assert mean_tone(MIN_ARTICLES - 1, 10.0) is None
    assert mean_tone(MIN_ARTICLES, 9.0) == pytest.approx(3.0)


def test_short_or_bad_rows_are_ignored():
    text = "bad row\n" + _row("apple inc", "not-a-number") + "\n" + _row("apple inc", 2.0)
    assert parse_gkg_rows(text, NAMES)["AAPL"] == (1, 2.0)


def test_run_logs_one_row_per_ticker_per_file(tmp_path):
    path = tmp_path / "s.jsonl"
    text = "\n".join([_row("apple inc", 1.0)] * 3 + [_row("tesla", -2.0)])
    blob = _zip(text)
    run = ShadowRun(lambda url: blob, NAMES, path=path, sleep=lambda s: None)
    rows = run.run(["http://x/a.gkg.csv.zip"])
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["AAPL"]["n_articles"] == 3 and by_ticker["AAPL"]["mean_tone"] == pytest.approx(1.0)
    assert by_ticker["TSLA"]["mean_tone"] is None  # one article: below the minimum
    logged = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(logged) == 2 and all(r["zip_sha256"] for r in logged)


def test_failures_are_logged_not_skipped(tmp_path):
    path = tmp_path / "s.jsonl"

    def boom(url):
        raise OSError("connection refused")

    rows = ShadowRun(boom, NAMES, path=path, sleep=lambda s: None).run(["http://x/a.gkg.csv.zip"])
    assert rows[0]["status"] == "failed" and "OSError" in rows[0]["error"]
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "failed"


def test_coverage_and_kill_threshold():
    rows = ([{"ticker": "A", "mean_tone": 1.0}] * 7 + [{"ticker": "A", "mean_tone": None}] * 3)
    assert coverage(rows) == pytest.approx(0.7)
    assert coverage_breached(rows)
    assert not coverage_breached([{"ticker": "A", "mean_tone": 1.0}] * 9
                                 + [{"ticker": "A", "mean_tone": None}])
