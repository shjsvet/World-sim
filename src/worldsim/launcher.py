"""Точка входа приложения WorldSim.

Модуль запускает веб-интерфейс на Streamlit и передаёт ему аргументы
командной строки. Используется консольной командой ``worldsim``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_script() -> Path:
    """Возвращает путь к Streamlit-скрипту приложения.

    Returns:
        Путь к ``worldsim/ui/app.py`` внутри установленного пакета.
    """
    return Path(__file__).resolve().parent / "ui" / "app.py"


def build_streamlit_argv(args: list[str]) -> list[str]:
    """Собирает аргументы командной строки для Streamlit.

    Args:
        args: дополнительные аргументы, переданные пользователем.

    Returns:
        Список вида ``["streamlit", "run", "<app>", *args]``.
    """
    return ["streamlit", "run", str(app_script()), *args]


def main(argv: list[str] | None = None) -> int:
    """Запускает веб-приложение WorldSim.

    Args:
        argv: аргументы без имени программы; по умолчанию ``sys.argv[1:]``.

    Returns:
        Код возврата процесса.
    """
    from streamlit.web import cli as streamlit_cli

    sys.argv = build_streamlit_argv(list(sys.argv[1:] if argv is None else argv))
    try:
        streamlit_cli.main()
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0
