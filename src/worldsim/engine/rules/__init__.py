"""Контракты правил симуляции: контекст шага, изменения и результат."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from worldsim.ai.ruler import RulerDecision
from worldsim.core.diplomacy import War
from worldsim.core.events import Event
from worldsim.core.magic import MagicAcademy
from worldsim.core.resources import TradeRoute
from worldsim.core.rng import Rng
from worldsim.core.rulers import DiplomaticMessage
from worldsim.core.state import WorldConfig, WorldState

if TYPE_CHECKING:
    from worldsim.engine.metrics import FactionStats


@dataclass(frozen=True)
class TileUpdate:
    """Изменения одного тайла, которые правило просит применить.

    Attributes:
        tile_id: Идентификатор тайла.
        population: Новое население; ``None`` — не менять.
        population_capacity: Новая ёмкость; ``None`` — не менять.
        fertility: Новое плодородие; ``None`` — не менять.
        owner_id: Новый владелец (используется вместе с ``set_owner``).
        set_owner: Явно ли менять владельца (позволяет выставить ``None``).
        happiness: Новое счастье; ``None`` — не менять.
        unrest: Новое недовольство; ``None`` — не менять.
        fortification: Новая фортификация; ``None`` — не менять.
        army_presence: Новый гарнизон; ``None`` — не менять.
        urbanization: Новый уровень урбанизации; ``None`` — не менять.
        culture: Название культуры населения; ``None`` — не менять.
        culture_id: Идентификатор культуры; ``None`` — не менять.
        religion_id: Идентификатор религии; ``None`` — не менять.
        assimilation: Уровень ассимиляции; ``None`` — не менять.
        cultural_tension: Культурное напряжение; ``None`` — не менять.
        resource_depletion: Остаток ресурса в земле; ``None`` — не менять.
    """

    tile_id: int
    population: int | None = None
    population_capacity: int | None = None
    fertility: float | None = None
    owner_id: int | None = None
    set_owner: bool = False
    happiness: float | None = None
    unrest: float | None = None
    fortification: float | None = None
    army_presence: int | None = None
    urbanization: float | None = None
    culture: str | None = None
    culture_id: int | None = None
    religion_id: int | None = None
    assimilation: float | None = None
    cultural_tension: float | None = None
    resource_depletion: float | None = None


@dataclass(frozen=True)
class FactionUpdate:
    """Изменения полей фракции.

    Движок применяет их начиная с T17, когда у снимка мира появляются фракции.
    """

    faction_id: int
    changes: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BattleRequest:
    """Заявка на бой, которую экспансия передаёт правилу войны."""

    attacker_id: int
    defender_id: int
    tile_id: int


@dataclass(frozen=True)
class MagicBoost:
    """Результат боевой магии для одной заявки на бой."""

    attacker_id: int
    defender_id: int
    tile_id: int
    mana_spent: int
    magic_bonus: float
    school_modifier: float


@dataclass(frozen=True)
class AICommand:
    """Решение ИИ-правителя, привязанное к фракции."""

    faction_id: int
    decision: RulerDecision


@dataclass(frozen=True)
class StepContext:
    """Контекст одного шага симуляции, доступный правилам."""

    year: int
    config: WorldConfig
    rng: Rng
    stats: Mapping[int, FactionStats] = field(default_factory=dict)
    pending_battles: list[BattleRequest] = field(default_factory=list)
    magic_boosts: list[MagicBoost] = field(default_factory=list)
    ai_decisions: list[AICommand] = field(default_factory=list)


@dataclass(frozen=True)
class RuleOutcome:
    """Результат работы правила: изменения и события."""

    tile_updates: tuple[TileUpdate, ...] = ()
    faction_updates: tuple[FactionUpdate, ...] = ()
    events: tuple[Event, ...] = ()
    wars: tuple[War, ...] | None = None
    trade_routes: tuple[TradeRoute, ...] | None = None
    academies: tuple[MagicAcademy, ...] | None = None
    diplomatic_messages: tuple[DiplomaticMessage, ...] | None = None


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
