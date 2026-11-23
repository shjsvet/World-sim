"""Тесты армий на карте."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.army import (
    ArmyMovementRule,
    FrontlineRule,
    OccupationRule,
)


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int | None = 0,
    army: float = 100.0,
) -> Faction:
    """Создаёт фракцию для тестов армий."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        army_size=army,
    )


def make_war(attacker: int = 0, defender: int = 1) -> War:
    """Создаёт активную войну между фракциями."""
    return War(
        id=0,
        attacker_id=attacker,
        defender_id=defender,
        started_year=0,
        battles=1,
        active=True,
    )


def make_state(
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    *,
    wars: tuple[War, ...] = (),
    seed: int = 1,
    size: int = 4,
) -> WorldState:
    """Создаёт карту с фракциями, войнами и переопределениями тайлов."""
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
        }
        data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    config = WorldConfig(seed=seed, size=size, initial_factions=len(factions))
    return WorldState(
        config=config,
        year=0,
        map=WorldMap(size=size, tiles=tuple(tiles)),
        factions=factions,
        wars=wars,
    )


def run_rule(rule: object, state: WorldState, seed: int = 1) -> WorldState:
    """Выполняет шаг движка с одним правилом."""
    engine = SimulationEngine(
        [rule],  # type: ignore[list-item]
        Chronicle(),
        initial_state=state,
    )
    return engine.step()


def test_total_presence_does_not_exceed_army() -> None:
    """Суммарный гарнизон не превышает размер армии."""
    first = make_faction(0, army=100.0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (first, second),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 2: {"owner_id": 0}, 3: {"owner_id": 0}},
        wars=(make_war(),),
    )

    updated = run_rule(ArmyMovementRule(), state)

    total = sum(tile.army_presence for tile in updated.map.tiles if tile.owner_id == 0)
    assert total <= 100
    assert total > 0


def test_army_pulls_to_frontline() -> None:
    """Гарнизон стягивается к границе с врагом."""
    first = make_faction(0, army=100.0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (first, second),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 8: {"owner_id": 0}},
        wars=(make_war(),),
        size=6,
    )

    updated = run_rule(ArmyMovementRule(), state)

    assert updated.map.tiles[0].army_presence > updated.map.tiles[8].army_presence


def test_river_makes_frontline_cheaper() -> None:
    """Река снижает стоимость перемещения и повышает гарнизон."""
    first = make_faction(0, army=100.0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (first, second),
        {
            0: {"owner_id": 0, "has_river": True},
            1: {"owner_id": 1},
            2: {"owner_id": 0},
        },
        wars=(make_war(),),
        size=6,
    )

    updated = run_rule(ArmyMovementRule(), state)

    assert updated.map.tiles[0].army_presence > updated.map.tiles[2].army_presence


def test_empty_army_clears_garrisons() -> None:
    """Без армии гарнизоны снимаются."""
    faction = make_faction(0, army=0.0)
    state = make_state(
        (faction,),
        {0: {"owner_id": 0, "army_presence": 5}, 1: {"owner_id": 0, "army_presence": 3}},
    )

    updated = run_rule(ArmyMovementRule(), state)

    assert updated.map.tiles[0].army_presence == 0
    assert updated.map.tiles[1].army_presence == 0


def test_frontline_builds_fortifications() -> None:
    """Приграничный тайл укрепляется, тыловой — нет."""
    first = make_faction(0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (first, second),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 8: {"owner_id": 0}},
        wars=(make_war(),),
        size=6,
    )

    updated = run_rule(FrontlineRule(), state)

    assert updated.map.tiles[0].fortification == 1.0
    assert updated.map.tiles[8].fortification == 0.0


def test_frontline_needs_war() -> None:
    """Без войны укрепления не строятся."""
    faction = make_faction(0)
    state = make_state((faction,), {0: {"owner_id": 0}})

    updated = run_rule(FrontlineRule(), state)

    assert updated.map.tiles[0].fortification == 0.0


def test_occupation_does_not_change_owners() -> None:
    """Правило оккупации само по себе не меняет владельцев."""
    first = make_faction(0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (first, second),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )

    updated = run_rule(OccupationRule(), state)

    assert updated.map.tiles[0].owner_id == 0
    assert updated.map.tiles[1].owner_id == 1


def test_garrison_is_capped_by_army() -> None:
    """Гарнизон не может превышать армию фракции."""
    faction = make_faction(0, army=3.0)
    state = make_state((faction,), {0: {"owner_id": 0, "army_presence": 10}})
    chronicle = Chronicle()

    engine = SimulationEngine([OccupationRule()], chronicle, initial_state=state)
    updated = engine.step()

    assert updated.map.tiles[0].army_presence == 3
    assert len(chronicle.filter(type=EventType.OCCUPATION)) == 1


def test_army_movement_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковое распределение армии."""

    def run_once() -> str:
        first = make_faction(0, army=100.0)
        second = make_faction(1, name="Орда", color="#445566", capital=1)
        state = make_state(
            (first, second),
            {0: {"owner_id": 0}, 1: {"owner_id": 1}, 2: {"owner_id": 0}},
            wars=(make_war(),),
            seed=17,
        )
        return run_rule(ArmyMovementRule(), state).snapshot_hash()

    assert run_once() == run_once()


def test_previous_snapshot_is_not_mutated() -> None:
    """Исходный снимок не меняется после распределения армии."""
    first = make_faction(0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (first, second),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
        wars=(make_war(),),
    )
    before = state.snapshot_hash()

    run_rule(ArmyMovementRule(), state)

    assert state.snapshot_hash() == before
