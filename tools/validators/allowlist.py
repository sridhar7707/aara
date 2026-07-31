"""Loads and applies the explicit, auditable exception list for brand
governance checks (tools/validators/allowlist.yaml).

Every entry must carry a non-blank justification -- an undocumented
exception is treated as a config error, not silently honored.
"""
import os

import yaml

ALLOWLIST_PATH = "tools/validators/allowlist.yaml"


def load_allowlist(path: str = ALLOWLIST_PATH) -> dict:
    if not os.path.exists(path):
        return {"files": set(), "terms": [], "colors": []}

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    bad_entries = []
    files = set()
    for entry in raw.get("files") or []:
        _check_justification(entry, bad_entries)
        if "path" in entry:
            files.add(entry["path"])

    terms = raw.get("terms") or []
    for entry in terms:
        _check_justification(entry, bad_entries)

    colors = raw.get("colors") or []
    for entry in colors:
        _check_justification(entry, bad_entries)

    if bad_entries:
        raise ValueError(
            f"{path} has {len(bad_entries)} allowlist entr{'y' if len(bad_entries) == 1 else 'ies'} "
            f"missing a justification: {bad_entries}"
        )

    return {"files": files, "terms": terms, "colors": colors}


def _check_justification(entry: dict, bad_entries: list) -> None:
    if not str(entry.get("justification", "")).strip():
        bad_entries.append(entry)


def is_file_exempt(filepath: str, allowlist: dict) -> bool:
    return _relpath(filepath) in allowlist["files"]


def is_term_exempt(term: str, filepath: str, allowlist: dict) -> bool:
    rel = _relpath(filepath)
    return any(e.get("term") == term and e.get("file") == rel for e in allowlist["terms"])


def is_color_exempt(hex_value: str, filepath: str, allowlist: dict) -> bool:
    rel = _relpath(filepath)
    return any(str(e.get("hex", "")).lower() == hex_value.lower() and e.get("file") == rel
               for e in allowlist["colors"])


def _relpath(filepath: str) -> str:
    return os.path.relpath(filepath).replace(os.sep, "/")
