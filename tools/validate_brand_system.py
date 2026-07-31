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


def main():
    print("Executing Sentinel Brand Governance Validation...")

    try:
        allowlist = load_allowlist()
    except ValueError as e:
        print(f"\nBrand Governance Validation FAILED:\n  - [ERROR] ALLOWLIST_CONFIG: {e}")
        sys.exit(1)

    result = ValidationResult()
    parsed_contracts, contract_result = load_contracts()
    result.extend(contract_result)
    result.extend(validate_version_lock(parsed_contracts))
    result.extend(validate_icons(parsed_contracts))
    result.extend(validate_tokens())
    result.extend(validate_code(parsed_contracts, allowlist))
    result.extend(validate_component_registry(parsed_contracts))

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
