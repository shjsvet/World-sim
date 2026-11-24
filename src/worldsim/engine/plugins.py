"""Загрузка правил-плагинов из entry points и каталогов ``plugins/``."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast

from worldsim.core.events import Event, EventType
from worldsim.core.state import WorldState
from worldsim.engine.rules import Rule, RuleOutcome, StepContext

ENTRY_POINT_GROUP = "worldsim.rules"


class PluginError(RuntimeError):
    """Ошибка загрузки или проверки плагина."""


@dataclass
class PluginRule:
    """Обёртка плагина: флаг ``enabled`` и изоляция падений."""

    inner: Rule
    enabled: bool = True

    @property
    def name(self) -> str:
        """Имя правила."""
        return self.inner.name

    @property
    def priority(self) -> int:
        """Приоритет правила."""
        return self.inner.priority

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Выполняет правило; падение отключает его и даёт ``CUSTOM``."""
        if not self.enabled:
            return RuleOutcome()
        try:
            return self.inner.apply(state, ctx)
        except Exception as exc:
            self.enabled = False
            event = Event(
                id=0,
                year=ctx.year,
                type=EventType.CUSTOM,
                summary=f"Правило {self.name} отключено: {type(exc).__name__}",
                severity=1.0,
            )
            return RuleOutcome(events=(event,))


def load_rules(sources: Sequence[str | Path] = ()) -> list[PluginRule]:
    """Загружает правила из entry points и указанных путей.

    Args:
        sources: Файлы ``*_rule.py`` или каталоги с ними.

    Raises:
        PluginError: Если правило не соответствует ``Rule``, имя повторяется
            или модуль не загружается.
    """
    loaded: list[PluginRule] = []
    names: set[str] = set()

    for entry_point in _entry_points():
        try:
            candidate = entry_point.load()
        except Exception as exc:
            raise PluginError(
                f"не удалось загрузить entry point {entry_point.name}: {exc}"
            ) from exc
        _add(
            loaded,
            names,
            _normalize(candidate, f"entry point {entry_point.name}"),
            f"entry point {entry_point.name}",
        )

    for source in sources:
        path = Path(source)
        files = sorted(path.glob("*_rule.py")) if path.is_dir() else [path]
        if not files:
            raise PluginError(f"в {path} не найдено правил *_rule.py")
        for file in files:
            module = _load_module(file)
            for rule in _module_rules(module, str(file)):
                _add(loaded, names, rule, str(file))

    return sorted(loaded, key=lambda rule: (rule.priority, rule.name))


def _entry_points() -> Iterable[importlib.metadata.EntryPoint]:
    """Возвращает entry points группы ``worldsim.rules``."""
    return importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)


def _add(
    loaded: list[PluginRule],
    names: set[str],
    rule: Rule,
    origin: str,
) -> None:
    """Добавляет правило с проверкой уникальности имени."""
    if rule.name in names:
        raise PluginError(f"конфликт имён правил: {rule.name} ({origin})")
    names.add(rule.name)
    loaded.append(PluginRule(inner=rule, enabled=getattr(rule, "enabled", True)))


def _normalize(candidate: object, origin: str) -> Rule:
    """Превращает класс или экземпляр в правило."""
    instance: object = candidate
    if isinstance(candidate, type):
        try:
            instance = candidate()
        except Exception as exc:
            raise PluginError(f"не удалось создать правило из {origin}: {exc}") from exc
    if not _is_rule(instance):
        raise PluginError(f"{origin} не реализует Rule")
    return cast(Rule, instance)


def _is_rule(candidate: object) -> bool:
    """Проверяет структурное соответствие ``Rule``."""
    name = getattr(candidate, "name", None)
    priority = getattr(candidate, "priority", None)
    apply_method = getattr(candidate, "apply", None)
    return (
        isinstance(name, str)
        and name != ""
        and isinstance(priority, int)
        and callable(apply_method)
    )


def _load_module(path: Path) -> ModuleType:
    """Загружает модуль плагина по пути."""
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:10]
    name = f"worldsim_plugin_{path.stem}_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PluginError(f"не удалось создать модуль для {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise PluginError(f"не удалось загрузить {path}: {exc}") from exc
    return module


def _module_rules(module: ModuleType, origin: str) -> list[Rule]:
    """Достаёт правила из модуля: ``RULES``, ``RULE`` или классы."""
    rules_attr = getattr(module, "RULES", None)
    rule_attr = getattr(module, "RULE", None)
    if rules_attr is not None:
        candidates = list(rules_attr)
    elif rule_attr is not None:
        candidates = [rule_attr]
    else:
        candidates = [
            value
            for value in vars(module).values()
            if isinstance(value, type) and value.__module__ == module.__name__ and _is_rule(value)
        ]
    if not candidates:
        raise PluginError(f"в {origin} нет правил")
    return [_normalize(candidate, origin) for candidate in candidates]
