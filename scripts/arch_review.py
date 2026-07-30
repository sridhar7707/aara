#!/usr/bin/env python3
"""
Architectural design enforcer and coding standards checker for ai-trading-bot.

Usage:
    python scripts/arch_review.py              # check all bot/ dashboard/ database/ files
    python scripts/arch_review.py bot/main.py  # check specific files
    python scripts/arch_review.py --diff       # check only files changed in git diff (staged+unstaged)
"""
import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 6-Layer architecture from ARCHITECTURE.md
# Layer N may only import from layers with lower numbers.
# The execution layer (5) MUST pass through risk (4) — never called directly
# from strategy layers.
# ---------------------------------------------------------------------------
LAYER_ORDER = ["data", "regime", "rl_agent", "risk", "execution", "monitoring", "core", "dashboard", "database"]

LAYER_PATHS: dict[str, list[str]] = {
    "data":       ["bot/strategy/features.py", "bot/strategy/macro.py",
                   "bot/strategy/sentiment.py", "bot/strategy/reddit_sentiment.py"],
    "regime":     ["bot/strategy/regime_classifier.py"],
    "rl_agent":   ["bot/strategy/rl_agent.py", "bot/strategy/ensemble.py",
                   "bot/strategy/xgb_predictor.py", "bot/strategy/lstm_predictor.py"],
    "risk":       ["bot/risk/risk_manager.py"],
    "execution":  ["bot/execution/alpaca_client.py"],
    "monitoring": ["bot/monitor/"],
    "core":       ["bot/core/"],
    "dashboard":  ["dashboard/"],
    "database":   ["database/"],
}

# Strategy layers must never call execution directly (must go via risk manager)
STRATEGY_LAYERS = {"data", "regime", "rl_agent"}
EXECUTION_SYMBOLS = re.compile(r'\balpaca_client\b|\bsubmit_order\b|\bplace_order\b', re.IGNORECASE)

# Critical risk thresholds — any change to these is a [BLOCK]
RISK_THRESHOLDS = {
    "stop_loss":   (r'0\.04\b|4\.0\b', "Stop-loss must be 4%"),
    "daily_loss":  (r'0\.05\b|5\.0\b', "Daily loss limit must be 5%"),
    "max_position":(r'0\.20\b|20\.0\b', "Max position size must be 20%"),
}

SECRET_PATTERNS = [
    (r'(?i)(api_key|secret|password|token|credential)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret"),
    (r'APCA-API-KEY-ID\s*=\s*["\'][A-Z0-9]{20,}', "Hardcoded Alpaca key"),
    (r'(?i)telegram.*token\s*=\s*["\'][0-9]{8,}:[A-Za-z0-9_-]{30,}', "Hardcoded Telegram token"),
]

MAX_FILE_LINES = 500

PRODUCTION_DIRS = {"bot", "dashboard", "database"}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    file: str
    line: int
    rule: str
    message: str
    severity: str = "ERROR"   # BLOCK | ERROR | WARN | INFO


@dataclass
class ReviewResult:
    violations: list[Violation] = field(default_factory=list)

    def add(self, file: str, line: int, rule: str, message: str, severity: str = "ERROR"):
        self.violations.append(Violation(str(file), line, rule, message, severity))

    @property
    def blocks(self):
        return [v for v in self.violations if v.severity == "BLOCK"]

    @property
    def errors(self):
        return [v for v in self.violations if v.severity == "ERROR"]

    @property
    def warnings(self):
        return [v for v in self.violations if v.severity == "WARN"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _posix(path) -> str:
    return str(path).replace("\\", "/")


def get_layer(file_str: str) -> Optional[str]:
    s = file_str.replace("\\", "/")
    for layer, paths in LAYER_PATHS.items():
        for p in paths:
            if s.endswith(p) or f"/{p}" in s or s.startswith(p):
                return layer
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_file_size(path: Path, result: ReviewResult):
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return
    if len(lines) > MAX_FILE_LINES:
        result.add(path, MAX_FILE_LINES, "FILE_SIZE",
                   f"{len(lines)} lines — max is {MAX_FILE_LINES}", "WARN")


def check_secrets(path: Path, content: str, result: ReviewResult):
    for i, line in enumerate(content.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, line):
                result.add(path, i, "HARDCODED_SECRET", f"{desc} detected", "BLOCK")


def check_print_statements(path: Path, tree: Optional[ast.AST], result: ReviewResult):
    top = _posix(path).split("/")[0]
    if top not in PRODUCTION_DIRS or tree is None:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                result.add(path, node.lineno, "USE_LOGGING",
                           "Use logging instead of print() in production code", "WARN")


def check_risk_bypass(path: Path, content: str, result: ReviewResult):
    layer = get_layer(_posix(path))
    if layer not in STRATEGY_LAYERS:
        return
    for i, line in enumerate(content.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        if EXECUTION_SYMBOLS.search(line):
            result.add(path, i, "RISK_BYPASS",
                       "Strategy layer must not call execution layer directly — route through risk manager", "BLOCK")


def check_risk_constants(path: Path, content: str, result: ReviewResult):
    # Thresholds live in config.py as env-overridable defaults.
    if not _posix(path).endswith("config.py"):
        return
    checks = [
        (r"STOP_LOSS_PCT\s*=.*0\.04", "STOP_LOSS_PCT default must be 0.04 (4%)"),
        (r"DAILY_LOSS_LIMIT_PCT\s*=.*0\.05", "DAILY_LOSS_LIMIT_PCT default must be 0.05 (5%)"),
        (r"MAX_POSITION_PCT\s*=.*0\.20", "MAX_POSITION_PCT default must be 0.20 (20%)"),
    ]
    for pattern, msg in checks:
        if not re.search(pattern, content):
            result.add(path, 0, "RISK_THRESHOLD",
                       f"{msg} — default appears changed, verify intentional", "ERROR")


_TEST_IMPORT_EDGES_CACHE: dict[Path, tuple[set[tuple[str, str]], set[str]]] = {}


def _test_import_edges(project_root: Path) -> tuple[set[tuple[str, str]], set[str]]:
    """({(module, name)} for `from module import name`, {module} for `import module`)
    across every tests/**/test_*.py file.

    AST-based rather than regex-on-raw-text: a regex scan can't distinguish a
    real import from the same text inside a comment, and `[^\\n]*` can't span
    the multi-line parenthesized imports this repo's facades commonly use
    (e.g. bot/_main_db.py's `from bot.db.X import (\\n    name,\\n)` blocks) —
    both would silently break the facade-tracing this exists to support.

    Cached per project_root: arch_review calls this once per bot/ file
    checked (147+ times per run) but the test tree doesn't change mid-run.
    """
    cached = _TEST_IMPORT_EDGES_CACHE.get(project_root)
    if cached is not None:
        return cached
    from_edges: set[tuple[str, str]] = set()
    plain_imports: set[str] = set()
    tests_dir = project_root / "tests"
    if tests_dir.is_dir():
        for f in tests_dir.rglob("test_*.py"):
            if "__pycache__" in f.parts:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        from_edges.add((node.module, alias.name))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        plain_imports.add(alias.name)
    edges = (from_edges, plain_imports)
    _TEST_IMPORT_EDGES_CACHE[project_root] = edges
    return edges


_REEXPORT_EDGES_CACHE: dict[Path, list[tuple[str, str, str, str]]] = {}


def _reexport_edges(project_root: Path) -> list[tuple[str, str, str, str]]:
    """(source_module, orig_name, bound_name, importer_module) for every
    `from source_module import orig_name [as bound_name]` in production code.

    Used to follow this repo's facade pattern (e.g. bot/_main_db.py
    re-exporting bot/db/*.py helpers under a renamed alias for bot/main.py
    to import) so coverage of the alias counts as coverage of the leaf.
    """
    cached = _REEXPORT_EDGES_CACHE.get(project_root)
    if cached is not None:
        return cached
    edges: list[tuple[str, str, str, str]] = []
    for subdir in PRODUCTION_DIRS:
        d = project_root / subdir
        if not d.is_dir():
            continue
        for f in d.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except (SyntaxError, OSError):
                continue
            importer_dotted = ".".join(f.relative_to(project_root).with_suffix("").parts)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        edges.append((node.module, alias.name, alias.asname or alias.name, importer_dotted))
    _REEXPORT_EDGES_CACHE[project_root] = edges
    return edges


def _facade_covered(project_root: Path, dotted: str, symbols: set[str]) -> set[tuple[str, str]]:
    """BFS the re-export graph: every (module, name) pair a test could
    plausibly import that still traces back to `dotted`'s own symbols."""
    edges = _reexport_edges(project_root)
    frontier = {(dotted, name) for name in symbols}
    covered = set(frontier)
    for _ in range(4):  # bounded depth — facades in this repo are 1-2 hops
        new = {
            (importer, bound)
            for (mod, name) in frontier
            for (src, orig, bound, importer) in edges
            if src == mod and orig == name and (importer, bound) not in covered
        }
        if not new:
            break
        covered |= new
        frontier = new
    return covered


def check_missing_tests(path: Path, tree: Optional[ast.AST], project_root: Path, result: ReviewResult):
    s = _posix(path)
    if not s.startswith("bot/") or "__init__" in s:
        return
    module = path.stem
    dotted = ".".join(path.with_suffix("").parts)
    parent_dotted = ".".join(path.parent.parts)
    from_edges, plain_imports = _test_import_edges(project_root)

    # Module is covered if any test file (anywhere under tests/, not just
    # tests/test_<module>.py) imports it directly, via its parent package,
    # or via a re-exported alias reachable through the facade pattern.
    covered = (
        dotted in plain_imports
        or any(mod == dotted for mod, _name in from_edges)
        or (parent_dotted, module) in from_edges
    )
    if not covered:
        symbols = {
            n.name for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        } if tree is not None else set()
        covered = any(
            (mod, name) in from_edges
            for mod, name in _facade_covered(project_root, dotted, symbols)
        )
    if not covered:
        result.add(path, 0, "MISSING_TESTS",
                   f"No test file imports {dotted} directly or via a re-export "
                   f"(checked tests/**/test_*.py)", "WARN")


def check_type_hints(path: Path, tree: Optional[ast.AST], result: ReviewResult):
    top = _posix(path).split("/")[0]
    if top not in PRODUCTION_DIRS or tree is None:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        missing = []
        for arg in node.args.args:
            if arg.arg == "self":
                continue
            if arg.annotation is None:
                missing.append(arg.arg)
        if node.returns is None:
            missing.append("return")
        if missing:
            result.add(path, node.lineno, "TYPE_HINTS",
                       f"Public function '{node.name}' missing type hints for: {', '.join(missing)}", "WARN")


def check_env_var_usage(path: Path, content: str, result: ReviewResult):
    """Config values should come from os.environ / config.py, not literals in bot code."""
    top = _posix(path).split("/")[0]
    if top not in {"bot", "scripts"}:
        return
    # Detect direct use of known env-var names as string literals
    for i, line in enumerate(content.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        if re.search(r'"(APCA_API_KEY|TELEGRAM_TOKEN|FRED_API_KEY|HF_TOKEN)"', line):
            if "os.environ" not in line and "os.getenv" not in line and "getenv" not in line:
                result.add(path, i, "ENV_VAR_LITERAL",
                           "Reference env var via os.getenv() or config.py, not bare string", "WARN")


# ---------------------------------------------------------------------------
# File scanner
# ---------------------------------------------------------------------------

def review_file(path: Path, project_root: Path, result: ReviewResult):
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        rel = path

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return

    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None

    check_file_size(rel, result)
    check_secrets(rel, content, result)
    check_print_statements(rel, tree, result)
    check_risk_bypass(rel, content, result)
    check_risk_constants(rel, content, result)
    check_missing_tests(rel, tree, project_root, result)
    check_type_hints(rel, tree, result)
    check_env_var_usage(rel, content, result)


def collect_project_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for subdir in ["bot", "dashboard", "database", "scripts", "config.py"]:
        p = project_root / subdir
        if p.is_dir():
            files.extend(p.rglob("*.py"))
        elif p.is_file():
            files.append(p)
    return files


def collect_diff_files(project_root: Path) -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=project_root, text=True, stderr=subprocess.DEVNULL
        )
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=project_root, text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return []
    names = set((out + staged).splitlines())
    return [project_root / n for n in names if n.endswith(".py")]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

SEVERITY_ICON = {"BLOCK": "[BLOCK]", "ERROR": "[ERROR]", "WARN": "[WARN]", "INFO": "[INFO]"}


def print_report(result: ReviewResult, files_checked: int) -> int:
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  ARCH REVIEW  --  {files_checked} file(s) checked")
    print(sep)

    if not result.violations:
        print("  PASS: All checks passed.\n")
        return 0

    for severity in ("BLOCK", "ERROR", "WARN", "INFO"):
        items = [v for v in result.violations if v.severity == severity]
        if not items:
            continue
        icon = SEVERITY_ICON[severity]
        print(f"\n  {icon} ({len(items)})")
        print(f"  {'-'*58}")
        for v in items:
            loc = f"{v.file}:{v.line}" if v.line else v.file
            print(f"  [{v.rule}]  {loc}")
            print(f"    {v.message}")

    b, e, w = len(result.blocks), len(result.errors), len(result.warnings)
    print(f"\n{sep}")
    print(f"  Results: {b} block(s)  {e} error(s)  {w} warning(s)")
    print(sep + "\n")
    return 1 if (b or e) else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    project_root = Path(__file__).resolve().parent.parent

    args = sys.argv[1:]

    if "--diff" in args:
        files = collect_diff_files(project_root)
        if not files:
            print("No Python files in the current diff.")
            sys.exit(0)
    elif args:
        files = [Path(a) if Path(a).is_absolute() else project_root / a for a in args]
    else:
        files = collect_project_files(project_root)

    files = [f for f in files if f.exists() and f.suffix == ".py"]

    result = ReviewResult()
    for f in files:
        review_file(f, project_root, result)

    exit_code = print_report(result, len(files))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
