"""Regression tests for scripts/hooks/secret_scan.py: real keys are caught, ordinary words are not."""
from scripts.hooks.secret_scan import scan_line

# Built at runtime so this test file itself contains no contiguous key-shaped string.
FAKE_OPENAI_STYLE_KEY = "sk-" + "A" * 24


def test_real_sk_key_is_flagged():
    assert "API secret key" in scan_line(f"key = {FAKE_OPENAI_STYLE_KEY}")


def test_words_containing_sk_dash_are_not_flagged():
    for line in (
        "the risk-management-policy-approval-threshold value",
        "from desk-quantitative-signals-engine import x",
    ):
        assert "API secret key" not in scan_line(line), line
