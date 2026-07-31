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
SENTINEL_COMPONENT_CATALOG.md's documented component names (INFO,
non-blocking), matched by identity (canonical_name or registry key), not
by lifecycle -- a registered component can validly describe something the
catalog has never documented (e.g. GovernancePanel), which is a different
situation from tracking a component the catalog does document. Duplicate
component keys are caught earlier, in yaml_contracts.py's
duplicate-key-detecting loader (plain YAML parsing would silently keep
only the last one).
"""
import os
import re

from .code_scan_validator import FRONTEND_JS_EXTENSIONS
from .types import ValidationResult

REGISTRY_PATH = "brand/design_system/COMPONENT_REGISTRY.yaml"
CATALOG_PATH = "docs/architecture/SENTINEL_COMPONENT_CATALOG.md"
CATALOG_NAME_RE = re.compile(r'^\*\*Name:\*\*\s*(\S+)', re.MULTILINE)

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


def _report_coverage(components, result):
    if not os.path.exists(CATALOG_PATH):
        # docs/architecture/ is gitignored (repo policy, not an accident) --
        # this means CATALOG_PATH is only ever present in a local checkout,
        # never in CI. Silently returning here would make CI's "PASSED
        # cleanly" imply coverage was checked when it wasn't; say so
        # instead, at WARN (visible, but non-blocking even after Stage 3
        # Phase B -- this is an environment limitation, not a registry
        # defect).
        result.add(REGISTRY_PATH, 0, "REGISTRY_COVERAGE_UNAVAILABLE",
                    f"{CATALOG_PATH} not present in this checkout (docs/architecture/ is "
                    f"gitignored) -- registry-vs-catalog coverage cannot be verified here; "
                    f"run locally to check it", "WARN")
        return
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog_content = f.read()
    catalog_names = set(CATALOG_NAME_RE.findall(catalog_content))
    if not catalog_names:
        return

    # Match by identity (canonical_name if set, else the registry key),
    # not by lifecycle -- a component can be legitimately planned/
    # implemented/deprecated while still describing something the catalog
    # has never documented (e.g. GovernancePanel), and that's not the same
    # situation as tracking a component the catalog *does* document.
    tracked_names = {(m or {}).get("canonical_name", key) for key, m in components.items()}
    covered = tracked_names & catalog_names
    beyond_catalog = tracked_names - catalog_names

    message = f"registry tracks {len(covered)}/{len(catalog_names)} catalog components in {CATALOG_PATH}"
    if beyond_catalog:
        plural = "y" if len(beyond_catalog) == 1 else "ies"
        message += (f" ({len(beyond_catalog)} additional entr{plural} not in the catalog: "
                     f"{', '.join(sorted(beyond_catalog))})")
    result.add(REGISTRY_PATH, 0, "REGISTRY_COVERAGE", message, "INFO")


def validate_component_registry(parsed_contracts):
    result = ValidationResult()
    registry = parsed_contracts.get(REGISTRY_PATH)
    if not registry:
        return result
    components = registry.get("components") or {}
    for name, meta in components.items():
        _check_component(name, meta or {}, result)
    _report_coverage(components, result)
    return result
