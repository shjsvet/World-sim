"""Тесты случайных событий движка."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.engine.rules.random_events import FamineRule, PlagueRule


def make_state(
    *,
    size: int = 4,
    population: int = 10,
    capacity: int = 100,
    fertility: float = 50.0,
    biome: Biome = Biome.PLAINS,
    plague_chance: float = 0.0,
    growth_rate: float = 0.02,
) -> WorldState:
    """Создаёт однородный мир для тестов случайных событий."""
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
    config = WorldConfig(
        seed=42,
        size=size,
        plague_chance=plague_chance,
        growth_rate=growth_rate,
    )
    return WorldState(config=config, year=0, map=WorldMap(size=size, tiles=tiles))


def test_plague_disabled_produces_no_events() -> None:
    """При нулевой вероятности эпидемий не бывает."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PlagueRule()],
        chronicle,
        initial_state=make_state(plague_chance=0.0),
    )

    engine.run(20)

    assert chronicle.filter(type=EventType.PLAGUE) == ()


def test_plague_always_triggers_at_full_probability() -> None:
    """При вероятности 1 эпидемия случается в первый же год."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PlagueRule()],
        chronicle,
        initial_state=make_state(plague_chance=1.0),
    )

    engine.step()

    events = chronicle.filter(type=EventType.PLAGUE)
    assert 1 <= len(events) <= 3
    assert all(event.year == 0 for event in events)


def test_plague_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковую последовательность эпидемий."""

    def run_once() -> str:
        chronicle = Chronicle()
        engine = SimulationEngine(
            [PlagueRule()],
            chronicle,
            initial_state=make_state(plague_chance=0.7),
        )
        engine.run(10)
        return chronicle.to_json()

    assert run_once() == run_once()


def test_plague_reduces_population_without_going_negative() -> None:
    """Эпидемия уменьшает население, но не ниже нуля."""
    chronicle = Chronicle()
    state = make_state(population=1, plague_chance=1.0)
    engine = SimulationEngine([PlagueRule()], chronicle, initial_state=state)

    updated = engine.step()

    assert all(tile.population >= 0 for tile in updated.map.tiles)
    assert any(tile.population == 0 for tile in updated.map.tiles)


def test_plague_ignores_empty_water() -> None:
    """Без населённых тайлов эпидемия не создаёт событий."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PlagueRule()],
        chronicle,
        initial_state=make_state(biome=Biome.OCEAN, population=0, plague_chance=1.0),
    )

    engine.step()

    assert chronicle.filter(type=EventType.PLAGUE) == ()


def test_plague_severity_range() -> None:
    """Потери от эпидемии лежат в диапазоне 10–60 %."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PlagueRule()],
        chronicle,
        initial_state=make_state(plague_chance=1.0),
    )

    engine.run(5)

    for event in chronicle.filter(type=EventType.PLAGUE):
        assert 0.1 <= event.severity <= 0.6


def test_plague_events_have_correct_year() -> None:
    """События попадают в тот год, когда произошли."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PlagueRule()],
        chronicle,
        initial_state=make_state(plague_chance=1.0),
    )

    engine.run(3)

    assert {event.year for event in chronicle.filter(type=EventType.PLAGUE)} <= {0, 1, 2}


def test_famine_on_overpopulation() -> None:
    """Голод снижает население до ёмкости и истощает плодородие."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [FamineRule()],
        chronicle,
        initial_state=make_state(population=150, capacity=100, fertility=50.0),
    )

    engine.step()

    tile = engine.state.map.tiles[0]
    assert tile.population == 100
    assert tile.fertility < 50.0
    events = chronicle.filter(type=EventType.FAMINE)
    assert len(events) == 16
    assert events[0].severity == pytest.approx(0.5)
    assert events[0].year == 0


def test_famine_does_not_trigger_without_overpopulation() -> None:
    """Без перенаселения голода нет."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [FamineRule()],
        chronicle,
        initial_state=make_state(population=10, capacity=100),
    )

    engine.step()

    assert chronicle.filter(type=EventType.FAMINE) == ()


def test_famine_runs_before_population_growth() -> None:
    """Голод срабатывает раньше роста, поэтому событие не дублируется."""
    chronicle = Chronicle()
    engine = SimulationEngine(
        [PopulationGrowthRule(), FamineRule()],
        chronicle,
        initial_state=make_state(population=150, capacity=100),
    )

    engine.step()

    assert len(chronicle.filter(type=EventType.FAMINE)) == 16
    assert engine.state.map.tiles[0].population == 100
