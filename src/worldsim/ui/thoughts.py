"""Подготовка дневников правителей для интерфейса."""

from __future__ import annotations

from collections.abc import Iterable

from worldsim.core.faction import Faction
from worldsim.core.rulers import RulerThought

_ACTION_LABELS = {
    "build_academy": "Строительство академии",
    "recruit": "Набор армии",
    "extract_resource": "Добыча ресурсов",
    "redistribute_population": "Переселение",
    "propose_peace": "Предложение мира",
    "offer_trade": "Торговое предложение",
    "move_army": "Поход армии",
    "found_religion": "Новая религия",
    "hold": "Бездействие",
}


def action_label(action: str) -> str:
    """Человекочитаемое название действия."""
    return _ACTION_LABELS.get(action, action or "Бездействие")


def thoughts_by_faction(
    thoughts: Iterable[RulerThought],
    factions: Iterable[Faction],
) -> dict[int, tuple[RulerThought, ...]]:
    """Группирует мысли по фракциям, сортируя по году и id."""
    ordered = sorted(thoughts, key=lambda thought: (thought.year, thought.id))
    return {
        faction.id: tuple(thought for thought in ordered if thought.faction_id == faction.id)
        for faction in factions
    }


def format_thought(thought: RulerThought, faction_name: str) -> str:
    """Форматирует одну мысль для markdown/UI."""
    return (
        f"**Год {thought.year} · {faction_name}**\n\n"
        f"**Действие:** {action_label(thought.action)}\n\n"
        f"{thought.text}"
    )


def thoughts_to_markdown(
    thoughts: Iterable[RulerThought],
    factions: Iterable[Faction],
) -> str:
    """Собирает markdown-дневник по фракциям."""
    names = {faction.id: faction.name for faction in factions}
    grouped = thoughts_by_faction(thoughts, factions)
    lines = ["# Мысли правителей", ""]
    for faction_id, entries in grouped.items():
        if not entries:
            continue
        lines.append(f"## {names[faction_id]}")
        lines.append("")
        for thought in entries:
            lines.append(f"### Год {thought.year} — {action_label(thought.action)}")
            lines.append("")
            lines.append(thought.text)
            lines.append("")
    if len(lines) == 2:
        lines.append("_Мыслей пока нет._")
        lines.append("")
    return "\n".join(lines)
