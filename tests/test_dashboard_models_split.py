"""ADR-079 — dashboard/components/models.py split into a facade + 4 files.

Proves the public import surface and the import-time component
registration survived the split unchanged.
"""
import dashboard.components.models as m


def test_facade_re_exports_every_externally_imported_name():
    for name in (
        "render_validation_report",
        "render_investor_view",
        "render_paper_trading_scorecard",
        "render_institutional_metrics",
        "_lstm_loss_display",
        "_model_quality_fallback",
    ):
        assert hasattr(m, name), f"dashboard.components.models lost {name!r}"


def test_registration_side_effect_unchanged():
    from dashboard.registry import _specs  # internal, test-only peek

    for key, group, priority in (
        ("investor_out",  "FAST", 90),
        ("scorecard_out", "SLOW", 60),
        ("metrics_out",   "SLOW", 61),
        ("val_out",       "SLOW", 62),
    ):
        assert key in _specs, f"{key} missing from the component registry"
        spec = _specs[key]
        assert spec.group.name == group
        assert spec.priority == priority
