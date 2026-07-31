"""Checks COMPONENT_REGISTRY.yaml stays consistent with what's actually on
disk, using a `lifecycle` field per component so validation rules aren't
one-size-fits-all:

  implemented -- file: must exist on disk, specification: must exist
  planned     -- specification: must exist, file: may be absent
  unresolved  -- identity/existence not yet settled; file: and
                 specification: not required, but note: explaining the
                 open question IS required (an undocumented "we don't know"
                 is itself a governance gap)
  deprecated  -- file: may still exist; issues are WARN, not ERROR

Also reports registry coverage against docs/architecture/
SENTINEL_COMPONENT_CATALOG.md's component count (INFO, non-blocking) --
the registry is a partial, hand-maintained subset of the catalog today, not
an independently authoritative list of what exists. Duplicate component
keys are caught earlier, in yaml_contracts.py's duplicate-key-detecting
loader (plain YAML parsing would silently keep only the last one).
"""
import os
import re

from .code_scan_validator import FRONTEND_JS_EXTENSIONS
from .types import ValidationResult

REGISTRY_PATH = "brand/design_system/COMPONENT_REGISTRY.yaml"
CATALOG_PATH = "docs/architecture/SENTINEL_COMPONENT_CATALOG.md"
CATALOG_HEADING_RE = re.compile(r'^## Component \d+:', re.MULTILINE)

VALID_LIFECYCLES = {"implemented", "planned", "unresolved", "deprecated"}


def _file_exists(file_ref: str) -> bool:
    candidates = [file_ref] + [file_ref + ext for ext in (".py", *FRONTEND_JS_EXTENSIONS)]
    return any(os.path.exists(c) for c in candidates)


def _check_component(name, meta, result):
    lifecycle = meta.get("lifecycle")
    if lifecycle not in VALID_LIFECYCLES:
        result.add(REGISTRY_PATH, 0, "REGISTRY_LIFECYCLE_INVALID",
                    f"'{name}' has missing/invalid lifecycle "
                    f"(got {lifecycle!r}, must be one of {sorted(VALID_LIFECYCLES)})")
        return

    spec = meta.get("specification")
    file_ref = meta.get("file")
    severity = "WARN" if lifecycle == "deprecated" else "ERROR"

    if lifecycle == "unresolved":
        if not str(meta.get("note", "")).strip():
            result.add(REGISTRY_PATH, 0, "REGISTRY_UNRESOLVED_UNDOCUMENTED",
                        f"'{name}' is lifecycle: unresolved but has no note: explaining why")
        return

    if lifecycle in ("implemented", "deprecated"):
        if not file_ref:
            result.add(REGISTRY_PATH, 0, "REGISTRY_FILE_MISSING",
                        f"'{name}' is lifecycle: {lifecycle} but has no file: reference", severity)
        elif not _file_exists(file_ref):
            result.add(REGISTRY_PATH, 0, "REGISTRY_FILE_MISSING",
                        f"'{name}' file reference not found on disk: {file_ref}", severity)

    # implemented, planned, and deprecated components all need a spec
    if not spec:
        result.add(REGISTRY_PATH, 0, "REGISTRY_SPEC_MISSING",
                    f"'{name}' (lifecycle: {lifecycle}) has no specification: reference", severity)
    elif not os.path.exists(spec):
        result.add(REGISTRY_PATH, 0, "REGISTRY_SPEC_MISSING",
                    f"'{name}' specification file missing: {spec}", severity)


def _report_coverage(registered_count, result):
    if not os.path.exists(CATALOG_PATH):
        return
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog_content = f.read()
    expected_count = len(CATALOG_HEADING_RE.findall(catalog_content))
    if expected_count == 0:
        return
    result.add(
        REGISTRY_PATH, 0, "REGISTRY_COVERAGE",
        f"registry tracks {registered_count}/{expected_count} components documented in {CATALOG_PATH}",
        "INFO",
    )


def validate_component_registry(parsed_contracts):
    result = ValidationResult()
    registry = parsed_contracts.get(REGISTRY_PATH)
    if not registry:
        return result
    components = registry.get("components") or {}
    for name, meta in components.items():
        _check_component(name, meta or {}, result)
    _report_coverage(len(components), result)
    return result
