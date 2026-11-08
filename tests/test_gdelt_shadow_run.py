"""Tests for scripts/gdelt_shadow_run.py (network stubbed)."""
import importlib.util
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gdelt_shadow_run", ROOT / "scripts" / "gdelt_shadow_run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.gkg.csv", text)
    return buf.getvalue()


def test_runner_uses_only_the_requested_number_of_files(monkeypatch, tmp_path, capsys):
    master = "\n".join(f"1 h http://x/{i:03d}.gkg.csv.zip" for i in range(10))
    fetched = []

    def fake_get(url):
        fetched.append(url)
        if url == runner.MASTER_LIST:
            return master.encode()
        return _zip("")  # empty GKG file: zero matches, no failures

    monkeypatch.setattr(runner, "_get", fake_get)
    monkeypatch.setattr(runner, "ShadowRun", lambda get, names, sleep: _quiet(get, names, tmp_path))
    code = runner.main(["--files", "3"])
    out = capsys.readouterr().out
    assert code == 0
    gkg_fetched = [u for u in fetched if u.endswith(".gkg.csv.zip")]
    assert len(gkg_fetched) == 3
    assert "files: 3" in out


def _quiet(get, names, tmp_path):
    """Build a ShadowRun that writes to a temp log instead of logs/."""
    from analytics.gdelt_shadow import ShadowRun

    class _Run(ShadowRun):
        def __init__(self, g, n, sleep=None):
            super().__init__(g, n, path=tmp_path / "shadow.jsonl", sleep=None)

    return _Run(get, names)
