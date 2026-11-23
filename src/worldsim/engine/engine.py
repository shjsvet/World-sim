"""Движок симуляции: применение правил и шаг времени."""

from __future__ import annotations

from collections.abc import Sequence

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.geography import RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldState
from worldsim.engine.rules import Rule, RuleOutcome, StepContext


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
        ctx = StepContext(year=state.year, config=state.config, rng=self._rng)

        for rule in self._rules:
            outcome = rule.apply(state, ctx)
            state = self._apply(state, outcome)
            for event in outcome.events:
                self._add_event(event)

        self._state = state.evolve(year=state.year + 1)
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
        """Применяет изменения правила к снимку мира."""
        if outcome.faction_updates:
            raise NotImplementedError(
                "обновления фракций появятся в T17 вместе с WorldState.factions"
            )
        if not outcome.tile_updates:
            return state

        tiles = list(state.map.tiles)
        for update in outcome.tile_updates:
            if not 0 <= update.tile_id < len(tiles):
                raise ValueError(f"тайл #{update.tile_id} вне карты")
            tile = tiles[update.tile_id]
            data = tile.model_dump()
            if update.population is not None:
                data["population"] = update.population
            if update.set_owner:
                data["owner_id"] = update.owner_id
            tiles[update.tile_id] = RegionData.model_validate(data)

        world_map = WorldMap(size=state.map.size, tiles=tuple(tiles))
        return state.evolve(map=world_map)

    def _add_event(self, event: Event) -> None:
        """Добавляет событие в летопись, выдавая уникальный идентификатор."""
        event_id = len(self._chronicle)
        self._chronicle.add(event.model_copy(update={"id": event_id}))
