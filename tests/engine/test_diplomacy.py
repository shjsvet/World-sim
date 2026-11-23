"""Тесты дипломатии: запрос мира и перемирие."""

from __future__ import annotations

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import BattleRequest, RuleOutcome, StepContext
from worldsim.engine.rules.diplomacy import TRUCE_YEARS, DiplomacyRule
from worldsim.engine.rules.expansion import ExpansionRule


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int | None = 0,
    army: float = 10.0,
    treasury: float = 100.0,
    morale: float = 0.8,
    aggressiveness: float = 0.5,
    stockpile: float = 100.0,
) -> Faction:
    """Создаёт фракцию для тестов дипломатии."""
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
        aggressiveness=aggressiveness,
        food_stockpile=stockpile,
    )


def make_war(
    war_id: int = 0,
    *,
    attacker: int = 0,
    defender: int = 1,
    active: bool = True,
    truce: int | None = None,
    attacker_losses: float = 0.0,
    defender_losses: float = 0.0,
) -> War:
    """Создаёт запись войны для тестов."""
    return War(
        id=war_id,
        attacker_id=attacker,
        defender_id=defender,
        started_year=0,
        battles=0,
        attacker_losses=attacker_losses,
        defender_losses=defender_losses,
        active=active,
        truce_until_year=truce,
    )


def make_state(
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    *,
    wars: tuple[War, ...] = (),
    year: int = 0,
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
        year=year,
        map=WorldMap(size=size, tiles=tuple(tiles)),
        factions=factions,
        wars=wars,
    )


class CaptureQueue:
    """Запоминает заявки на бой, переданные расширением."""

    name = "capture-queue"
    priority = 11

    def __init__(self) -> None:
        self.requests: list[BattleRequest] = []

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        self.requests.extend(ctx.pending_battles)
        return RuleOutcome()


def test_low_morale_offers_peace_but_not_accepted() -> None:
    """Мораль ниже порога рождает предложение мира, но противник может отказать."""
    asker = make_faction(0, morale=0.2)
    opponent = make_faction(1, name="Орда", color="#445566", capital=1, morale=0.8)
    state = make_state(
        (asker, opponent),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
        wars=(make_war(),),
    )
    chronicle = Chronicle()
    engine = SimulationEngine([DiplomacyRule()], chronicle, initial_state=state)

    engine.run(100)

    assert len(chronicle.filter(type=EventType.PEACE_OFFER)) >= 1
    assert chronicle.filter(type=EventType.PEACE_TREATY) == ()
    assert engine.state.wars[0].active is True


def test_peace_accepted_when_opponent_is_exhausted() -> None:
    """Противник с моралью ниже 0.5 принимает мир и получает перемирие."""
    asker = make_faction(0, morale=0.0)
    opponent = make_faction(1, name="Орда", color="#445566", capital=1, morale=0.4)
    state = make_state(
        (asker, opponent),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
        wars=(make_war(),),
    )
    chronicle = Chronicle()
    engine = SimulationEngine([DiplomacyRule()], chronicle, initial_state=state)

    updated = engine.run(100)

    war = updated.wars[0]
    assert war.active is False
    assert war.truce_until_year is not None
    assert war.truce_until_year - TRUCE_YEARS >= 0
    assert len(chronicle.filter(type=EventType.PEACE_TREATY)) == 1
    assert updated.factions[0].morale == pytest.approx(0.1)
    assert updated.factions[1].morale == pytest.approx(0.5)
    assert updated.factions[0].aggressiveness == pytest.approx(0.4)


def test_high_morale_keeps_war() -> None:
    """При высокой морали обеих сторон война продолжается."""
    first = make_faction(0, morale=0.8)
    second = make_faction(1, name="Орда", color="#445566", capital=1, morale=0.8)
    state = make_state(
        (first, second),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
        wars=(make_war(),),
    )
    chronicle = Chronicle()
    engine = SimulationEngine([DiplomacyRule()], chronicle, initial_state=state)

    updated = engine.run(10)

    assert chronicle.filter(type=EventType.PEACE_OFFER) == ()
    assert updated.wars[0].active is True


def test_acceptance_by_heavy_losses() -> None:
    """Противник с большими потерями соглашается на мир даже при высокой морали."""
    asker = make_faction(0, morale=0.0)
    opponent = make_faction(1, name="Орда", color="#445566", capital=1, morale=0.8)
    state = make_state(
        (asker, opponent),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
        wars=(make_war(attacker_losses=10.0, defender_losses=100.0),),
    )
    engine = SimulationEngine([DiplomacyRule()], Chronicle(), initial_state=state)

    updated = engine.run(100)

    assert updated.wars[0].active is False


def test_truce_blocks_expansion() -> None:
    """Под перемирием экспансия не атакует противника."""
    attacker = make_faction(0, stockpile=0.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (attacker, defender),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 4: {"biome": Biome.OCEAN}},
        wars=(make_war(active=False, truce=100),),
    )
    chronicle = Chronicle()
    queue = CaptureQueue()
    engine = SimulationEngine([ExpansionRule(), queue], chronicle, initial_state=state)

    engine.step()

    assert queue.requests == []
    assert chronicle.filter(type=EventType.WAR) == ()
    assert engine.state.map.tiles[1].owner_id == 1


def test_expired_truce_allows_attack() -> None:
    """После окончания перемирия атаки возобновляются."""
    attacker = make_faction(0, stockpile=0.0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        (attacker, defender),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}, 4: {"biome": Biome.OCEAN}},
        wars=(make_war(active=False, truce=3),),
        year=5,
    )
    chronicle = Chronicle()
    queue = CaptureQueue()
    engine = SimulationEngine([ExpansionRule(), queue], chronicle, initial_state=state)

    engine.step()

    assert len(queue.requests) == 1
    assert len(chronicle.filter(type=EventType.WAR)) == 1


def test_diplomacy_does_not_mutate_snapshot() -> None:
    """Исходный снимок не меняется после дипломатии."""
    asker = make_faction(0, morale=0.0)
    opponent = make_faction(1, name="Орда", color="#445566", capital=1, morale=0.4)
    state = make_state(
        (asker, opponent),
        {0: {"owner_id": 0}, 1: {"owner_id": 1}},
        wars=(make_war(),),
    )
    before = state.snapshot_hash()
    engine = SimulationEngine([DiplomacyRule()], Chronicle(), initial_state=state)

    engine.run(100)

    assert state.snapshot_hash() == before
    assert state.factions[0].morale == 0.0


def test_diplomacy_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковый дипломатический исход."""

    def run_once() -> tuple[str, str]:
        asker = make_faction(0, morale=0.0)
        opponent = make_faction(1, name="Орда", color="#445566", capital=1, morale=0.4)
        state = make_state(
            (asker, opponent),
            {0: {"owner_id": 0}, 1: {"owner_id": 1}},
            wars=(make_war(),),
            seed=13,
        )
        chronicle = Chronicle()
        engine = SimulationEngine([DiplomacyRule()], chronicle, initial_state=state)
        updated = engine.run(50)
        return updated.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()
