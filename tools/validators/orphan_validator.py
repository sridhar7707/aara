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
