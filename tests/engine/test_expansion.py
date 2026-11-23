"""Тесты правила экспансии."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import BattleRequest, RuleOutcome, StepContext
from worldsim.engine.rules.expansion import ExpansionRule


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int | None = 0,
    stockpile: float = 100.0,
    aggressiveness: float = 0.5,
    army: float = 10.0,
) -> Faction:
    """Создаёт фракцию для тестов экспансии."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        food_stockpile=stockpile,
        aggressiveness=aggressiveness,
        army_size=army,
    )


def make_state(
    *,
    size: int = 4,
    factions: tuple[Faction, ...] = (),
    overrides: dict[int, dict[str, object]] | None = None,
    aggression: float = 0.5,
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
    config = WorldConfig(
        seed=1,
        size=size,
        initial_factions=len(factions),
        aggression=aggression,
    )
    return WorldState(
        config=config,
        year=0,
        map=WorldMap(size=size, tiles=tuple(tiles)),
        factions=factions,
    )


class CaptureQueue:
    """Запоминает заявки на бой, переданные следующим правилам."""

    name = "capture-queue"
    priority = 11

    def __init__(self) -> None:
        self.requests: list[BattleRequest] = []

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        self.requests.extend(ctx.pending_battles)
        return RuleOutcome()


def test_starving_faction_takes_neutral_tile() -> None:
    """Голодная фракция всегда занимает нейтральный тайл."""
    chronicle = Chronicle()
    faction = make_faction(stockpile=0.0)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})
    engine = SimulationEngine([ExpansionRule()], chronicle, initial_state=state)

    updated = engine.step()

    owned = [tile for tile in updated.map.tiles if tile.owner_id == 0]
    assert len(owned) == 2
    events = chronicle.filter(type=EventType.EXPANSION)
    assert len(events) == 1
    assert events[0].year == 0
    assert events[0].faction_ids == (0,)


def test_satiated_non_aggressive_faction_does_not_expand() -> None:
    """Сытая и неагрессивная фракция остаётся на месте."""
    chronicle = Chronicle()
    faction = make_faction(stockpile=100.0, aggressiveness=0.0)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})
    engine = SimulationEngine([ExpansionRule()], chronicle, initial_state=state)

    updated = engine.step()

    assert [tile.owner_id for tile in updated.map.tiles] == [0] + [None] * 15
    assert chronicle.filter(type=EventType.EXPANSION) == ()


def test_zero_global_aggression_stops_expansion() -> None:
    """При нулевой агрессии мира атаки не начинаются."""
    chronicle = Chronicle()
    faction = make_faction(stockpile=100.0, aggressiveness=1.0)
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0}},
        aggression=0.0,
    )
    engine = SimulationEngine([ExpansionRule()], chronicle, initial_state=state)

    engine.step()

    assert chronicle.filter(type=EventType.EXPANSION) == ()


def test_enemy_target_goes_to_battle_queue() -> None:
    """Чужой тайл не захватывается сразу, а попадает в очередь боёв."""
    chronicle = Chronicle()
    attacker = make_faction(stockpile=0.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1)
    queue = CaptureQueue()
    state = make_state(
        factions=(attacker, defender),
        overrides={
            0: {"owner_id": 0},
            1: {"owner_id": 1},
            4: {"biome": Biome.OCEAN},
        },
    )
    engine = SimulationEngine([ExpansionRule(), queue], chronicle, initial_state=state)

    updated = engine.step()

    assert updated.map.tiles[1].owner_id == 1
    assert queue.requests == [BattleRequest(attacker_id=0, defender_id=1, tile_id=1)]
    events = chronicle.filter(type=EventType.WAR)
    assert len(events) == 1
    assert events[0].payload == {"attacker_id": 0, "defender_id": 1}


def test_target_weight_excludes_barren_tiles() -> None:
    """Тайл с нулевым плодородием не выбирается целью."""
    chronicle = Chronicle()
    faction = make_faction(stockpile=0.0)
    state = make_state(
        factions=(faction,),
        overrides={
            0: {"owner_id": 0},
            1: {"fertility": 0.0},
            4: {"fertility": 90.0},
        },
    )
    engine = SimulationEngine([ExpansionRule()], chronicle, initial_state=state)

    updated = engine.step()

    assert updated.map.tiles[1].owner_id is None
    assert updated.map.tiles[4].owner_id == 0


def test_one_action_per_faction_per_year() -> None:
    """За год фракция делает не больше одного хода."""
    chronicle = Chronicle()
    first = make_faction(stockpile=0.0)
    second = make_faction(1, name="Орда", color="#445566", capital=5)
    third = make_faction(2, name="Союз", color="#778899", capital=4)
    queue = CaptureQueue()
    state = make_state(
        factions=(first, second, third),
        overrides={
            0: {"owner_id": 0},
            1: {"owner_id": 0},
            4: {"owner_id": 2},
            5: {"owner_id": 1},
        },
        aggression=0.0,
    )
    engine = SimulationEngine([ExpansionRule(), queue], chronicle, initial_state=state)

    engine.step()

    total = len(chronicle.filter(type=EventType.EXPANSION)) + len(
        chronicle.filter(type=EventType.WAR)
    )
    assert total == 1


def test_water_is_not_a_target() -> None:
    """Вода не становится целью экспансии."""
    chronicle = Chronicle()
    faction = make_faction(stockpile=0.0)
    state = make_state(
        factions=(faction,),
        overrides={
            0: {"owner_id": 0},
            1: {"biome": Biome.OCEAN},
            4: {"biome": Biome.OCEAN},
        },
    )
    engine = SimulationEngine([ExpansionRule()], chronicle, initial_state=state)

    engine.step()

    assert chronicle.filter(type=EventType.EXPANSION) == ()


def test_previous_snapshot_is_not_mutated() -> None:
    """Исходный снимок не меняется после экспансии."""
    faction = make_faction(stockpile=0.0)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})
    before = state.snapshot_hash()
    engine = SimulationEngine([ExpansionRule()], Chronicle(), initial_state=state)

    engine.step()

    assert state.snapshot_hash() == before
    assert state.map.tiles[1].owner_id is None


def test_no_battle_requests_for_neutral_tile() -> None:
    """Захват нейтрального тайла не создаёт заявок на бой."""
    queue = CaptureQueue()
    faction = make_faction(stockpile=0.0)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})
    engine = SimulationEngine([ExpansionRule(), queue], Chronicle(), initial_state=state)

    engine.step()

    assert queue.requests == []


@pytest.mark.parametrize("army_presence", [0, 5])
def test_defended_tiles_are_still_candidates(army_presence: int) -> None:
    """Гарнизон снижает вес цели, но не убирает её из кандидатов."""
    chronicle = Chronicle()
    attacker = make_faction(stockpile=0.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        factions=(attacker, defender),
        overrides={
            0: {"owner_id": 0},
            1: {"owner_id": 1, "army_presence": army_presence},
            4: {"biome": Biome.OCEAN},
        },
    )
    queue = CaptureQueue()
    engine = SimulationEngine([ExpansionRule(), queue], chronicle, initial_state=state)

    engine.step()

    assert len(queue.requests) == 1
