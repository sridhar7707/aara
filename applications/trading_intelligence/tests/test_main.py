"""Tests for applications.trading_intelligence.main.main().

Uses a fake application object throughout -- no real
bootstrap.build_trading_intelligence_app() call and no real Gradio server
launch -- since main() only orchestrates one call
(build_trading_intelligence_app().launch()) and this test verifies exactly
that orchestration, not bootstrap.py or Gradio itself.
"""
import ast
import pathlib

import applications.trading_intelligence.main as main_module

_MAIN_FILE = pathlib.Path(main_module.__file__).resolve()


class _FakeApp:
    def __init__(self):
        self.launch_calls = 0

    def launch(self):
        self.launch_calls += 1


def test_main_calls_build_trading_intelligence_app(monkeypatch):
    fake_app = _FakeApp()
    build_calls = []

    def fake_build_trading_intelligence_app():
        build_calls.append(1)
        return fake_app

    monkeypatch.setattr(
        main_module, "build_trading_intelligence_app", fake_build_trading_intelligence_app,
    )

    main_module.main()

    assert len(build_calls) == 1


def test_main_launches_the_app_built_from_build_trading_intelligence_app(monkeypatch):
    fake_app = _FakeApp()
    monkeypatch.setattr(main_module, "build_trading_intelligence_app", lambda: fake_app)

    main_module.main()

    assert fake_app.launch_calls == 1


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
