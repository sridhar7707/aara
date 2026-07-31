"""Derives the internal-only metric label set from METRIC_CONTRACT.yaml, so
downstream checks can't drift from the single source of truth by
hardcoding their own copy.

Deliberately does NOT expose an "approved labels" allowlist for a
must-match-exactly check on UI strings -- most UI text (buttons, help
copy, headers) isn't a metric label at all, so a positive allowlist would
false-positive constantly. The internal-only/investor-visible distinction
is the one rule METRIC_CONTRACT.yaml actually states precisely enough to
enforce.
"""


def build_internal_only_labels(parsed_contracts):
    """Returns the set of metric display labels marked investor_visible:
    false in METRIC_CONTRACT.yaml -- e.g. raw model confidence, an internal
    diagnostic that must never appear in investor-facing UI copy."""
    contract = parsed_contracts.get("brand/METRIC_CONTRACT.yaml") or {}
    metrics = contract.get("metrics") or {}
    internal_only_labels = set()
    for meta in metrics.values():
        display = (meta or {}).get("display") or {}
        label = display.get("label")
        if label and display.get("investor_visible") is False:
            internal_only_labels.add(label)
    return internal_only_labels
