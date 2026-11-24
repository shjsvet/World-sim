"""Движок симуляции: применение правил и шаг времени."""

from __future__ import annotations

from collections.abc import Sequence

from worldsim.ai.ruler import RulerDecision
from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.geography import RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.rulers import DiplomaticMessage, RulerThought
from worldsim.core.state import WorldState
from worldsim.engine.metrics import compute_faction_stats
from worldsim.engine.rules import (
    AICommand,
    FactionUpdate,
    Rule,
    RuleOutcome,
    StepContext,
)


class SimulationEngine:
    """Выполняет правила над иммутабельными снимками мира.

    Правила сортируются по ``priority`` (затем по имени) и получают уже
    обновлённый снимок. Каждый шаг создаёт новый ``WorldState`` и увеличивает
    год на единицу; события складываются в летопись.
    """

    def __init__(
        self,
        rules: Sequence[Rule],
        chronicle: Chronicle,
        initial_state: WorldState | None = None,
    ) -> None:
        """Создаёт движок.

        Args:
            rules: Правила симуляции.
            chronicle: Летопись, куда попадают события.
            initial_state: Необязательный стартовый снимок мира.
        """
        self._rules: tuple[Rule, ...] = tuple(
            sorted(rules, key=lambda rule: (rule.priority, rule.name))
        )
        self._chronicle = chronicle
        self._state = initial_state
        self._rng = Rng(initial_state.config.seed) if initial_state is not None else None
        self._pending_ai_decisions: list[AICommand] = []

    @property
    def state(self) -> WorldState:
        """Текущий снимок мира.

        Raises:
            RuntimeError: Если снимок ещё не установлен.
        """
        if self._state is None:
            raise RuntimeError("снимок мира не установлен: передайте initial_state или reset()")
        return self._state

    @property
    def chronicle(self) -> Chronicle:
        """Летопись движка."""
        return self._chronicle

    @property
    def rules(self) -> tuple[Rule, ...]:
        """Подключённые правила в порядке применения."""
        return self._rules

    @property
    def pending_ai_decisions(self) -> tuple[AICommand, ...]:
        """Решения ИИ, ожидающие следующего шага."""
        return tuple(self._pending_ai_decisions)

    def queue_decision(self, faction_id: int, decision: RulerDecision) -> None:
        """Ставит одно решение ИИ в очередь следующего шага."""
        self._pending_ai_decisions.append(AICommand(faction_id=faction_id, decision=decision))

    def queue_decisions(self, commands: Sequence[AICommand]) -> None:
        """Ставит несколько решений ИИ в очередь следующего шага."""
        self._pending_ai_decisions.extend(commands)

    def record_thoughts(self, thoughts: Sequence[RulerThought]) -> WorldState:
        """Добавляет мысли правителей в текущий снимок без шага времени."""
        if not thoughts:
            return self.state
        self._state = self.state.model_copy(update={"thoughts": (*self.state.thoughts, *thoughts)})
        return self._state

    def record_messages(self, messages: Sequence[DiplomaticMessage]) -> WorldState:
        """Добавляет дипломатические сообщения в текущий снимок."""
        if not messages:
            return self.state
        self._state = self.state.model_copy(
            update={
                "diplomatic_messages": (
                    *self.state.diplomatic_messages,
                    *messages,
                )
            }
        )
        return self._state

    def reset(self, state: WorldState) -> None:
        """Устанавливает новый снимок и пересоздаёт генератор по его сиду."""
        self._state = state
        self._rng = Rng(state.config.seed)

    def step(self) -> WorldState:
        """Выполняет один шаг симуляции (один год).

        Returns:
            Новый снимок мира с увеличенным годом.
        """
        if self._state is None or self._rng is None:
            raise RuntimeError("снимок мира не установлен: передайте initial_state или reset()")

        state = self._state
        commands = self._pending_ai_decisions
        self._pending_ai_decisions = []
        ctx = StepContext(
            year=state.year,
            config=state.config,
            rng=self._rng,
            stats=compute_faction_stats(state),
            ai_decisions=commands,
        )

        for rule in self._rules:
            outcome = rule.apply(state, ctx)
            state = self._apply(state, outcome)
            for event in outcome.events:
                self._add_event(event)

        self._state = state.model_copy(update={"year": state.year + 1})
        return self._state

    def run(self, years: int) -> WorldState:
        """Выполняет несколько шагов подряд.

        Args:
            years: Количество лет (не может быть отрицательным).

        Returns:
            Снимок после последнего шага.

        Raises:
            ValueError: Если ``years`` отрицательный.
        """
        if years < 0:
            raise ValueError("количество лет не может быть отрицательным")
        for _ in range(years):
            self.step()
        return self.state

    def _apply(self, state: WorldState, outcome: RuleOutcome) -> WorldState:
        """Применяет изменения правила к снимку мира.

        Внутри шага используется быстрый ``model_copy``: правила формируют
        изменения уже провалидированных полей, а публичные границы
        (``initial_state``, ``reset``, JSON) валидируются отдельно.
        """
        if outcome.faction_updates:
            state = self._apply_faction_updates(state, outcome.faction_updates)
        if outcome.wars is not None:
            state = state.model_copy(update={"wars": outcome.wars})
        if outcome.trade_routes is not None:
            state = state.model_copy(update={"trade_routes": outcome.trade_routes})
        if outcome.academies is not None:
            state = state.model_copy(update={"academies": outcome.academies})
        if outcome.diplomatic_messages is not None:
            state = state.model_copy(update={"diplomatic_messages": outcome.diplomatic_messages})
        if outcome.standing_orders is not None:
            state = state.model_copy(update={"standing_orders": outcome.standing_orders})
        if outcome.religions is not None:
            state = state.model_copy(update={"religions": outcome.religions})
        if outcome.army_marches is not None:
            state = state.model_copy(update={"army_marches": outcome.army_marches})
        if not outcome.tile_updates:
            return state

        tiles = list(state.map.tiles)
        for update in outcome.tile_updates:
            if not 0 <= update.tile_id < len(tiles):
                raise ValueError(f"тайл #{update.tile_id} вне карты")
            changes: dict[str, object] = {}
            if update.population is not None:
                changes["population"] = update.population
            if update.population_capacity is not None:
                changes["population_capacity"] = update.population_capacity
            if update.fertility is not None:
                changes["fertility"] = update.fertility
            if update.happiness is not None:
                changes["happiness"] = update.happiness
            if update.unrest is not None:
                changes["unrest"] = update.unrest
            if update.fortification is not None:
                changes["fortification"] = update.fortification
            if update.army_presence is not None:
                changes["army_presence"] = update.army_presence
            if update.urbanization is not None:
                changes["urbanization"] = update.urbanization
            if update.culture is not None:
                changes["culture"] = update.culture
            if update.culture_id is not None:
                changes["culture_id"] = update.culture_id
            if update.religion_id is not None:
                changes["religion_id"] = update.religion_id
            if update.assimilation is not None:
                changes["assimilation"] = update.assimilation
            if update.cultural_tension is not None:
                changes["cultural_tension"] = update.cultural_tension
            if update.resource_depletion is not None:
                changes["resource_depletion"] = update.resource_depletion
            if update.set_owner:
                changes["owner_id"] = update.owner_id
            tile = tiles[update.tile_id]
            if not _changes_valid(changes):
                RegionData.model_validate({**tile.__dict__, **changes})
            tiles[update.tile_id] = _copy_tile(tile, changes)

        world_map = WorldMap.model_construct(size=state.map.size, tiles=tuple(tiles))
        return state.model_copy(update={"map": world_map})

    def _apply_faction_updates(
        self,
        state: WorldState,
        updates: tuple[FactionUpdate, ...],
    ) -> WorldState:
        """Применяет изменения фракций через ``Faction.evolve``."""
        factions = list(state.factions)
        positions = {faction.id: index for index, faction in enumerate(factions)}
        for update in updates:
            position = positions.get(update.faction_id)
            if position is None:
                raise ValueError(f"фракция #{update.faction_id} отсутствует в снимке")
            factions[position] = factions[position].evolve(**dict(update.changes))
        return state.model_copy(update={"factions": tuple(factions)})

    def _add_event(self, event: Event) -> None:
        """Добавляет событие в летопись, выдавая уникальный идентификатор."""
        event_id = len(self._chronicle)
        self._chronicle.add(event.model_copy(update={"id": event_id}))


def _copy_tile(tile: RegionData, changes: dict[str, object]) -> RegionData:
    """Быстрая копия тайла с изменениями без повторной валидации.

    Внутри шага поля уже проверены правилами; копирование через
    ``__dict__`` экономит время на массовых обновлениях карты.
    """
    new = object.__new__(RegionData)
    new.__dict__ = {**tile.__dict__, **changes}
    fields_set: set[str] = set(getattr(tile, "__pydantic_fields_set__", set()))
    object.__setattr__(new, "__pydantic_extra__", None)
    object.__setattr__(
        new,
        "__pydantic_fields_set__",
        fields_set | set(changes),
    )
    object.__setattr__(new, "__pydantic_private__", None)
    return new


def _changes_valid(changes: dict[str, object]) -> bool:
    """Проверяет диапазоны изменяемых полей без полной валидации модели."""
    for name, value in changes.items():
        if name in {"population", "population_capacity", "army_presence"}:
            if not isinstance(value, int) or value < 0:
                return False
        elif name in {
            "fertility",
            "happiness",
            "unrest",
            "fortification",
            "urbanization",
            "cultural_tension",
        }:
            if not isinstance(value, (int, float)) or not 0.0 <= value <= 100.0:
                return False
        elif name == "assimilation":
            if not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                return False
        elif name == "resource_depletion":
            if not isinstance(value, (int, float)) or value < 0.0:
                return False
        elif (
            name in {"owner_id", "culture_id", "religion_id"}
            and value is not None
            and (not isinstance(value, int) or value < 0)
        ):
            return False
    return True
