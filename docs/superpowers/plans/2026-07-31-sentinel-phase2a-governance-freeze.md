# Sentinel Phase 2A Governance Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the already-partial Sentinel governance control plane (validator self-integrity, VERSION_LOCK structural freeze checks, orphan-contract detection, freeze evidence) into a single `tools/validate_all.py` entrypoint, wired into a new blocking CI gate — without duplicating the existing brand validator suite and without ever touching or exposing `docs/architecture/`.

**Architecture:** Extend the existing `tools/validate_brand_system.py` + `tools/validators/*` package (duplicate-key YAML loader, version-lock cross-checks, registry/icon/token/code-scan validators — all already working and passing cleanly) with three new checks (validator self-integrity, VERSION_LOCK structural rules, orphan-contract detection) plus a comprehensive orchestrator, a freeze-report generator, and a new narrow blocking CI workflow. The existing informational `ci.yml` Sentinel step and its documented Phase B deferral are left untouched.

**Tech Stack:** Python 3.11, PyYAML, GitHub Actions.

## Global Constraints

- Repo is confirmed **public** on GitHub (`sridhar7707/ai-trading-bot`).
- `docs/architecture/` (proprietary PRD/ADR/Trading Constitution/brand strategy docs) is confirmed gitignored, confirmed never committed (`git log --all` empty, `git ls-files` empty), and confirmed absent from `origin/main`. **Never** read its content into a generated artifact, never move/rename it, never add it to git.
- **DO NOT create** `tools/validators/yaml_utils.py` or `tools/validators/brand_contract_validator.py` — equivalent logic already exists as `tools/validators/yaml_contracts.py` (duplicate-key loader + version cross-check) and `tools/validators/registry_validator.py`. Extend those instead.
- **DO NOT commit anything in this session.** Every task below ends with a verification run, not a `git commit` step — that's a deliberate deviation from this skill's normal per-task commit convention, per explicit instruction. The final task stages nothing; it only reports `git status` / `git diff --cached --name-only` and hands the exact commit command back for manual approval.
- Follow the existing validator package's conventions exactly: `ValidationResult`/`Violation` from `tools/validators/types.py`, severities `BLOCK | ERROR | WARN | INFO`, `result.blocking` (BLOCK/ERROR) decides `sys.exit(1)`.
- This validator package has no pytest coverage today (verified: `find tests -iname "*valid*" -o -iname "*governance*" -o -iname "*brand*"` → empty). Verification for every task is "run the script, inspect printed output/exit code" — matching the existing pattern, not inventing a new one.
- Confirmed baseline: `python tools/validate_brand_system.py` currently exits 0 with one INFO advisory. Nothing here should regress that.

---

### Task 1: Shared strict-YAML loader + VERSION_LOCK structural validation

**Files:**
- Modify: `tools/validators/yaml_contracts.py`

**Interfaces:**
- Produces: `load_yaml_strict(path: str) -> dict` (reusable duplicate-key-rejecting loader), `validate_version_lock_structure(parsed_contracts: dict, validator_suite: dict) -> ValidationResult` — both consumed by Task 3 and Task 5.

- [ ] **Step 1: Extract the duplicate-key loader into a reusable function**

Replace the body of `load_contracts()` in `tools/validators/yaml_contracts.py` — add this function right after `_unique_key_loader()`:

```python
def load_yaml_strict(path):
    """Loads one YAML file with the duplicate-key-rejecting loader. Raises
    on a missing file, bad YAML, or a duplicate key -- callers decide how
    to turn that into a ValidationResult, this function never swallows it.
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=_unique_key_loader())
```

Then rewrite `load_contracts()` to use it:

```python
def load_contracts():
    """Returns (parsed_contracts: dict[path, obj], ValidationResult).

    Parsing continues past a single bad contract so one broken file doesn't
    hide errors in the rest.
    """
    result = ValidationResult()
    parsed = {}
    for contract in YAML_CONTRACTS:
        if not os.path.exists(contract):
            result.add(contract, 0, "YAML_CONTRACT_MISSING",
                        f"Missing mandatory YAML contract: {contract}", "BLOCK")
            continue
        try:
            parsed[contract] = load_yaml_strict(contract)
        except Exception as e:
            result.add(contract, 0, "YAML_INVALID", f"Invalid YAML syntax or structure: {e}", "BLOCK")
    return parsed, result
```

- [ ] **Step 2: Run the existing suite to confirm the refactor is behavior-preserving**

Run: `python tools/validate_brand_system.py`
Expected: unchanged — `Brand Governance Validation PASSED with advisories` and the same single `REGISTRY_COVERAGE` INFO line as before, exit 0.

- [ ] **Step 3: Add VERSION_LOCK structural validation**

Append to `tools/validators/yaml_contracts.py`:

```python
VERSION_LOCK_REQUIRED_SECTIONS = ["release", "contracts", "compatibility", "identities"]
VERSION_LOCK_REQUIRED_RELEASE_FIELDS = ["name", "version", "status", "date"]


def validate_version_lock_structure(parsed_contracts, validator_suite):
    """Structural checks on brand/VERSION_LOCK.yaml's own shape -- required
    top-level sections, required release: fields, frozen status, and that
    release.version matches the validator suite's declared
    compatible_brand_version (tools/validators/VERSION.yaml). Complements
    validate_version_lock() above, which checks the four *contract*
    versions listed under `contracts:` against each contract file's own
    declared version -- that one checks cross-file alignment, this one
    checks this one file's own required shape.
    """
    result = ValidationResult()
    lock_data = parsed_contracts.get("brand/VERSION_LOCK.yaml")
    if not lock_data:
        return result

    for section in VERSION_LOCK_REQUIRED_SECTIONS:
        if section not in lock_data:
            result.add("brand/VERSION_LOCK.yaml", 0, "VERSION_LOCK_SECTION_MISSING",
                        f"Missing required top-level section: {section}", "BLOCK")

    release = lock_data.get("release") or {}
    for field in VERSION_LOCK_REQUIRED_RELEASE_FIELDS:
        if field not in release:
            result.add("brand/VERSION_LOCK.yaml", 0, "VERSION_LOCK_RELEASE_FIELD_MISSING",
                        f"release: section missing required field: {field}", "BLOCK")

    status = release.get("status")
    if "status" in release and status != "frozen":
        result.add("brand/VERSION_LOCK.yaml", 0, "VERSION_LOCK_NOT_FROZEN",
                    f"release.status must be 'frozen', got {status!r}", "BLOCK")

    if validator_suite:
        compatible = validator_suite.get("compatible_brand_version")
        release_version = release.get("version")
        if "version" in release and compatible is not None and release_version != compatible:
            result.add("brand/VERSION_LOCK.yaml", 0, "VERSION_LOCK_VALIDATOR_MISMATCH",
                        f"release.version ({release_version!r}) does not match validator suite's "
                        f"compatible_brand_version ({compatible!r})", "BLOCK")
    return result
```

- [ ] **Step 4: Sanity-check against the real file**

Run:
```bash
python -c "
from tools.validators.yaml_contracts import load_contracts, validate_version_lock_structure
parsed, _ = load_contracts()
r = validate_version_lock_structure(parsed, {'compatible_brand_version': '1.0'})
print(len(r.violations), 'violations')
"
```
Expected: `0 violations` — `brand/VERSION_LOCK.yaml` today has `release: {name, version: "1.0", status: frozen, date}`, `contracts:`, `compatibility:`, `identities:` (confirmed by reading the file), so this must pass clean against a matching compatible version.

---

### Task 2: Validator suite self-integrity file and check

**Files:**
- Create: `tools/validators/VERSION.yaml`
- Create: `tools/validators/suite_integrity.py`

**Interfaces:**
- Consumes: `load_yaml_strict` from Task 1 (`tools/validators/yaml_contracts.py`).
- Produces: `load_validator_suite() -> tuple[dict | None, ValidationResult]`, consumed by Task 3 (orphan strict_mode) and Task 5 (`validate_all.py`).

- [ ] **Step 1: Create the self-declaration file**

Create `tools/validators/VERSION.yaml`:

```yaml
validator_suite:
  name: "Sentinel Governance Validator"
  version: "1.0"
  compatible_brand_version: "1.0"
  status: frozen
  strict_mode: true
```

- [ ] **Step 2: Write the self-integrity check module**

Create `tools/validators/suite_integrity.py`:

```python
"""Validates the governance validator suite's own self-declaration
(tools/validators/VERSION.yaml) -- a 'frozen' governance suite that
silently drifts its own status or strict-mode flag would be worse than no
self-check at all, since every other check in this package implicitly
trusts strict_mode to decide BLOCK vs WARN severity.
"""
import os

from .types import ValidationResult
from .yaml_contracts import load_yaml_strict

VERSION_PATH = "tools/validators/VERSION.yaml"
REQUIRED_FIELDS = ["name", "version", "compatible_brand_version", "status", "strict_mode"]


def load_validator_suite():
    """Returns (validator_suite: dict | None, ValidationResult)."""
    result = ValidationResult()
    if not os.path.exists(VERSION_PATH):
        result.add(VERSION_PATH, 0, "VALIDATOR_VERSION_MISSING",
                    f"Missing validator self-integrity file: {VERSION_PATH}", "BLOCK")
        return None, result
    try:
        data = load_yaml_strict(VERSION_PATH)
    except Exception as e:
        result.add(VERSION_PATH, 0, "VALIDATOR_VERSION_INVALID", f"Invalid YAML: {e}", "BLOCK")
        return None, result

    suite = (data or {}).get("validator_suite")
    if not suite:
        result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_MISSING",
                    "Missing top-level validator_suite: section", "BLOCK")
        return None, result

    for field in REQUIRED_FIELDS:
        if field not in suite:
            result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_FIELD_MISSING",
                        f"validator_suite: missing required field: {field}", "BLOCK")

    status = suite.get("status")
    if "status" in suite and status != "frozen":
        result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_NOT_FROZEN",
                    f"validator_suite.status must be 'frozen', got {status!r}", "BLOCK")

    strict_mode = suite.get("strict_mode")
    # isinstance(True, int) is True in Python (bool subclasses int), but
    # isinstance(1, bool) is False -- checking isinstance(..., bool) first
    # correctly accepts real YAML booleans and rejects "true"/"false"
    # strings and 1/0 ints.
    if "strict_mode" in suite and not isinstance(strict_mode, bool):
        result.add(VERSION_PATH, 0, "VALIDATOR_SUITE_STRICT_MODE_TYPE",
                    f"validator_suite.strict_mode must be a YAML boolean (true/false), "
                    f"got {strict_mode!r} ({type(strict_mode).__name__})", "BLOCK")

    return suite, result
```

- [ ] **Step 3: Run it standalone**

Run:
```bash
python -c "
from tools.validators.suite_integrity import load_validator_suite
suite, result = load_validator_suite()
print(suite)
print(len(result.violations), 'violations')
"
```
Expected: prints the dict `{'name': 'Sentinel Governance Validator', 'version': '1.0', 'compatible_brand_version': '1.0', 'status': 'frozen', 'strict_mode': True}` and `0 violations`.

- [ ] **Step 4: Verify the strict-type rejection actually rejects**

Run:
```bash
python -c "
import yaml
data = yaml.safe_load('validator_suite:\n  strict_mode: \"true\"\n')
print(isinstance(data['validator_suite']['strict_mode'], bool))
"
```
Expected: `False` — confirms a quoted string would be correctly flagged by the check in Step 2 (do not change `VERSION.yaml` itself; this is just confirming the type check logic).

---

### Task 3: Orphan YAML contract detection

**Files:**
- Create: `tools/validators/orphan_validator.py`

**Interfaces:**
- Consumes: `YAML_CONTRACTS` list from `tools/validators/yaml_contracts.py` (Task 1's file, unchanged constant).
- Produces: `validate_no_orphan_contracts(strict_mode: bool) -> ValidationResult`, consumed by Task 5.

- [ ] **Step 1: Write the orphan check**

Create `tools/validators/orphan_validator.py`:

```python
"""Detects YAML files under brand/ that aren't declared in
yaml_contracts.YAML_CONTRACTS -- an undeclared contract file is either
dead weight or a governance gap (a new contract nobody wired into
VERSION_LOCK.yaml's tracking).
"""
import glob

from .types import ValidationResult
from .yaml_contracts import YAML_CONTRACTS


def validate_no_orphan_contracts(strict_mode):
    result = ValidationResult()
    allowed = set(YAML_CONTRACTS)
    found = {p.replace("\\", "/") for p in glob.glob("brand/**/*.yaml", recursive=True)}
    orphans = found - allowed
    severity = "BLOCK" if strict_mode else "WARN"
    for orphan in sorted(orphans):
        result.add(orphan, 0, "ORPHAN_YAML_CONTRACT",
                    f"YAML file under brand/ is not declared in yaml_contracts.YAML_CONTRACTS: {orphan}",
                    severity)
    return result
```

- [ ] **Step 2: Run against the current repo state (should be clean)**

Run:
```bash
python -c "
from tools.validators.orphan_validator import validate_no_orphan_contracts
r = validate_no_orphan_contracts(True)
print(len(r.violations), 'violations')
"
```
Expected: `0 violations` — confirmed earlier that `brand/*.yaml` and `brand/design_system/*.yaml` today contain exactly the 5 files already in `YAML_CONTRACTS`.

- [ ] **Step 3: Verify the strict_mode severity switch works**

Run:
```bash
python -c "
import os
os.makedirs('brand/tmp_orphan_test', exist_ok=True)
open('brand/tmp_orphan_test/EXTRA.yaml', 'w').write('x: 1\n')
from tools.validators.orphan_validator import validate_no_orphan_contracts
strict = validate_no_orphan_contracts(True)
loose = validate_no_orphan_contracts(False)
print('strict:', strict.violations[0].severity)
print('loose:', loose.violations[0].severity)
os.remove('brand/tmp_orphan_test/EXTRA.yaml')
os.rmdir('brand/tmp_orphan_test')
"
```
Expected: `strict: BLOCK` then `loose: WARN`. The temp file is created and removed by the same command — nothing left behind.

---

### Task 4: Refactor `validate_brand_system.py` to expose a reusable check function

**Files:**
- Modify: `tools/validate_brand_system.py`

**Interfaces:**
- Produces: `run_brand_checks() -> ValidationResult`, consumed by Task 5 (`validate_all.py`).
- `main()`'s printed output and exit-code behavior must stay byte-for-byte identical to today — this is a pure extraction, not a behavior change.

- [ ] **Step 1: Extract the check-running body into its own function**

Replace the full contents of `tools/validate_brand_system.py` with:

```python
#!/usr/bin/env python3
"""
Sentinel Brand & UI Governance Validator -- runner.

Aggregates findings from tools/validators/*; each module owns one
governance concern (YAML contracts, icons, tokens, code purity, registry
consistency) and reports Violations with a stable `rule` code, matching
scripts/arch_review.py's existing convention in this repo.
"""
import sys

from validators.allowlist import load_allowlist
from validators.code_scan_validator import validate_code
from validators.icon_validator import validate_icons
from validators.registry_validator import validate_component_registry
from validators.token_validator import validate_tokens
from validators.types import ValidationResult
from validators.yaml_contracts import load_contracts, validate_version_lock


def run_brand_checks() -> ValidationResult:
    """Runs every brand/UI governance check and returns the combined
    result. Raises ValueError if tools/validators/allowlist.yaml has an
    entry missing a justification -- that's a config error, not a check
    result, so it propagates instead of being folded into the violations
    list.
    """
    allowlist = load_allowlist()

    result = ValidationResult()
    parsed_contracts, contract_result = load_contracts()
    result.extend(contract_result)
    result.extend(validate_version_lock(parsed_contracts))
    result.extend(validate_icons(parsed_contracts))
    result.extend(validate_tokens())
    result.extend(validate_code(parsed_contracts, allowlist))
    result.extend(validate_component_registry(parsed_contracts))
    return result


def main():
    print("Executing Sentinel Brand Governance Validation...")

    try:
        result = run_brand_checks()
    except ValueError as e:
        print(f"\nBrand Governance Validation FAILED:\n  - [ERROR] ALLOWLIST_CONFIG: {e}")
        sys.exit(1)

    if result.violations:
        header = "FAILED" if result.blocking else "PASSED with advisories"
        print(f"\nBrand Governance Validation {header}:")
        for v in result.violations:
            location = f"{v.file}:{v.line}" if v.line else v.file
            print(f"  - [{v.severity}] {v.rule} {location}: {v.message}")
        sys.exit(1 if result.blocking else 0)
    else:
        print("Sentinel Brand Governance Validation PASSED cleanly.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Confirm zero behavior change**

Run: `python tools/validate_brand_system.py`
Expected: identical to the Task 1 Step 2 baseline — `PASSED with advisories`, one `REGISTRY_COVERAGE` INFO line, exit 0.

---

### Task 5: Comprehensive `tools/validate_all.py` entrypoint

**Files:**
- Create: `tools/validate_all.py`

**Interfaces:**
- Consumes: `run_brand_checks()` (Task 4), `load_validator_suite()` (Task 2), `validate_no_orphan_contracts()` (Task 3), `validate_version_lock_structure()` + `load_contracts()` (Task 1).
- Produces: `run_all_checks() -> ValidationResult`, consumed by Task 7 (`generate_freeze_report.py`) and by CI (Task 8).

- [ ] **Step 1: Write the orchestrator**

Create `tools/validate_all.py`:

```python
#!/usr/bin/env python3
"""Sentinel Governance Validator -- Phase 2A comprehensive entrypoint.

Runs every governance check in one pass: the existing brand/UI suite
(validate_brand_system.run_brand_checks), plus the Phase 2A additions --
validator self-integrity (tools/validators/VERSION.yaml), VERSION_LOCK.yaml
structural checks, and orphan-contract detection. This is the single
command CI and tools/generate_freeze_report.py both call, so there is one
governance verdict, not several that can disagree.
"""
import sys

from validate_brand_system import run_brand_checks
from validators.orphan_validator import validate_no_orphan_contracts
from validators.suite_integrity import load_validator_suite
from validators.types import ValidationResult
from validators.yaml_contracts import load_contracts, validate_version_lock_structure


def run_all_checks() -> ValidationResult:
    result = ValidationResult()

    validator_suite, suite_result = load_validator_suite()
    result.extend(suite_result)

    parsed_contracts, _ = load_contracts()
    result.extend(validate_version_lock_structure(parsed_contracts, validator_suite or {}))

    strict_mode = bool((validator_suite or {}).get("strict_mode", True))
    result.extend(validate_no_orphan_contracts(strict_mode))

    result.extend(run_brand_checks())
    return result


def main():
    print("Executing Sentinel Governance Validation (Phase 2A, full suite)...")
    try:
        result = run_all_checks()
    except ValueError as e:
        print(f"\nGovernance Validation FAILED:\n  - [ERROR] CONFIG: {e}")
        sys.exit(1)

    if result.violations:
        header = "FAILED" if result.blocking else "PASSED with advisories"
        print(f"\nGovernance Validation {header}:")
        for v in result.violations:
            location = f"{v.file}:{v.line}" if v.line else v.file
            print(f"  - [{v.severity}] {v.rule} {location}: {v.message}")
        if result.blocking:
            sys.exit(1)
        return

    print("ALL GOVERNANCE CHECKS PASSED CLEANLY.\nSUITE FULLY COMPLIANT.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it from the repo root**

Run: `python tools/validate_all.py`
Expected:
```
Executing Sentinel Governance Validation (Phase 2A, full suite)...

Governance Validation PASSED with advisories:
  - [INFO] REGISTRY_COVERAGE brand/design_system/COMPONENT_REGISTRY.yaml: registry tracks 9/9 catalog components in docs/architecture/SENTINEL_COMPONENT_CATALOG.md (1 additional entry not in the catalog: GovernancePanel)
```
Exit code 0 (INFO-only, not blocking). If this instead prints `ALL GOVERNANCE CHECKS PASSED CLEANLY.` with zero violations, that's also acceptable — it means `docs/architecture/SENTINEL_COMPONENT_CATALOG.md` wasn't present in whatever environment ran it (fine locally where it exists; in CI it will genuinely be absent since that directory is gitignored, and `registry_validator.py` already handles that case at WARN).

---

### Task 6: Pinned validator dependency file

**Files:**
- Create: `tools/requirements-validator.txt`

- [ ] **Step 1: Create the pinned dependency file**

Create `tools/requirements-validator.txt`:

```
PyYAML==6.0.2
```

- [ ] **Step 2: Verify it installs cleanly in isolation**

Run: `pip install -r tools/requirements-validator.txt --dry-run`
Expected: no errors (PyYAML 6.0.2 resolvable; the repo's main `requirements.txt` already pins `PyYAML>=6.0.0`, so this is compatible, just stricter for the validator job specifically).

---

### Task 7: Freeze report generator

**Files:**
- Create: `tools/generate_freeze_report.py`
- Create: `release/README.md`

**Interfaces:**
- Consumes: `run_all_checks()` (Task 5), `load_validator_suite()` (Task 2), `load_contracts()` (Task 1).

- [ ] **Step 1: Document the release/ directory's rules**

Create `release/README.md`:

```markdown
# Release Evidence Layer

Purpose: immutable validation evidence, freeze reports, and release
verification artifacts for Sentinel governance milestones.

Rules:
- Contents are generated during release preparation (see
  `tools/generate_freeze_report.py`), not hand-written.
- Every report references the validator suite version and the Git commit
  SHA it was generated against.
- Contains no proprietary strategy information: no content from
  `docs/architecture/` may ever be copied or referenced here.
- Contains no customer, broker, account, or portfolio data.
```

- [ ] **Step 2: Write the report generator**

Create `tools/generate_freeze_report.py`:

```python
#!/usr/bin/env python3
"""Generates release/phase2a-validation-report.txt -- the auditable
freeze-evidence artifact for Sentinel Phase 2A. Refuses to write a report
claiming FROZEN status if the governance suite doesn't currently pass; a
freeze report is a signed attestation, not a status dump, so it must
never say FROZEN over a failing suite. Contains only validator/contract
metadata -- never reads or references docs/architecture/.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

from validate_all import run_all_checks
from validators.suite_integrity import load_validator_suite
from validators.yaml_contracts import load_contracts

REPORT_PATH = "release/phase2a-validation-report.txt"


def _git_sha():
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def main():
    result = run_all_checks()
    if result.blocking:
        print("Cannot generate freeze report: governance suite has blocking violations.")
        for v in result.blocking:
            print(f"  - [{v.severity}] {v.rule} {v.file}: {v.message}")
        sys.exit(1)

    validator_suite, _ = load_validator_suite()
    parsed_contracts, _ = load_contracts()
    lock = parsed_contracts.get("brand/VERSION_LOCK.yaml") or {}
    validator_suite = validator_suite or {}

    lines = [
        "SENTINEL GOVERNANCE FREEZE REPORT",
        "",
        "Stage:",
        "Phase 2A",
        "",
        "Git Commit SHA:",
        _git_sha(),
        "",
        "UTC Timestamp:",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "",
        "Validator Version:",
        str(validator_suite.get("version", "unknown")),
        "",
        "Validator Status:",
        str(validator_suite.get("status", "unknown")),
        "",
        "Compatibility (brand) Version:",
        str(validator_suite.get("compatible_brand_version", "unknown")),
        "",
        "Contract Versions:",
    ]
    for key, version in (lock.get("contracts") or {}).items():
        lines.append(f"  {key}: {version}")
    lines += ["", "Status:", "FROZEN"]

    os.makedirs("release", exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Freeze report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Generate a report and manually inspect it for leaks**

Run: `python tools/generate_freeze_report.py`
Expected: `Freeze report written to release/phase2a-validation-report.txt`, exit 0.

Then read the file and confirm by inspection that it contains only: stage name, git SHA, UTC timestamp, validator version/status, compatibility version, and the four contract versions (`manifest`, `state_mapping`, `metric_contract`, `component_registry`) — no file paths, prose, or content from `docs/architecture/`.

---

### Task 8: New blocking governance CI workflow

**Files:**
- Create: `.github/workflows/governance.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/governance.yml`:

```yaml
name: Sentinel Governance Validation

# Hard-blocking Phase 2A gate: validator self-integrity (tools/validators/
# VERSION.yaml), VERSION_LOCK.yaml structural freeze checks, orphan
# contract detection, and the existing brand/UI suite -- all via
# tools/validate_all.py. Confirmed passing cleanly as of 2026-07-31, so
# this can block from day one. ci.yml's separate informational Sentinel
# step is left as-is -- see its own comment for why that one stays soft
# while the registry/catalog baseline stabilizes; this workflow is a
# narrower, newer gate on top of Phase 2A invariants specifically.

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  governance:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'
          cache: pip

      - name: Install validator dependencies
        run: pip install -r tools/requirements-validator.txt --quiet

      - name: Run Sentinel governance validation
        run: python tools/validate_all.py
```

- [ ] **Step 2: Validate the workflow YAML syntax locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/governance.yml'))" && echo OK`
Expected: `OK`

---

### Task 9: Repo-root boundary documentation

**Files:**
- Create: `ARCHITECTURE_BOUNDARIES.md`

- [ ] **Step 1: Write the boundary doc**

Create `ARCHITECTURE_BOUNDARIES.md` at the repo root:

```markdown
# Repository Documentation & Governance Boundaries

This repo is public on GitHub. This file states, in one place, what is
public and what must never be tracked in git.

## Public

- `docs/` (top-level files: `ARCHITECTURE.md`, `GOALS.md`, `REQUIREMENTS.md`,
  etc.) — implementation-level documentation for the trading bot.
- `brand/` — Sentinel brand/UI governance *contracts* (`BRAND_MANIFEST.yaml`,
  `STATE_MAPPING.yaml`, `METRIC_CONTRACT.yaml`,
  `brand/design_system/COMPONENT_REGISTRY.yaml`, `VERSION_LOCK.yaml`) and
  their supporting guideline docs. These describe *what* the UI must look
  like and *how* it's validated, not investment logic or business strategy.
- `tools/` — governance validator source code (`tools/validate_all.py`,
  `tools/validators/*`). Code that enforces the boundary is itself public;
  the data it protects is not.
- `release/` — freeze evidence only (validator version, contract versions,
  git SHA, timestamps). See `release/README.md` for the exact rules.

## Private — never tracked in git

- `docs/architecture/` — proprietary PRDs, ADRs, the Trading Constitution,
  model/brand strategy documents, and internal roadmaps. Confirmed
  gitignored, confirmed never committed, confirmed absent from
  `origin/main` (verified 2026-07-31: `git log --all -- docs/architecture`
  and `git ls-files docs/architecture` both return nothing).
- `docs/PHASE_PLAN_decision_intelligence.md` — local planning doc.
- Anything matching `docs/internal/`, `*.draft.md`, `*.internal.md`,
  `scratch/`, `notes/` (see `.gitignore`).

## Enforcement (defense in depth, not just `.gitignore`)

1. `.gitignore` — first line of defense, but not trusted alone (see #2).
2. `scripts/check_forbidden_paths.py` — hardcoded pattern list, checked
   against `git ls-files` directly. Deliberately independent of
   `.gitignore`'s current content: editing `.gitignore` alone can never
   silently defeat this check. Run in CI via
   `.github/workflows/secret-scan.yml` (hard-blocking).
3. `tools/validate_all.py` — Sentinel governance contract validation
   (validator self-integrity, VERSION_LOCK freeze status, orphan contract
   detection, brand/UI checks). Run in CI via
   `.github/workflows/governance.yml` (hard-blocking).

Generated artifacts (freeze reports, validation output) must never read
from or reference `docs/architecture/` content — only file paths,
version strings, and pass/fail status.
```

- [ ] **Step 2: Confirm no proprietary content leaked into the doc**

Run: `grep -iE "trading.?constitution|model.?strategy|PRD" ARCHITECTURE_BOUNDARIES.md`
Expected: only matches the *filenames* mentioned as examples (e.g. "the Trading Constitution" as a category name) — no actual strategy content, since none was read from `docs/architecture/` to write this file.

---

### Task 10: `.gitignore` hardening

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add the missing private-path guards**

In `.gitignore`, immediately after the existing block:
```
# Architecture docs — kept local only, stripped from GitHub history 2026-07-29
docs/architecture/
```
add:
```

# Sentinel private IP guards (Phase 2A hardening)
docs/internal/
*.draft.md
*.internal.md
scratch/
notes/
```

- [ ] **Step 2: Confirm no currently-tracked file is accidentally caught**

Run: `git status --porcelain | grep -E "^ D|^D "`
Expected: no output — nothing currently tracked should start disappearing from `git status` as a result of this `.gitignore` change (these patterns match nothing that exists in the tracked tree today).

---

### Task 11: Harden `scripts/check_forbidden_paths.py` to match

**Files:**
- Modify: `scripts/check_forbidden_paths.py`

- [ ] **Step 1: Add matching proactive guards**

In `scripts/check_forbidden_paths.py`, add to the `PROACTIVE_GUARDS` list (it already has `docs/private/*`, `docs/private/**/*`) — insert after the existing `docs/private/` entries:

```python
    "docs/internal/*", "docs/internal/**/*",
    "*.draft.md",
    "*.internal.md",
    "scratch/*", "scratch/**/*",
    "notes/*", "notes/**/*",
```

- [ ] **Step 2: Run it**

Run: `python scripts/check_forbidden_paths.py`
Expected: `Forbidden path check: N tracked files checked, 0 violations.` (same clean pass as before this change — nothing new is tracked that matches these patterns).

---

### Task 12: Full verification and git-safety audit (no commit)

**Files:** none (verification only).

- [ ] **Step 1: Run the full comprehensive validator**

Run: `python tools/validate_all.py`
Expected: exit 0, either `ALL GOVERNANCE CHECKS PASSED CLEANLY. SUITE FULLY COMPLIANT.` or `PASSED with advisories` with only the known `REGISTRY_COVERAGE` INFO line.

- [ ] **Step 2: Run the existing forbidden-path and brand-system checks for regression**

Run:
```bash
python scripts/check_forbidden_paths.py
python tools/validate_brand_system.py
```
Expected: both exit 0, unchanged from their pre-task baselines.

- [ ] **Step 3: Git safety verification**

Run each and record output:
```bash
git status
git ls-files docs/architecture
git log --all -- docs/architecture
git grep -n "TRADING_CONSTITUTION"
git grep -n "MODEL_STRATEGY"
git grep -n "ADR_DECISIONS"
```
Expected: `git ls-files docs/architecture` and `git log --all -- docs/architecture` produce no output; the three `git grep` commands produce no output (only tracked files are searched, and none should reference these names).

- [ ] **Step 4: Report — do not commit**

List every file created/modified in this plan (Tasks 1–11), the validation output from Steps 1–3 above, and the exact commit command for the user to run themselves:

```bash
git add tools/ brand/ release/ .github/workflows/governance.yml .gitignore scripts/check_forbidden_paths.py ARCHITECTURE_BOUNDARIES.md
git status
git diff --cached --name-only
```

Tell the user: after they run the `git add` above themselves, re-check `git diff --cached --name-only` for any of `docs/architecture/`, `docs/private/`, `*.internal.md`, `*.draft.md` before committing — none should appear, since none of those paths are in the `git add` list above.

Stop here. Do not run `git add`, `git commit`, or `git push` — hand this back to the user per the explicit "do not commit automatically" instruction in the Global Constraints.
