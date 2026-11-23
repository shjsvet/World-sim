"""Тесты правила войны."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import BattleRequest, RuleOutcome, StepContext
from worldsim.engine.rules.war import WarResolutionRule


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int | None = 0,
    army: float = 10.0,
    treasury: float = 100.0,
    morale: float = 0.8,
) -> Faction:
    """Создаёт фракцию для тестов войны."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        army_size=army,
        treasury=treasury,
        morale=morale,
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
            "population": 100,
            "population_capacity": 1_000,
            "happiness": 60.0,
            "unrest": 10.0,
            "fortification": 0.0,
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


class BattleInjector:
    """Добавляет заявки на бой перед правилом войны."""

    name = "inject-battles"
    priority = 19

    def __init__(self, requests: list[BattleRequest]) -> None:
        self._requests = requests

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        ctx.pending_battles.extend(self._requests)
        return RuleOutcome()


class SequentialInjector:
    """Добавляет по одной заявке за шаг."""

    name = "inject-sequential"
    priority = 19

    def __init__(self, requests: list[BattleRequest]) -> None:
        self._requests = list(requests)

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        if self._requests:
            ctx.pending_battles.append(self._requests.pop(0))
        return RuleOutcome()


def test_strong_attacker_captures_tile() -> None:
    """Сильный атакующий захватывает тайл и оккупирует его."""
    attacker = make_faction(0, army=100.0, treasury=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=10.0, treasury=50.0)
    state = make_state((attacker, defender), {0: {"owner_id": 0}, 1: {"owner_id": 1}})
    chronicle = Chronicle()
    engine = SimulationEngine(
        [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
        chronicle,
        initial_state=state,
    )

    updated = engine.step()
    tile = updated.map.tiles[1]

    assert tile.owner_id == 0
    assert tile.army_presence >= 1
    assert tile.unrest == pytest.approx(30.0)
    assert tile.happiness == pytest.approx(50.0)
    assert tile.population <= 95
    assert updated.factions[0].army_size < 100.0
    assert updated.factions[1].army_size < 10.0
    assert updated.factions[0].morale == pytest.approx(0.85)
    assert updated.factions[1].morale == pytest.approx(0.7)
    assert updated.factions[0].treasury > 100.0
    assert updated.factions[1].treasury >= 0.0
    assert updated.wars and updated.wars[0].battles == 1
    assert updated.wars[0].active is True

    assert len(chronicle.filter(type=EventType.OCCUPATION)) == 1
    assert len(chronicle.filter(type=EventType.BATTLE_WON)) == 1
    assert state.map.tiles[1].owner_id == 1


def test_weak_attacker_fails() -> None:
    """Слабый атакующий не забирает тайл и теряет мораль."""
    attacker = make_faction(0, army=5.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=500.0)
    state = make_state(
        (attacker, defender),
        {0: {"owner_id": 0}, 1: {"owner_id": 1, "army_presence": 10}},
    )
    chronicle = Chronicle()
    engine = SimulationEngine(
        [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
        chronicle,
        initial_state=state,
    )

    updated = engine.step()

    assert updated.map.tiles[1].owner_id == 1
    assert updated.factions[0].morale < 0.8
    assert updated.factions[1].morale > 0.8
    assert updated.factions[0].treasury == 100.0
    assert updated.factions[1].treasury == 100.0
    assert len(chronicle.filter(type=EventType.BATTLE_LOST)) == 1


def test_stronger_side_wins_more_often() -> None:
    """При большом перевесе атакующий побеждает более чем в 60 % прогонов."""
    wins = 0
    for seed in range(100):
        attacker = make_faction(0, army=100.0)
        defender = make_faction(1, name="Орда", color="#445566", capital=1, army=5.0)
        state = make_state(
            (attacker, defender),
            {0: {"owner_id": 0}, 1: {"owner_id": 1}},
            seed=seed,
        )
        engine = SimulationEngine(
            [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
            Chronicle(),
            initial_state=state,
        )
        if engine.step().map.tiles[1].owner_id == 0:
            wins += 1

    assert wins > 60


def test_only_participants_lose_resources() -> None:
    """Потери и мораль меняются только у участников боя."""
    attacker = make_faction(0, army=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=10.0)
    neutral = make_faction(2, name="Союз", color="#778899", capital=2, army=50.0, treasury=30.0)
    state = make_state(
        (attacker, defender, neutral),
        {
            0: {"owner_id": 0},
            1: {"owner_id": 1},
            2: {"owner_id": 2},
        },
    )
    engine = SimulationEngine(
        [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
        Chronicle(),
        initial_state=state,
    )

    updated = engine.step()
    third = updated.factions[2]

    assert third.army_size == 50.0
    assert third.morale == 0.8
    assert third.treasury == 30.0


def test_treasury_never_goes_negative() -> None:
    """Трофеи не уводят казну проигравшего в минус."""
    attacker = make_faction(0, army=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=1.0, treasury=5.0)
    state = make_state((attacker, defender), {0: {"owner_id": 0}, 1: {"owner_id": 1}})
    engine = SimulationEngine(
        [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
        Chronicle(),
        initial_state=state,
    )

    updated = engine.step()

    assert updated.factions[1].treasury == 0.0
    assert updated.factions[0].treasury == pytest.approx(105.0)


def test_owner_changes_exactly_one_tile() -> None:
    """Захват меняет владельца ровно одного тайла."""
    attacker = make_faction(0, army=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=1.0)
    state = make_state((attacker, defender), {0: {"owner_id": 0}, 1: {"owner_id": 1}})
    engine = SimulationEngine(
        [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
        Chronicle(),
        initial_state=state,
    )

    updated = engine.step()

    assert [tile.owner_id for tile in updated.map.tiles].count(0) == 2
    assert updated.map.tiles[1].owner_id == 0


def test_capital_fall_moves_capital() -> None:
    """Падение столицы переносит её на уцелевший тайл."""
    attacker = make_faction(0, army=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=1.0)
    state = make_state(
        (attacker, defender),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 2: {"owner_id": 1}},
    )
    chronicle = Chronicle()
    engine = SimulationEngine(
        [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
        chronicle,
        initial_state=state,
    )

    updated = engine.step()

    assert updated.factions[1].capital_tile_id == 2
    assert len(chronicle.filter(type=EventType.CAPITAL_FALL)) == 1


def test_attacks_per_side_are_limited() -> None:
    """За год фракция проводит не больше трёх атак."""
    attacker = make_faction(0, army=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=1.0)
    overrides = {0: {"owner_id": 0}}
    for tile_id in range(1, 6):
        overrides[tile_id] = {"owner_id": 1}
    state = make_state((attacker, defender), overrides)
    requests = [BattleRequest(0, 1, tile_id) for tile_id in range(1, 6)]
    chronicle = Chronicle()
    engine = SimulationEngine(
        [BattleInjector(requests), WarResolutionRule()],
        chronicle,
        initial_state=state,
    )

    updated = engine.step()

    assert updated.wars[0].battles == 3
    assert len(chronicle.filter(type=EventType.BATTLE_WON)) == 3
    assert [tile.owner_id for tile in updated.map.tiles].count(0) == 4


def test_war_is_updated_across_steps() -> None:
    """Повторные бои обновляют одну и ту же войну."""
    attacker = make_faction(0, army=100.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1, army=1.0)
    state = make_state(
        (attacker, defender),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 2: {"owner_id": 1}},
    )
    injector = SequentialInjector([BattleRequest(0, 1, 1), BattleRequest(0, 1, 2)])
    engine = SimulationEngine([injector, WarResolutionRule()], Chronicle(), initial_state=state)

    updated = engine.run(2)

    assert len(updated.wars) == 1
    assert updated.wars[0].battles == 2
    assert updated.wars[0].attacker_losses > 0.0
    assert updated.wars[0].defender_losses > 0.0


def test_war_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковый исход войны."""

    def run_once() -> tuple[str, str]:
        attacker = make_faction(0, army=100.0)
        defender = make_faction(1, name="Орда", color="#445566", capital=1, army=10.0)
        state = make_state((attacker, defender), {0: {"owner_id": 0}, 1: {"owner_id": 1}})
        chronicle = Chronicle()
        engine = SimulationEngine(
            [BattleInjector([BattleRequest(0, 1, 1)]), WarResolutionRule()],
            chronicle,
            initial_state=state,
        )
        updated = engine.step()
        return updated.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()
