"""Проверка относительных ссылок, якорей и docstring'ов в документации.

Запуск: ``python scripts/check_docs.py``. Код возврата 1 при ошибках.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tmp",
    ".worldsim",
    "worlds",
    "htmlcov",
    "node_modules",
}
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*```")


def iter_markdown() -> list[Path]:
    """Находит Markdown-файлы проекта, кроме служебных каталогов."""
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*.md")):
        if any(part in SKIP_DIRS or part.startswith("pytest-of-") for part in path.parts):
            continue
        files.append(path)
    return files


def slugify(text: str) -> str:
    """Превращает заголовок в GitHub-якорь."""
    value = text.strip().lower()
    value = value.replace("`", "")
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "-", value)
    return value


def anchors_for(path: Path) -> set[str]:
    """Собирает якоря заголовков файла (с учётом дублей)."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match is None:
            continue
        base = slugify(match.group(2))
        index = counts.get(base, 0)
        counts[base] = index + 1
        anchors.add(base if index == 0 else f"{base}-{index}")
    return anchors


def resolve(source: Path, target: str) -> tuple[Path, str]:
    """Разбирает ссылку на путь и якорь."""
    raw = target.strip().strip("<>").split('"')[0].strip()
    path_part, _, anchor = raw.partition("#")
    path_part = unquote(path_part)
    if not path_part:
        return source, anchor
    return (source.parent / path_part).resolve(), anchor


def check_links(path: Path) -> list[str]:
    """Проверяет ссылки одного Markdown-файла."""
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_fence = False
    anchor_cache: dict[Path, set[str]] = {}

    for number, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        cleaned = re.sub(r"`[^`]*`", "", line)
        for match in LINK_RE.finditer(cleaned):
            destination = match.group(1).strip()
            if destination.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            if destination.startswith("#"):
                target_path, anchor = path, destination[1:]
            else:
                target_path, anchor = resolve(path, destination)
            if not target_path.exists():
                errors.append(
                    f"{path.relative_to(ROOT)}:{number}: ссылка не найдена: {destination}"
                )
                continue
            if not anchor or target_path.is_dir() or target_path.suffix != ".md":
                continue
            if anchor.startswith("L") and anchor[1:].isdigit():
                continue
            if target_path not in anchor_cache:
                anchor_cache[target_path] = anchors_for(target_path)
            if anchor not in anchor_cache[target_path]:
                errors.append(f"{path.relative_to(ROOT)}:{number}: якорь не найден: {destination}")
    return errors


def check_module_docstrings() -> list[str]:
    """Проверяет наличие docstring у публичных модулей."""
    errors: list[str] = []
    for path in sorted((ROOT / "src" / "worldsim").rglob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if ast.get_docstring(tree) is None:
            errors.append(f"{path.relative_to(ROOT)}: отсутствует docstring модуля")
    return errors


def main() -> int:
    """Запускает все проверки."""
    errors: list[str] = []
    for path in iter_markdown():
        errors.extend(check_links(path))
    errors.extend(check_module_docstrings())
    if errors:
        for error in errors:
            print(error)
        print(f"Проверка документации: ошибок {len(errors)}")
        return 1
    print("Проверка документации: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
