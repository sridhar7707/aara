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
