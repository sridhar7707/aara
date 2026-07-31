"""Scans UI source for hardcoded hex colors, forbidden marketing terms
(brand/guidelines/FORBIDDEN_UI_PATTERNS.md), and internal-only metric labels
leaking into investor-facing UI.

Python UI files (Gradio) are scanned via AST so only real string literals
are checked -- comments are already invisible to the parser, and docstrings
are explicitly excluded (see _docstring_node_ids). JS/TS/Vue files fall back
to a whole-file substring/regex scan.
"""
import ast
import os
import re

from .allowlist import is_color_exempt, is_file_exempt, is_term_exempt
from .metric_validator import build_internal_only_labels
from .types import ValidationResult

# Mirrors brand/guidelines/FORBIDDEN_UI_PATTERNS.md's "Prohibited AI
# Marketing Copy" / "Gimmick Gauges" sections. That doc is prose, not
# machine-readable, so this list is kept in sync by convention rather than
# parsed from it.
FORBIDDEN_TERMS = [
    "AI Confidence",
    "Decision Conviction",
    "Decision Conviction Score",
    "Trading Signals",
    "BUY NOW",
    "AI Predicts",
    "Fear & Greed",
    "Smart Trading Bot",
]

# JS/TS/Vue frontend doesn't exist yet (Sentinel committed to Gradio -- see
# sentinel/README.md "Layering"); kept so this validator still works if one
# is added later. Deliberately NOT scanning root-level dashboard/ -- that's
# the unrelated, already-shipped TradeGenius bot, never governed by this
# brand system.
FRONTEND_JS_EXTENSIONS = (".jsx", ".tsx", ".js", ".ts", ".vue")
PYTHON_UI_EXTENSIONS = (".py",)
SCAN_TARGETS = [
    ("frontend", FRONTEND_JS_EXTENSIONS),
    ("sentinel/frontend", PYTHON_UI_EXTENSIONS),
]

HEX_COLOR_REGEX = re.compile(r'#(?:[0-9a-fA-F]{3}){1,2}\b')


def _docstring_node_ids(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ids.add(id(body[0].value))
    return ids


def _check_string(filepath, lineno, text, internal_only_labels, allowlist, result):
    for term in FORBIDDEN_TERMS:
        if term in text and not is_term_exempt(term, filepath, allowlist):
            result.add(filepath, lineno, "FORBIDDEN_TERM", f"contains forbidden term '{term}'")
    for label in internal_only_labels:
        if label in text and not is_term_exempt(label, filepath, allowlist):
            result.add(
                filepath, lineno, "INTERNAL_METRIC_LEAK",
                f"exposes internal-only metric label '{label}' "
                f"(investor_visible: false in METRIC_CONTRACT.yaml)",
            )
    for hex_value in HEX_COLOR_REGEX.findall(text):
        if not is_color_exempt(hex_value, filepath, allowlist):
            result.add(filepath, lineno, "HARDCODED_HEX",
                        f"hardcoded hex color {hex_value}; use tokens.css variables")


def _scan_python_file(filepath, internal_only_labels, allowlist, result):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        result.add(filepath, e.lineno or 0, "PYTHON_SYNTAX_ERROR", str(e), "BLOCK")
        return
    skip_ids = _docstring_node_ids(tree)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip_ids):
            _check_string(filepath, node.lineno, node.value, internal_only_labels, allowlist, result)


def _scan_js_file(filepath, internal_only_labels, allowlist, result):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    _check_string(filepath, 1, content, internal_only_labels, allowlist, result)


def validate_code(parsed_contracts, allowlist):
    result = ValidationResult()
    internal_only_labels = build_internal_only_labels(parsed_contracts)
    for directory, extensions in SCAN_TARGETS:
        if not os.path.exists(directory):
            continue
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(extensions) or ".test." in file or ".spec." in file:
                    continue
                filepath = os.path.join(root, file)
                if is_file_exempt(filepath, allowlist):
                    continue
                if file.endswith(PYTHON_UI_EXTENSIONS):
                    _scan_python_file(filepath, internal_only_labels, allowlist, result)
                else:
                    _scan_js_file(filepath, internal_only_labels, allowlist, result)
    return result
