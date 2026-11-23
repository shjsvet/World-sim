"""Летопись мира поверх бинарного дерева поиска."""

from __future__ import annotations

import json
from typing import Any

from worldsim.core.events import Event, EventType
from worldsim.core.tree import BinarySearchTree


class Chronicle:
    """Хронологический журнал событий с мгновенным доступом по году.

    Ключом BST служит год, поэтому события всегда хранятся в хронологическом
    порядке, а несколько событий одного года сохраняются как мультимножество.
    Летопись не зависит от UI и не изменяет снимок мира.
    """

    def __init__(self) -> None:
        self._tree: BinarySearchTree[int, Event] = BinarySearchTree()

    def __len__(self) -> int:
        """Возвращает число событий в летописи."""
        return self._tree.value_count

    def add(self, event: Event) -> None:
        """Добавляет событие в летопись.

        Args:
            event: Событие; ключом становится его год.
        """
        self._tree.insert(event.year, event)

    def events_for_year(self, year: int) -> tuple[Event, ...]:
        """Возвращает все события указанного года в порядке добавления."""
        return tuple(self._tree.get_all(year))

    def between(self, start: int, end: int, inclusive: bool = True) -> tuple[Event, ...]:
        """Возвращает события за диапазон лет.

        Args:
            start: Начальный год.
            end: Конечный год.
            inclusive: Включать ли границы диапазона.

        Returns:
            Кортеж событий по возрастанию года.
        """
        return tuple(event for _, event in self._tree.range_query(start, end, inclusive=inclusive))

    def all_events(self) -> tuple[Event, ...]:
        """Возвращает все события в хронологическом порядке."""
        return tuple(event for _, event in self._tree.items())

    def filter(
        self,
        type: EventType | None = None,
        faction_id: int | None = None,
        tile_id: int | None = None,
    ) -> tuple[Event, ...]:
        """Фильтрует события по типу, фракции и тайлу.

        Args:
            type: Тип события.
            faction_id: Идентификатор фракции среди участников.
            tile_id: Идентификатор тайла среди участников.

        Returns:
            Кортеж подходящих событий в хронологическом порядке.
        """
        result: list[Event] = []
        for event in self.all_events():
            if type is not None and event.type is not type:
                continue
            if faction_id is not None and faction_id not in event.faction_ids:
                continue
            if tile_id is not None and tile_id not in event.tile_ids:
                continue
            result.append(event)
        return tuple(result)

    def clear(self) -> None:
        """Удаляет все события."""
        self._tree.clear()

    def to_markdown(self) -> str:
        """Возвращает летопись в виде Markdown-таблицы.

        Символы ``|`` в описаниях экранируются, переводы строк заменяются
        пробелами, чтобы таблица не ломалась.
        """
        lines = ["| Год | Тип | Событие |", "|-----|-----|---------|"]
        for event in self.all_events():
            summary = event.summary.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {event.year} | {event.type.value} | {summary} |")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Сериализует летопись в JSON."""
        payload: dict[str, list[dict[str, Any]]] = {
            "events": [event.as_dict() for event in self.all_events()]
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> Chronicle:
        """Восстанавливает летопись из JSON, созданного :meth:`to_json`.

        Args:
            payload: JSON-строка с массивом событий.

        Returns:
            Новая летопись с событиями в исходном порядке.
        """
        data: Any = json.loads(payload)
        chronicle = cls()
        for raw_event in data["events"]:
            chronicle.add(Event.model_validate(raw_event))
        return chronicle
