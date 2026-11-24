"""Тесты добычи ресурсов."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.extraction import ExtractionRule


def make_faction(
    faction_id: int = 0,
    *,
    treasury: float = 0.0,
    stockpile: float = 0.0,
) -> Faction:
    """Создаёт фракцию с пустой казной и складом."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.AGRARIAN,
        culture="Люди",
        capital_tile_id=0,
        treasury=treasury,
        food_stockpile=stockpile,
    )


def make_state(
    *,
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    seed: int = 1,
) -> WorldState:
    """Создаёт карту с переопределениями тайлов."""
    tiles: list[RegionData] = []
    for index in range(16):
        data: dict[str, object] = {
            "id": index,
            "x": index % 4,
            "y": index // 4,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": 10,
            "population_capacity": 10_000,
        }
        data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=seed, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
    )


def run_rule(state: WorldState) -> tuple[WorldState, Chronicle]:
    """Выполняет один шаг с правилом добычи."""
    chronicle = Chronicle()
    engine = SimulationEngine([ExtractionRule()], chronicle, initial_state=state)
    return engine.step(), chronicle


def test_food_extraction_fills_stockpile() -> None:
    """FOOD пополняет запас еды и истощает месторождение."""
    faction = make_faction(stockpile=0.0)
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.FOOD,
                "resource_amount": 10.0,
                "resource_depletion": 100.0,
            }
        },
    )

    updated, chronicle = run_rule(state)

    assert updated.factions[0].food_stockpile == 10.0
    assert updated.map.tiles[0].resource_depletion == 90.0
    assert chronicle.filter(type=EventType.RESOURCE_DEPLETED) == ()


def test_gold_extraction_fills_treasury() -> None:
    """GOLD пополняет казну."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.GOLD,
                "resource_amount": 10.0,
                "resource_depletion": 100.0,
            }
        },
    )

    updated, _ = run_rule(state)

    assert updated.factions[0].treasury == 10.0


def test_mana_extraction_goes_to_resources() -> None:
    """MANA попадает на склад ресурсов фракции."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.MANA,
                "resource_amount": 10.0,
                "resource_depletion": 100.0,
            }
        },
    )

    updated, _ = run_rule(state)

    assert updated.factions[0].resources["mana"] == 10.0


def test_city_and_river_increase_extraction() -> None:
    """Город и река повышают добычу."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.FOOD,
                "resource_amount": 10.0,
                "resource_depletion": 100.0,
                "population": 2_000,
                "urbanization": 60.0,
                "has_river": True,
            }
        },
    )

    updated, _ = run_rule(state)

    assert updated.factions[0].food_stockpile > 10.0
    assert updated.factions[0].food_stockpile < 20.0


def test_depleted_resource_event() -> None:
    """Истощение месторождения даёт RESOURCE_DEPLETED."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.FOOD,
                "resource_amount": 10.0,
                "resource_depletion": 5.0,
            }
        },
    )

    updated, chronicle = run_rule(state)

    assert updated.map.tiles[0].resource_depletion == 0.0
    assert chronicle.filter(type=EventType.RESOURCE_DEPLETED)


def test_unowned_and_empty_tiles_do_not_extract() -> None:
    """Нейтральные тайлы и тайлы без ресурсов не добывают."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.NONE},
            1: {"resource_type": ResourceType.FOOD, "resource_amount": 10.0},
        },
    )

    updated, _ = run_rule(state)

    assert updated.factions[0].food_stockpile == 0.0
    assert updated.map.tiles[1].resource_depletion == 0.0


def test_extraction_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковую добычу."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.FOOD,
                "resource_amount": 7.0,
                "resource_depletion": 50.0,
            }
        },
        seed=4,
    )

    first, _ = run_rule(state)
    second, _ = run_rule(state)

    assert first.snapshot_hash() == second.snapshot_hash()
