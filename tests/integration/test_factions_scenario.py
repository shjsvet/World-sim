"""Интеграционные тесты сценария фракций."""

from __future__ import annotations

import time

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.geography import WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import Rule
from worldsim.engine.rules.diplomacy import TRUCE_YEARS, DiplomacyRule
from worldsim.engine.rules.economy import EconomyRule
from worldsim.engine.rules.expansion import ExpansionRule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.engine.rules.random_events import FamineRule, PlagueRule
from worldsim.engine.rules.war import WarResolutionRule
from worldsim.generator.world import create_world

pytestmark = pytest.mark.integration


def full_rules() -> list[Rule]:
    """Полный набор правил этапа 1."""
    return [
        EconomyRule(),
        FamineRule(),
        ExpansionRule(),
        PopulationGrowthRule(),
        PlagueRule(),
        WarResolutionRule(),
        DiplomacyRule(),
    ]


def build_engine(
    state: WorldState,
    chronicle: Chronicle | None = None,
) -> SimulationEngine:
    """Собирает движок со всеми правилами."""
    target = chronicle if chronicle is not None else Chronicle()
    return SimulationEngine(full_rules(), target, initial_state=state)


def make_world(seed: int = 42, size: int = 32, factions: int = 3) -> WorldState:
    """Создаёт мир для интеграционных сценариев."""
    return create_world(WorldConfig(seed=seed, size=size, initial_factions=factions))


def test_hundred_year_scenario_invariants(request: pytest.FixtureRequest) -> None:
    """За 100 лет мир остаётся валидным, а прошлые снимки неизменны."""
    state = make_world()
    chronicle = Chronicle()
    engine = build_engine(state, chronicle)
    snapshots: list[tuple[int, str, WorldState]] = []

    started = time.perf_counter()
    for _ in range(10):
        state = engine.run(10)
        snapshots.append((state.year, state.snapshot_hash(), state))
    elapsed = time.perf_counter() - started

    if getattr(request.config.option, "cov_source", None) is None:
        assert elapsed < 10.0
    assert state.year == 100
    assert len(snapshots) == 10

    faction_ids = {faction.id for faction in state.factions}
    for tile in state.map.tiles:
        if tile.owner_id is not None:
            assert tile.owner_id in faction_ids
            assert tile.is_land
        if tile.biome.is_water:
            assert tile.owner_id is None

    for faction in state.factions:
        assert faction.treasury >= 0.0
        assert faction.food_stockpile >= 0.0
        assert 0.0 <= faction.morale <= 1.0
        assert faction.army_size >= 0.0
        assert all(amount >= 0.0 for amount in faction.resources.values())

    years = [event.year for event in chronicle.all_events()]
    assert years == sorted(years)

    for year, digest, snapshot in snapshots:
        assert snapshot.year == year
        assert snapshot.snapshot_hash() == digest

    for faction in state.factions:
        owns_tiles = any(tile.owner_id == faction.id for tile in state.map.tiles)
        if not owns_tiles:
            assert chronicle.filter(faction_id=faction.id)


def test_same_seed_is_deterministic() -> None:
    """Повторный прогон с тем же сидом даёт тот же мир и летопись."""

    def run_once(seed: int) -> tuple[str, str]:
        state = make_world(seed=seed)
        chronicle = Chronicle()
        engine = build_engine(state, chronicle)
        final = engine.run(100)
        return final.snapshot_hash(), chronicle.to_json()

    first = run_once(42)
    second = run_once(42)
    third = run_once(43)

    assert first == second
    assert first != third


def test_starvation_scenario() -> None:
    """Голод за 10 лет снижает население и повышает агрессивность."""
    state = make_world(seed=5, size=16, factions=1)
    faction = state.factions[0]
    hungry_tiles = tuple(
        tile.model_copy(update={"fertility": 5.0}) if tile.owner_id == faction.id else tile
        for tile in state.map.tiles
    )
    state = state.evolve(
        map=WorldMap(size=state.map.size, tiles=hungry_tiles),
        factions=(
            faction.evolve(
                food_stockpile=0.0,
                army_size=0.0,
                treasury=0.0,
                tech_level=10.0,
            ),
        ),
    )
    before_population = sum(
        tile.population for tile in state.map.tiles if tile.owner_id == faction.id
    )
    before_aggression = faction.aggressiveness
    chronicle = Chronicle()
    engine = build_engine(state, chronicle)

    after = engine.run(10)

    after_population = sum(
        tile.population for tile in after.map.tiles if tile.owner_id == faction.id
    )
    assert after_population < before_population
    assert after.factions[0].aggressiveness > before_aggression
    assert chronicle.filter(type=EventType.STARVATION)


def test_peace_scenario_and_truce() -> None:
    """Низкая мораль приводит к миру, а перемирие прекращает атаки."""
    state = make_world(seed=7, size=16, factions=2)
    exhausted = state.factions[0].evolve(morale=0.0)
    opponent = state.factions[1].evolve(morale=0.4)
    war = War(
        id=0,
        attacker_id=0,
        defender_id=1,
        started_year=0,
        battles=1,
        active=True,
    )
    state = state.evolve(factions=(exhausted, opponent), wars=(war,))

    chronicle = Chronicle()
    diplomacy_engine = SimulationEngine([DiplomacyRule()], chronicle, initial_state=state)
    for _ in range(100):
        state = diplomacy_engine.step()
        if not state.wars[0].active:
            break

    assert len(chronicle.filter(type=EventType.PEACE_OFFER)) >= 1
    assert len(chronicle.filter(type=EventType.PEACE_TREATY)) == 1
    assert state.wars[0].active is False
    assert state.wars[0].truce_until_year is not None
    peace_year = state.wars[0].truce_until_year - TRUCE_YEARS

    conflict_engine = build_engine(state, chronicle)
    after = conflict_engine.run(10)

    wars_after_peace = [
        event
        for event in chronicle.all_events()
        if event.type is EventType.WAR and event.year > peace_year
    ]
    assert wars_after_peace == []
    assert after.year == state.year + 10
