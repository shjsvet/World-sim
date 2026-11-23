"""Тесты экономики фракции."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.economy import (
    MAX_RECRUIT_SHARE,
    RECRUITMENT_COST_PER_SOLDIER,
    TECH_COST,
    EconomyRule,
)


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int | None = 0,
    army: float = 0.0,
    treasury: float = 0.0,
    stockpile: float = 0.0,
    morale: float = 0.8,
    aggressiveness: float = 0.5,
    tech: float = 1.0,
    ideology: Ideology = Ideology.MILITARIST,
    mana: int = 0,
) -> Faction:
    """Создаёт фракцию для тестов экономики."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=ideology,
        culture="Люди",
        capital_tile_id=capital,
        army_size=army,
        treasury=treasury,
        food_stockpile=stockpile,
        morale=morale,
        aggressiveness=aggressiveness,
        tech_level=tech,
        mana_pool=mana,
    )


def make_state(
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    *,
    seed: int = 1,
    size: int = 4,
) -> WorldState:
    """Создаёт карту с фракциями и переопределениями тайлов."""
    tiles: list[RegionData] = []
    for index in range(size * size):
        data: dict[str, object] = {
            "id": index,
            "x": index % size,
            "y": index // size,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": 0,
            "population_capacity": 1_000,
        }
        data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    config = WorldConfig(seed=seed, size=size, initial_factions=len(factions))
    return WorldState(
        config=config,
        year=0,
        map=WorldMap(size=size, tiles=tuple(tiles)),
        factions=factions,
    )


def test_food_balance_accumulates() -> None:
    """Запас еды растёт на разницу производства и потребления."""
    faction = make_faction(stockpile=50.0, tech=10.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 100, "fertility": 60.0}},
    )
    engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=state)

    updated = engine.step()

    assert updated.factions[0].food_stockpile == pytest.approx(60.0)


def test_starvation_reduces_population_and_raises_aggression() -> None:
    """Голод уменьшает население, бьёт по морали и повышает агрессивность."""
    faction = make_faction(stockpile=0.0, tech=10.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 100, "fertility": 10.0}},
    )
    chronicle = Chronicle()
    engine = SimulationEngine([EconomyRule()], chronicle, initial_state=state)

    updated = engine.step()
    updated_faction = updated.factions[0]
    tile = updated.map.tiles[0]

    assert updated_faction.food_stockpile == 0.0
    assert 85 <= tile.population <= 95
    assert updated_faction.morale == pytest.approx(0.75)
    assert updated_faction.aggressiveness == pytest.approx(0.55)
    events = chronicle.filter(type=EventType.STARVATION)
    assert len(events) == 1
    assert 0.05 <= events[0].severity <= 0.15


def test_aggressiveness_is_capped() -> None:
    """Рост агрессивности от голода не превышает единицу."""
    faction = make_faction(stockpile=0.0, tech=10.0, aggressiveness=1.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 100, "fertility": 10.0}},
    )
    engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=state)

    updated = engine.step()

    assert updated.factions[0].aggressiveness == 1.0


def test_army_upkeep_is_paid_from_treasury() -> None:
    """Содержание армии списывается из казны."""
    faction = make_faction(army=100.0, treasury=100.0, tech=10.0)
    state = make_state((faction,), {0: {"owner_id": 0}})
    chronicle = Chronicle()
    engine = SimulationEngine([EconomyRule()], chronicle, initial_state=state)

    updated = engine.step()

    assert updated.factions[0].treasury == pytest.approx(50.0)
    assert updated.factions[0].army_size == pytest.approx(100.0)
    assert chronicle.filter(type=EventType.DESERTION) == ()


def test_empty_treasury_causes_desertion() -> None:
    """Без денег на содержание армия дезертирует, казна обнуляется."""
    faction = make_faction(army=100.0, treasury=10.0, tech=10.0)
    state = make_state((faction,), {0: {"owner_id": 0}})
    chronicle = Chronicle()
    engine = SimulationEngine([EconomyRule()], chronicle, initial_state=state)

    updated = engine.step()

    assert updated.factions[0].treasury == 0.0
    assert updated.factions[0].army_size == pytest.approx(50.0)
    assert updated.factions[0].morale == pytest.approx(0.78)
    events = chronicle.filter(type=EventType.DESERTION)
    assert len(events) == 1
    assert events[0].severity == pytest.approx(0.5)


def test_recruitment_limited_by_population_share() -> None:
    """Набор не превышает 10 % населения и оплачивается золотом."""
    faction = make_faction(army=0.0, treasury=1000.0, tech=10.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 1_000, "fertility": 50.0}},
    )
    chronicle = Chronicle()
    engine = SimulationEngine([EconomyRule()], chronicle, initial_state=state)

    updated = engine.step()
    updated_faction = updated.factions[0]

    assert updated_faction.army_size == pytest.approx(1_000 * MAX_RECRUIT_SHARE)
    assert updated_faction.treasury == pytest.approx(
        1_000.0 - 1_000 * MAX_RECRUIT_SHARE * RECRUITMENT_COST_PER_SOLDIER
    )
    assert updated_faction.army_size <= 1_000 * updated_faction.ideology.army_share
    assert len(chronicle.filter(type=EventType.RECRUITMENT)) == 1


def test_technology_grows_and_costs_gold() -> None:
    """Технологии растут за золото с бонусом идеологии."""
    scholar = make_faction(treasury=100.0, tech=1.0, ideology=Ideology.SCHOLARLY)
    warrior = make_faction(treasury=100.0, tech=1.0, ideology=Ideology.MILITARIST)

    scholar_state = make_state((scholar,), {0: {"owner_id": 0}})
    warrior_state = make_state((warrior,), {0: {"owner_id": 0}})

    scholar_engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=scholar_state)
    warrior_engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=warrior_state)

    scholar_after = scholar_engine.step().factions[0]
    warrior_after = warrior_engine.step().factions[0]

    assert scholar_after.treasury == pytest.approx(100.0 - TECH_COST)
    assert warrior_after.treasury == pytest.approx(100.0 - TECH_COST)
    assert scholar_after.tech_level > warrior_after.tech_level


def test_technology_is_capped() -> None:
    """Уровень технологий не превышает 10."""
    faction = make_faction(treasury=100.0, tech=9.99)
    state = make_state((faction,), {0: {"owner_id": 0}})
    engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=state)

    updated = engine.step()

    assert updated.factions[0].tech_level == 10.0


def test_mana_income_accumulates() -> None:
    """Доход маны с тайлов попадает в запас фракции."""
    faction = make_faction(tech=10.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "mana_regeneration": 5, "mana_density": 60}},
    )
    engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=state)

    updated = engine.step()

    assert updated.factions[0].mana_pool == 5


def test_no_negative_resources() -> None:
    """Казна и запас еды не уходят в минус даже при голоде."""
    faction = make_faction(army=500.0, treasury=10.0, stockpile=0.0, tech=10.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 200, "fertility": 5.0}},
    )
    engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=state)

    updated = engine.step()

    assert updated.factions[0].treasury == 0.0
    assert updated.factions[0].food_stockpile == 0.0


def test_economy_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковый хозяйственный результат."""

    def run_once() -> tuple[str, str]:
        faction = make_faction(stockpile=0.0, tech=10.0)
        state = make_state(
            (faction,),
            {0: {"owner_id": 0, "population": 100, "fertility": 10.0}},
            seed=11,
        )
        chronicle = Chronicle()
        engine = SimulationEngine([EconomyRule()], chronicle, initial_state=state)
        updated = engine.step()
        return updated.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()


def test_previous_snapshot_is_not_mutated() -> None:
    """Исходный снимок не меняется после экономического шага."""
    faction = make_faction(army=100.0, treasury=100.0, tech=10.0)
    state = make_state((faction,), {0: {"owner_id": 0}})
    before = state.snapshot_hash()
    engine = SimulationEngine([EconomyRule()], Chronicle(), initial_state=state)

    engine.step()

    assert state.snapshot_hash() == before
    assert state.factions[0].treasury == 100.0
