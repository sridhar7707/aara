"""Keeps each HF Space's Gradio pin, its Space metadata, and its CI interpreter in step.

A Space runs the Gradio version in its requirements file, but Hugging Face also reads
sdk_version and python_version from the README the deploy workflow writes. If those drift
apart the Space builds against one Gradio/Python and the code was tested against another.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACES = {
    "trading_intelligence": ("requirements_trading_intelligence.txt", "deploy_trading_intelligence.yml"),
    "wealth_intelligence": ("requirements_wealth_intelligence.txt", "deploy_wealth_intelligence.yml"),
    "dashboard": ("requirements_space.txt", "deploy_ui.yml"),
}


def _gradio_pin(requirements: str) -> str:
    match = re.search(r"^gradio==([0-9.]+)\s*$", requirements, re.M)
    assert match, "requirements file must pin gradio with ==, not a range"
    return match.group(1)


def _space_metadata(workflow: str) -> tuple[str, str]:
    sdk = re.search(r'"sdk_version: ([0-9.]+)\\n"', workflow)
    py = re.search(r'"python_version: \\"([0-9.]+)\\"\\n"', workflow)
    assert sdk and py, "deploy workflow must write sdk_version and python_version"
    return sdk.group(1), py.group(1)


def _ci_python(workflow: str) -> str:
    match = re.search(r"python-version:\s*['\"]([0-9.]+)['\"]", workflow)
    assert match, "deploy workflow must set up Python"
    return match.group(1)


def test_each_space_metadata_matches_its_requirements_and_ci_interpreter():
    for name, (req_file, wf_file) in SPACES.items():
        requirements = (ROOT / req_file).read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / wf_file).read_text(encoding="utf-8")
        gradio = _gradio_pin(requirements)
        sdk, py = _space_metadata(workflow)
        assert sdk == gradio, f"{name}: Space sdk_version {sdk} != requirements gradio {gradio}"
        assert py == _ci_python(workflow), f"{name}: Space python_version {py} != CI interpreter"


def test_spaces_do_not_target_python_older_than_gradio_five_supports():
    # Gradio 5 requires Python >= 3.10; a Space still on 3.9 cannot take the pinned version.
    for name, (_, wf_file) in SPACES.items():
        workflow = (ROOT / ".github" / "workflows" / wf_file).read_text(encoding="utf-8")
        major, minor = (int(p) for p in _space_metadata(workflow)[1].split(".")[:2])
        assert (major, minor) >= (3, 10), f"{name}: Space python_version too old for Gradio 5"
