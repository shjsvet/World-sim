"""Тесты движка симуляции и правила роста населения."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext
from worldsim.engine.rules.population import PopulationGrowthRule


def make_state(
    *,
    size: int = 4,
    population: int = 10,
    capacity: int = 100,
    fertility: float = 50.0,
    biome: Biome = Biome.PLAINS,
    growth_rate: float = 0.02,
) -> WorldState:
    """Создаёт однородный мир для тестов движка."""
    tiles = tuple(
        RegionData(
            id=index,
            x=index % size,
            y=index // size,
            biome=biome,
            fertility=fertility,
            elevation=100.0,
            population=population,
            population_capacity=capacity,
        )
        for index in range(size * size)
    )
    config = WorldConfig(seed=42, size=size, growth_rate=growth_rate)
    return WorldState(config=config, year=0, map=WorldMap(size=size, tiles=tiles))


class RecordingRule:
    """Правило, которое запоминает порядок вызова."""

    def __init__(self, name: str, priority: int, log: list[str]) -> None:
        self.name = name
        self.priority = priority
        self._log = log

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        self._log.append(self.name)
        return RuleOutcome()


class FactionTouchingRule:
    """Правило, которое пытается менять фракцию (пока не поддерживается)."""

    name = "faction-touch"
    priority = 1

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        return RuleOutcome(faction_updates=(FactionUpdate(faction_id=1, changes={"morale": 0.5}),))


def test_step_increments_year_and_grows_population() -> None:
    """Шаг увеличивает год и население суши."""
    engine = SimulationEngine(
        [PopulationGrowthRule()],
        Chronicle(),
        initial_state=make_state(),
    )

    state = engine.step()

    assert state.year == 1
    assert all(tile.population == 11 for tile in state.map.tiles)


def test_previous_state_is_not_mutated() -> None:
    """Старый снимок не меняется после шага."""
    initial = make_state()
    before = initial.snapshot_hash()
    engine = SimulationEngine([PopulationGrowthRule()], Chronicle(), initial_state=initial)

    engine.step()

    assert initial.snapshot_hash() == before
    assert initial.year == 0
    assert engine.state.snapshot_hash() != before


def test_run_multiple_years() -> None:
    """``run`` выполняет заданное число шагов."""
    engine = SimulationEngine(
        [PopulationGrowthRule()],
        Chronicle(),
        initial_state=make_state(),
    )

    state = engine.run(5)

    assert state.year == 5
    assert state.map.tiles[0].population == 15


def test_rules_run_in_priority_order() -> None:
    """Правила выполняются по возрастанию priority."""
    log: list[str] = []
    rules = [
        RecordingRule("late", 30, log),
        RecordingRule("early", 10, log),
        RecordingRule("middle", 20, log),
    ]
    engine = SimulationEngine(rules, Chronicle(), initial_state=make_state())

    engine.step()

    assert log == ["early", "middle", "late"]


def test_rules_with_equal_priority_are_sorted_by_name() -> None:
    """При равном priority порядок определяется именем."""
    log: list[str] = []
    rules = [RecordingRule("b", 10, log), RecordingRule("a", 10, log)]
    engine = SimulationEngine(rules, Chronicle(), initial_state=make_state())

    engine.step()

    assert log == ["a", "b"]


def test_deterministic_runs() -> None:
    """Одинаковые правила и сид дают одинаковый мир и летопись."""

    def run_once() -> tuple[str, str]:
        chronicle = Chronicle()
        engine = SimulationEngine(
            [PopulationGrowthRule()],
            chronicle,
            initial_state=make_state(),
        )
        final = engine.run(10)
        return final.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()


def test_growth_stops_at_capacity() -> None:
    """Население не превышает ёмкость тайла."""
    engine = SimulationEngine(
        [PopulationGrowthRule()],
        Chronicle(),
        initial_state=make_state(population=100, capacity=100),
    )

    state = engine.step()

    assert state.map.tiles[0].population == 100


def test_zero_growth_rate_stops_growth() -> None:
    """При нулевом темпе роста население не меняется."""
    engine = SimulationEngine(
        [PopulationGrowthRule()],
        Chronicle(),
        initial_state=make_state(growth_rate=0.0),
    )

    state = engine.step()

    assert state.map.tiles[0].population == 10


def test_water_population_does_not_grow() -> None:
    """На воде население не растёт."""
    engine = SimulationEngine(
        [PopulationGrowthRule()],
        Chronicle(),
        initial_state=make_state(biome=Biome.OCEAN, population=0),
    )

    state = engine.step()

    assert all(tile.population == 0 for tile in state.map.tiles)


def test_overpopulation_emits_famine_and_caps_population() -> None:
    """Перенаселение даёт событие FAMINE и снижает население до ёмкости."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PopulationGrowthRule()],
        chronicle,
        initial_state=make_state(population=150, capacity=100),
    )

    engine.step()

    assert engine.state.map.tiles[0].population == 100
    events = chronicle.filter(type=EventType.FAMINE)
    assert len(events) == 16
    assert [event.id for event in events] == list(range(16))
    assert events[0].severity == pytest.approx(0.5)
    assert events[0].year == 0


def test_faction_updates_are_not_supported_yet() -> None:
    """Обновления фракций пока не поддерживаются движком."""
    engine = SimulationEngine(
        [FactionTouchingRule()],
        Chronicle(),
        initial_state=make_state(),
    )

    with pytest.raises(NotImplementedError):
        engine.step()


def test_step_requires_state() -> None:
    """Без стартового снимка шаг невозможен."""
    engine = SimulationEngine([PopulationGrowthRule()], Chronicle())

    with pytest.raises(RuntimeError):
        engine.step()


def test_run_rejects_negative_years() -> None:
    """Отрицательное число лет отклоняется."""
    engine = SimulationEngine([], Chronicle(), initial_state=make_state())

    with pytest.raises(ValueError):
        engine.run(-1)


def test_reset_sets_state() -> None:
    """``reset`` устанавливает новый снимок."""
    state = make_state()
    engine = SimulationEngine([], Chronicle())

    engine.reset(state)

    assert engine.state is state


def test_empty_rule_list_only_advances_year() -> None:
    """Без правил шаг только увеличивает год."""
    engine = SimulationEngine([], Chronicle(), initial_state=make_state())

    state = engine.step()

    assert state.year == 1
    assert state.map == make_state().map


def test_invalid_tile_update_is_rejected() -> None:
    """Некорректное изменение тайла отклоняется валидацией."""

    class BadRule:
        name = "bad"
        priority = 1

        def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
            from worldsim.engine.rules import TileUpdate

            return RuleOutcome(tile_updates=(TileUpdate(tile_id=0, population=-5),))

    engine = SimulationEngine([BadRule()], Chronicle(), initial_state=make_state())

    with pytest.raises(ValidationError, match="greater than or equal"):
        engine.step()
