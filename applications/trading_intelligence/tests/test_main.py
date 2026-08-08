"""Tests for applications.trading_intelligence.main.main().

Uses fake application objects throughout -- no real bootstrap.build_application()
call and no real Gradio server launch -- since main() only orchestrates two
calls (build_application(), then .build().launch() on the result) and this
test verifies exactly that orchestration, not bootstrap.py or Gradio itself.
"""
import ast
import pathlib

import applications.trading_intelligence.main as main_module

_MAIN_FILE = pathlib.Path(main_module.__file__).resolve()


class _FakeBlocks:
    def __init__(self):
        self.launch_calls = 0

    def launch(self):
        self.launch_calls += 1


class _FakeDecisionCenterUI:
    def __init__(self):
        self.build_calls = 0
        self.blocks = _FakeBlocks()

    def build(self):
        self.build_calls += 1
        return self.blocks


def test_main_calls_build_application(monkeypatch):
    fake_ui = _FakeDecisionCenterUI()
    build_application_calls = []

    def fake_build_application():
        build_application_calls.append(1)
        return fake_ui

    monkeypatch.setattr(main_module, "build_application", fake_build_application)

    main_module.main()

    assert len(build_application_calls) == 1


def test_main_launches_the_ui_built_from_build_application(monkeypatch):
    fake_ui = _FakeDecisionCenterUI()
    monkeypatch.setattr(main_module, "build_application", lambda: fake_ui)

    main_module.main()

    assert fake_ui.build_calls == 1
    assert fake_ui.blocks.launch_calls == 1


def test_main_imports_only_bootstrap():
    source = _MAIN_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_MAIN_FILE))

    forbidden_prefixes = (
        "sentinel_engine.repositories",
        "sentinel_engine.services",
        "sentinel_engine.events",
        "dashboard",
        "bot",
        "database",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden_prefixes), (
                    f"forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden_prefixes), (
                f"forbidden import from {module!r}"
            )
            assert module == "applications.trading_intelligence.bootstrap", (
                f"unexpected import from {module!r}; main.py should only import "
                "applications.trading_intelligence.bootstrap"
            )
