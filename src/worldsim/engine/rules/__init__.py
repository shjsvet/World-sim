"""Контракты правил симуляции: контекст шага, изменения и результат."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from worldsim.core.events import Event
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState


@dataclass(frozen=True)
class TileUpdate:
    """Изменения одного тайла, которые правило просит применить.

    Attributes:
        tile_id: Идентификатор тайла.
        population: Новое население; ``None`` — не менять.
        owner_id: Новый владелец (используется вместе с ``set_owner``).
        set_owner: Явно ли менять владельца (позволяет выставить ``None``).
    """

    tile_id: int
    population: int | None = None
    owner_id: int | None = None
    set_owner: bool = False


@dataclass(frozen=True)
class FactionUpdate:
    """Изменения полей фракции.

    Движок применяет их начиная с T17, когда у снимка мира появляются фракции.
    """

    faction_id: int
    changes: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StepContext:
    """Контекст одного шага симуляции, доступный правилам."""

    year: int
    config: WorldConfig
    rng: Rng
    stats: Mapping[int, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleOutcome:
    """Результат работы правила: изменения и события."""

    tile_updates: tuple[TileUpdate, ...] = ()
    faction_updates: tuple[FactionUpdate, ...] = ()
    events: tuple[Event, ...] = ()


class Rule(Protocol):
    """Правило симуляции.

    Правила выполняются движком по возрастанию ``priority`` (при равенстве —
    по имени), каждое получает уже обновлённый снимок мира.
    """

    name: str
    priority: int

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Применяет правило к снимку и возвращает изменения."""
        ...
