"""Тесты летописи."""

from __future__ import annotations

import json

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event, EventType


def make_event(
    event_id: int,
    year: int,
    event_type: EventType = EventType.CUSTOM,
    summary: str | None = None,
    **kwargs: object,
) -> Event:
    """Создаёт событие для тестов."""
    return Event(
        id=event_id,
        year=year,
        type=event_type,
        summary=summary or f"событие {event_id}",
        severity=0.0,
        **kwargs,  # type: ignore[arg-type]
    )


def test_empty_chronicle() -> None:
    """Пустая летопись корректно отвечает на запросы."""
    chronicle = Chronicle()

    assert len(chronicle) == 0
    assert chronicle.all_events() == ()
    assert chronicle.events_for_year(1) == ()
    assert chronicle.between(0, 10) == ()
    assert chronicle.filter() == ()
    assert chronicle.to_markdown().startswith("| Год | Тип | Событие |")


def test_events_are_chronological() -> None:
    """События хранятся по возрастанию года независимо от порядка добавления."""
    chronicle = Chronicle()
    chronicle.add(make_event(1, 3))
    chronicle.add(make_event(2, 1))
    chronicle.add(make_event(3, 2))

    assert [event.year for event in chronicle.all_events()] == [1, 2, 3]
    assert len(chronicle) == 3


def test_same_year_keeps_insertion_order() -> None:
    """Несколько событий одного года сохраняют порядок добавления."""
    chronicle = Chronicle()
    chronicle.add(make_event(1, 5, EventType.WAR, "первое"))
    chronicle.add(make_event(2, 5, EventType.WAR, "второе"))
    chronicle.add(make_event(3, 5, EventType.WAR, "третье"))

    assert len(chronicle) == 3
    assert [event.summary for event in chronicle.events_for_year(5)] == [
        "первое",
        "второе",
        "третье",
    ]


def test_between_boundaries() -> None:
    """Диапазон учитывает включаемые и исключаемые границы."""
    chronicle = Chronicle()
    for year in (1, 2, 3, 4):
        chronicle.add(make_event(year, year))

    assert [event.year for event in chronicle.between(2, 3)] == [2, 3]
    assert [event.year for event in chronicle.between(2, 4, inclusive=False)] == [3]
    assert chronicle.between(5, 6) == ()
    assert chronicle.between(4, 2) == ()


def test_filter_by_type_faction_and_tile() -> None:
    """Фильтры комбинируются и работают по участникам события."""
    chronicle = Chronicle()
    chronicle.add(make_event(1, 1, EventType.WAR, "война", faction_ids=(1, 2), tile_ids=(10,)))
    chronicle.add(make_event(2, 2, EventType.TRADE, "торговля", faction_ids=(1,), tile_ids=(11,)))
    chronicle.add(make_event(3, 3, EventType.WAR, "другая война", faction_ids=(2,), tile_ids=(10,)))

    assert [event.id for event in chronicle.filter(type=EventType.WAR)] == [1, 3]
    assert [event.id for event in chronicle.filter(faction_id=1)] == [1, 2]
    assert [event.id for event in chronicle.filter(tile_id=10)] == [1, 3]
    assert [event.id for event in chronicle.filter(type=EventType.WAR, tile_id=10)] == [1, 3]
    assert [event.id for event in chronicle.filter(type=EventType.TRADE, faction_id=2)] == []


def test_markdown_table_and_escaping() -> None:
    """Markdown-таблица экранирует трубы и не ломает строки."""
    chronicle = Chronicle()
    chronicle.add(make_event(1, 10, EventType.WAR, "битва | за мост"))
    chronicle.add(make_event(2, 11, EventType.CUSTOM, "строка\nс переводом"))

    lines = chronicle.to_markdown().splitlines()

    assert lines[0] == "| Год | Тип | Событие |"
    assert lines[1] == "|-----|-----|---------|"
    assert "битва \\| за мост" in lines[2]
    assert "\n" not in lines[3]
    assert len(lines) == 4


def test_clear() -> None:
    """``clear`` удаляет все события."""
    chronicle = Chronicle()
    chronicle.add(make_event(1, 1))

    chronicle.clear()

    assert len(chronicle) == 0
    assert chronicle.all_events() == ()


def test_json_round_trip() -> None:
    """Летопись переживает сериализацию в JSON и обратно."""
    chronicle = Chronicle()
    chronicle.add(make_event(1, 2, EventType.PLAGUE, "эпидемия", tile_ids=(1, 2)))
    chronicle.add(make_event(2, 2, EventType.WAR, "война", faction_ids=(1, 2)))
    chronicle.add(make_event(3, 1, EventType.TRADE, "торговля"))

    payload = chronicle.to_json()
    restored = Chronicle.from_json(payload)

    assert len(restored) == 3
    assert restored.all_events() == chronicle.all_events()
    assert [event.id for event in restored.all_events()] == [3, 1, 2]
    assert json.loads(payload)["events"][0]["type"] == "trade"


def test_large_chronicle() -> None:
    """5 000 событий добавляются и обходятся без падения."""
    chronicle = Chronicle()
    for index in range(5_000):
        chronicle.add(make_event(index, index % 1_000))

    assert len(chronicle) == 5_000
    assert len(chronicle.all_events()) == 5_000
    assert chronicle.all_events()[0].year == 0
    assert chronicle.all_events()[-1].year == 999
    assert len(chronicle.events_for_year(0)) == 5
