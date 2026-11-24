"""Тесты хелперов дневников правителей."""

from __future__ import annotations

from worldsim.core.faction import Faction, Ideology
from worldsim.core.rulers import RulerThought
from worldsim.ui.thoughts import (
    action_label,
    format_thought,
    thoughts_by_faction,
    thoughts_to_markdown,
)


def make_faction(faction_id: int, name: str) -> Faction:
    """Создаёт фракцию для тестов."""
    return Faction(
        id=faction_id,
        name=name,
        color="#112233",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=faction_id,
    )


def make_thought(
    thought_id: int,
    faction_id: int,
    year: int,
    *,
    action: str = "hold",
    text: str = "Мысль.",
) -> RulerThought:
    """Создаёт мысль для тестов."""
    return RulerThought(
        id=thought_id,
        faction_id=faction_id,
        year=year,
        text=text,
        action=action,
    )


def test_thoughts_grouped_and_sorted() -> None:
    """Мысли группируются по фракциям и сортируются по году."""
    factions = (make_faction(0, "Альянс"), make_faction(1, "Орда"))
    thoughts = (
        make_thought(2, 0, 5),
        make_thought(0, 1, 2),
        make_thought(1, 0, 1),
    )

    grouped = thoughts_by_faction(thoughts, factions)

    assert [thought.id for thought in grouped[0]] == [1, 2]
    assert [thought.id for thought in grouped[1]] == [0]


def test_empty_grouping() -> None:
    """Без мыслей группы пустые."""
    factions = (make_faction(0, "Альянс"),)

    grouped = thoughts_by_faction((), factions)

    assert grouped == {0: ()}


def test_format_thought_contains_fields() -> None:
    """Формат содержит год, фракцию, действие и текст."""
    thought = make_thought(
        0,
        0,
        7,
        action="build_academy",
        text="Пора учить магов.",
    )

    text = format_thought(thought, "Альянс")

    assert "Год 7" in text
    assert "Альянс" in text
    assert "академи" in text
    assert "Пора учить магов." in text


def test_format_unknown_action() -> None:
    """Неизвестное действие выводится как есть."""
    thought = make_thought(0, 0, 0, action="unknown_action")

    assert "unknown_action" in format_thought(thought, "Альянс")
    assert action_label("hold") == "Бездействие"


def test_markdown_contains_faction_sections() -> None:
    """Markdown-дневник содержит секции фракций и мысли."""
    factions = (make_faction(0, "Альянс"), make_faction(1, "Орда"))
    thoughts = (
        make_thought(0, 0, 1, action="recruit", text="Наберу солдат."),
        make_thought(1, 1, 1, action="hold", text="Подожду."),
    )

    text = thoughts_to_markdown(thoughts, factions)

    assert "# Мысли правителей" in text
    assert "## Альянс" in text
    assert "## Орда" in text
    assert "Наберу солдат." in text
    assert "Подожду." in text


def test_markdown_empty() -> None:
    """Пустой дневник содержит пояснение."""
    text = thoughts_to_markdown((), (make_faction(0, "Альянс"),))

    assert "Мыслей пока нет" in text
