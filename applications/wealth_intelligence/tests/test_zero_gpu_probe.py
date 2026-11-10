"""Regression guard: the wealth Space runs on ZeroGPU, which will not start a Space that has no
@spaces.GPU function at startup. The probe and the `spaces` pin must stay together.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_wealth_entry_point_declares_a_zero_gpu_startup_probe():
    source = (ROOT / "applications" / "wealth_intelligence" / "main.py").read_text(encoding="utf-8")
    assert "import spaces" in source
    assert "@spaces.GPU" in source
    assert "def _zero_gpu_startup_probe" in source


def test_wealth_requirements_pin_the_spaces_package():
    requirements = (ROOT / "requirements_wealth_intelligence.txt").read_text(encoding="utf-8")
    assert "spaces==" in requirements
