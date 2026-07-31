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
