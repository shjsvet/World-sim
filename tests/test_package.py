"""Смоук-тесты каркаса пакета и точки входа приложения."""

from __future__ import annotations

import importlib
import sys
import types

import pytest

import worldsim
from worldsim.launcher import app_script, build_streamlit_argv, main

SUBPACKAGES = [
    "worldsim.core",
    "worldsim.generator",
    "worldsim.engine",
    "worldsim.vcs",
    "worldsim.ai",
    "worldsim.ui",
]


def test_version_is_semver() -> None:
    """Версия пакета — строка вида MAJOR.MINOR.PATCH."""
    assert isinstance(worldsim.__version__, str)
    parts = worldsim.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.parametrize("module_name", SUBPACKAGES)
def test_subpackage_importable(module_name: str) -> None:
    """Каждый подпакет импортируется и имеет docstring."""
    module = importlib.import_module(module_name)
    assert module.__doc__


def test_launcher_builds_streamlit_argv() -> None:
    """Точка входа собирает команду ``streamlit run <app>`` и пробрасывает флаги."""
    argv = build_streamlit_argv(["--server.port", "8600"])
    assert argv[:2] == ["streamlit", "run"]
    assert argv[2].endswith("app.py")
    assert argv[3:] == ["--server.port", "8600"]


def test_app_script_exists() -> None:
    """Streamlit-скрипт приложения существует внутри пакета."""
    assert app_script().is_file()


def test_main_runs_streamlit_with_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main`` запускает Streamlit с переданными аргументами и возвращает код выхода."""
    calls: dict[str, list[str]] = {}

    fake_cli = types.ModuleType("streamlit.web.cli")

    def fake_main() -> None:
        calls["argv"] = sys.argv[:]
        raise SystemExit(3)

    fake_cli.main = fake_main  # type: ignore[attr-defined]
    fake_web = types.ModuleType("streamlit.web")
    fake_web.cli = fake_cli  # type: ignore[attr-defined]
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.web = fake_web  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setitem(sys.modules, "streamlit.web", fake_web)
    monkeypatch.setitem(sys.modules, "streamlit.web.cli", fake_cli)

    original_argv = sys.argv[:]
    try:
        exit_code = main(["--server.headless", "true"])
    finally:
        sys.argv = original_argv

    assert exit_code == 3
    assert calls["argv"][:2] == ["streamlit", "run"]
    assert calls["argv"][3:] == ["--server.headless", "true"]
