"""Shared finding type for the brand governance validators.

Mirrors scripts/arch_review.py's Violation/ReviewResult shape so this
repo has one consistent static-analysis convention, not two.
"""
from dataclasses import dataclass, field


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    message: str
    severity: str = "ERROR"   # BLOCK | ERROR | WARN | INFO


@dataclass
class ValidationResult:
    violations: list = field(default_factory=list)

    def add(self, file, line, rule, message, severity="ERROR"):
        self.violations.append(Violation(str(file), line, rule, message, severity))

    def extend(self, other: "ValidationResult"):
        self.violations.extend(other.violations)

    @property
    def blocking(self):
        """BLOCK/ERROR violations -- these fail the run. WARN/INFO are advisory."""
        return [v for v in self.violations if v.severity in ("BLOCK", "ERROR")]
