"""Тесты метрик фракций."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.metrics import (
    FOOD_PER_CAPITA,
    MORALE_PEACE_THRESHOLD,
    compute_faction_stats,
)
from worldsim.engine.rules import RuleOutcome, StepContext


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    culture: str = "Люди",
    morale: float = 0.8,
    stockpile: float = 100.0,
    treasury: float = 50.0,
    army: float = 10.0,
    capital: int | None = 0,
) -> Faction:
    """Создаёт фракцию для тестов метрик."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture=culture,
        capital_tile_id=capital,
        morale=morale,
        food_stockpile=stockpile,
        treasury=treasury,
        army_size=army,
    )


def make_state(
    *,
    size: int = 4,
    factions: tuple[Faction, ...] = (),
    overrides: dict[int, dict[str, object]] | None = None,
) -> WorldState:
    """Создаёт карту с точечными переопределениями тайлов."""
    tiles: list[RegionData] = []
    for index in range(size * size):
        data: dict[str, object] = {
            "id": index,
            "x": index % size,
            "y": index // size,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": 10,
            "population_capacity": 100,
        }
        if overrides is not None:
            data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    config = WorldConfig(seed=1, size=size, initial_factions=len(factions))
    return WorldState(
        config=config,
        year=0,
        map=WorldMap(size=size, tiles=tuple(tiles)),
        factions=factions,
    )


def test_basic_aggregates() -> None:
    """Территории, население и еда считаются по тайлам фракции."""
    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}, 1: {"owner_id": 0}})

    stats = compute_faction_stats(state)[0]

    assert stats.faction_id == 0
    assert stats.culture == "Люди"
    assert stats.tiles == 2
    assert stats.population == 20
    assert stats.food_production == pytest.approx(10.0)
    assert stats.food_consumption == pytest.approx(20 * FOOD_PER_CAPITA)
    assert stats.treasury == 50.0
    assert stats.food_stockpile == 100.0
    assert stats.army_size == 10.0
    assert stats.military_power == faction.military_power
    assert stats.is_starving is False
    assert stats.is_low_morale is False
    assert stats.border_contact == ()
    assert stats.enemies == ()


def test_faction_without_territory() -> None:
    """Фракция без территорий получает нули без деления на ноль."""
    faction = make_faction(stockpile=100.0, capital=None)
    state = make_state(factions=(faction,))

    stats = compute_faction_stats(state)[0]

    assert stats.tiles == 0
    assert stats.population == 0
    assert stats.food_production == 0.0
    assert stats.food_consumption == 0.0
    assert stats.mana_income == 0
    assert stats.mana_density_avg == 0.0
    assert stats.happiness_avg == 0.0
    assert stats.unrest_avg == 0.0
    assert stats.cities == 0


def test_empty_world_has_no_stats() -> None:
    """Без фракций метрик нет."""
    assert compute_faction_stats(make_state()) == {}


def test_cities_and_averages_over_populated_tiles() -> None:
    """Города считаются, а средние — только по населённым тайлам."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {"owner_id": 0, "population": 2_000, "urbanization": 60.0, "happiness": 90.0},
            1: {"owner_id": 0, "population": 0, "happiness": 30.0, "unrest": 70.0},
        },
    )

    stats = compute_faction_stats(state)[0]

    assert stats.cities == 1
    assert stats.population == 2_000
    assert stats.happiness_avg == pytest.approx(90.0)
    assert stats.unrest_avg == pytest.approx(0.0)


def test_mana_metrics() -> None:
    """Доход маны, лей-линии и средняя плотность считаются по владениям."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {"owner_id": 0, "mana_regeneration": 5, "mana_density": 80, "ley_line": True},
            1: {"owner_id": 0, "mana_regeneration": 3, "mana_density": 40},
        },
    )

    stats = compute_faction_stats(state)[0]

    assert stats.mana_income == 8
    assert stats.ley_lines == 1
    assert stats.mana_density_avg == pytest.approx(60.0)
    assert stats.magic_affinity == faction.magic_affinity


def test_starvation_conditions() -> None:
    """Голод: пустой запас или производство ниже потребления."""
    hungry = make_faction(stockpile=0.0)
    state = make_state(
        factions=(hungry,),
        overrides={0: {"owner_id": 0}},
    )
    assert compute_faction_stats(state)[0].is_starving is True

    poor = make_faction(stockpile=10.0)
    poor_state = make_state(
        factions=(poor,),
        overrides={
            0: {"owner_id": 0, "population": 100, "fertility": 10.0},
        },
    )
    stats = compute_faction_stats(poor_state)[0]
    assert stats.food_consumption > stats.food_production
    assert stats.is_starving is True


def test_low_morale() -> None:
    """Низкая мораль определяется порогом."""
    low = make_faction(morale=0.2)
    high = make_faction(morale=0.8)

    low_state = make_state(factions=(low,), overrides={0: {"owner_id": 0}})
    high_state = make_state(factions=(high,), overrides={0: {"owner_id": 0}})

    assert MORALE_PEACE_THRESHOLD == 0.3
    assert compute_faction_stats(low_state)[0].is_low_morale is True
    assert compute_faction_stats(high_state)[0].is_low_morale is False


def test_border_contact() -> None:
    """Границы считаются по соседям с другим владельцем."""
    first = make_faction()
    second = make_faction(faction_id=1, name="Орда", color="#445566", capital=5)
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0},
            1: {"owner_id": 0},
            5: {"owner_id": 1},
            6: {"owner_id": 1},
        },
    )

    stats = compute_faction_stats(state)

    assert stats[0].border_contact == (1,)
    assert stats[1].border_contact == (0,)


def test_stats_are_deterministic() -> None:
    """Повторный расчёт даёт те же значения."""
    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    assert compute_faction_stats(state) == compute_faction_stats(state)


def test_engine_passes_stats_to_rules() -> None:
    """Движок кэширует метрики в ``StepContext.stats``."""
    captured: dict[int, object] = {}

    class CaptureRule:
        name = "capture"
        priority = 1

        def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
            captured.update(ctx.stats)
            return RuleOutcome()

    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})
    engine = SimulationEngine([CaptureRule()], Chronicle(), initial_state=state)

    engine.step()

    assert set(captured) == {0}
    assert captured[0].tiles == 1  # type: ignore[union-attr]
