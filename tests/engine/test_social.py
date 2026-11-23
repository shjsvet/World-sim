"""Тесты социальной динамики тайлов."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.social import (
    HappinessRule,
    RiotRule,
    SecessionRule,
    UnrestRule,
    UrbanizationRule,
)


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int | None = 0,
    culture: str = "Люди",
    stockpile: float = 100.0,
) -> Faction:
    """Создаёт фракцию для тестов социальной динамики."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture=culture,
        capital_tile_id=capital,
        food_stockpile=stockpile,
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
            "population": 10,
            "population_capacity": 1_000,
            "happiness": 50.0,
            "unrest": 0.0,
            "culture": "Люди",
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


def run_rule(
    rule: object,
    state: WorldState,
    seed: int = 1,
) -> tuple[WorldState, Chronicle]:
    """Выполняет один шаг движка с одним правилом."""
    chronicle = Chronicle()
    engine = SimulationEngine([rule], chronicle, initial_state=state)  # type: ignore[list-item]
    return engine.step(), chronicle


def test_happiness_grows_in_peace() -> None:
    """В мирные годы с едой и родной культурой счастье растёт."""
    faction = make_faction(stockpile=100.0)
    state = make_state((faction,), {0: {"owner_id": 0}})

    updated, _ = run_rule(HappinessRule(), state)

    assert updated.map.tiles[0].happiness == pytest.approx(53.0)


def test_happiness_falls_during_famine_and_foreign_culture() -> None:
    """Голод, чужая культура и беспорядки снижают счастье."""
    faction = make_faction(stockpile=0.0)
    state = make_state(
        (faction,),
        {
            0: {
                "owner_id": 0,
                "population": 100,
                "fertility": 10.0,
                "culture": "Орки",
                "unrest": 70.0,
            }
        },
    )

    updated, _ = run_rule(HappinessRule(), state)

    assert updated.map.tiles[0].happiness < 50.0


def test_unrest_grows_with_poverty_and_falls_with_order() -> None:
    """Недовольство растёт при низком счастье и падает от порядка."""
    faction = make_faction()
    riot_state = make_state((faction,), {0: {"owner_id": 0, "happiness": 20.0}})
    calm_state = make_state(
        (faction,),
        {0: {"owner_id": 0, "happiness": 80.0, "army_presence": 5, "infrastructure": 30.0}},
    )

    rioted, _ = run_rule(UnrestRule(), riot_state)
    calmed, _ = run_rule(UnrestRule(), calm_state)

    assert rioted.map.tiles[0].unrest > 0.0
    assert calmed.map.tiles[0].unrest == 0.0


def test_riot_reduces_population_and_raises_unrest() -> None:
    """Бунт убивает часть населения и повышает недовольство."""
    faction = make_faction()
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 1_000, "happiness": 10.0, "unrest": 70.0}},
    )
    chronicle = Chronicle()

    engine = SimulationEngine([RiotRule()], chronicle, initial_state=state)
    updated = engine.step()

    tile = updated.map.tiles[0]
    assert 850 <= tile.population <= 950
    assert tile.unrest == pytest.approx(80.0)
    assert len(chronicle.filter(type=EventType.RIOT)) == 1


def test_secession_creates_neutral_tile() -> None:
    """При отсутствии родственного соседа тайл отделяется."""
    faction = make_faction()
    state = make_state((faction,), {0: {"owner_id": 0, "unrest": 90.0}})
    chronicle = Chronicle()

    engine = SimulationEngine([SecessionRule()], chronicle, initial_state=state)
    updated = engine.step()

    assert updated.map.tiles[0].owner_id is None
    assert updated.map.tiles[0].army_presence == 0
    assert len(chronicle.filter(type=EventType.SECESSION)) == 1
    assert updated.factions[0].capital_tile_id is None


def test_defection_moves_tile_to_same_culture_neighbor() -> None:
    """Тайл переходит к соседу той же культуры."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Союз", color="#445566", capital=1, culture="Люди")
    state = make_state(
        (first, second),
        {0: {"owner_id": 0, "unrest": 90.0}, 1: {"owner_id": 1}},
    )
    chronicle = Chronicle()

    engine = SimulationEngine([SecessionRule()], chronicle, initial_state=state)
    updated = engine.step()

    assert updated.map.tiles[0].owner_id == 1
    assert updated.factions[0].capital_tile_id is None
    events = chronicle.filter(type=EventType.DEFECTION)
    assert len(events) == 1
    assert events[0].faction_ids == (0, 1)


def test_city_rise_when_thresholds_are_crossed() -> None:
    """Тайл становится городом на порогах населения и урбанизации."""
    faction = make_faction(stockpile=100.0)
    state = make_state(
        (faction,),
        {
            0: {
                "owner_id": 0,
                "population": 1_500,
                "population_capacity": 2_000,
                "urbanization": 49.0,
                "infrastructure": 30.0,
                "happiness": 80.0,
            }
        },
    )
    chronicle = Chronicle()

    engine = SimulationEngine([UrbanizationRule()], chronicle, initial_state=state)
    updated = engine.step()

    tile = updated.map.tiles[0]
    assert tile.urbanization == pytest.approx(51.0)
    assert tile.is_city is True
    assert tile.population_capacity == 2_010
    assert len(chronicle.filter(type=EventType.CITY_RISE)) == 1


def test_existing_city_does_not_duplicate_bonus() -> None:
    """Повторный вход в статус города не даёт бонус ещё раз."""
    faction = make_faction(stockpile=100.0)
    state = make_state(
        (faction,),
        {
            0: {
                "owner_id": 0,
                "population": 1_500,
                "population_capacity": 2_000,
                "urbanization": 60.0,
                "infrastructure": 30.0,
                "happiness": 80.0,
            }
        },
    )
    chronicle = Chronicle()

    engine = SimulationEngine([UrbanizationRule()], chronicle, initial_state=state)
    updated = engine.step()

    assert updated.map.tiles[0].population_capacity == 2_000
    assert chronicle.filter(type=EventType.CITY_RISE) == ()


def test_urbanization_falls_during_famine() -> None:
    """Голод снижает урбанизацию."""
    faction = make_faction(stockpile=0.0)
    state = make_state(
        (faction,),
        {
            0: {
                "owner_id": 0,
                "population": 600,
                "fertility": 10.0,
                "population_capacity": 1_000,
                "urbanization": 60.0,
                "infrastructure": 30.0,
                "happiness": 80.0,
            }
        },
    )

    updated, _ = run_rule(UrbanizationRule(), state)

    assert updated.map.tiles[0].urbanization < 60.0


def test_unowned_and_water_tiles_are_untouched() -> None:
    """Нейтральные и водные тайлы не меняются."""
    faction = make_faction()
    state = make_state(
        (faction,),
        {
            0: {"owner_id": 0},
            1: {"biome": Biome.OCEAN, "happiness": 10.0, "unrest": 90.0},
            2: {"owner_id": None, "happiness": 10.0, "unrest": 90.0},
        },
    )

    updated, _ = run_rule(HappinessRule(), state)

    assert updated.map.tiles[1] == state.map.tiles[1]
    assert updated.map.tiles[2] == state.map.tiles[2]


def test_social_rules_are_deterministic() -> None:
    """Одинаковый сид даёт одинаковый бунт."""

    def run_once() -> tuple[str, str]:
        faction = make_faction()
        state = make_state(
            (faction,),
            {0: {"owner_id": 0, "population": 1_000, "happiness": 10.0, "unrest": 70.0}},
            seed=9,
        )
        chronicle = Chronicle()
        engine = SimulationEngine([RiotRule()], chronicle, initial_state=state)
        updated = engine.step()
        return updated.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()


def test_previous_snapshot_is_not_mutated() -> None:
    """Исходный снимок не меняется после социального шага."""
    faction = make_faction()
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "population": 1_000, "happiness": 10.0, "unrest": 70.0}},
    )
    before = state.snapshot_hash()
    engine = SimulationEngine([RiotRule()], Chronicle(), initial_state=state)

    engine.step()

    assert state.snapshot_hash() == before
