"""Тесты торговых маршрутов."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.trade import TradeRule


def make_faction(
    faction_id: int = 0,
    *,
    capital: int = 0,
) -> Faction:
    """Создаёт торговую фракцию."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MERCANTILE,
        culture="Люди",
        capital_tile_id=capital,
    )


def make_state(
    *,
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    wars: tuple[War, ...] = (),
    seed: int = 1,
) -> WorldState:
    """Создаёт карту с фракциями и войнами."""
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
            "population_capacity": 1_000,
        }
        data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=seed, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        wars=wars,
    )


def run_rule(state: WorldState) -> tuple[WorldState, Chronicle]:
    """Выполняет шаг с правилом торговли."""
    chronicle = Chronicle()
    engine = SimulationEngine([TradeRule()], chronicle, initial_state=state)
    return engine.step(), chronicle


def test_route_between_neighbours() -> None:
    """Маршрут строится только между соседними фракциями."""
    first = make_faction(0)
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.FOOD},
            1: {"owner_id": 1, "resource_type": ResourceType.GOLD},
        },
    )

    updated, chronicle = run_rule(state)

    assert len(updated.trade_routes) == 1
    route = updated.trade_routes[0]
    assert {route.from_tile, route.to_tile} == {0, 1}
    assert route.resource is ResourceType.FOOD
    assert chronicle.filter(type=EventType.TRADE)


def test_non_neighbours_do_not_trade() -> None:
    """Удалённые тайлы не связываются маршрутом."""
    first = make_faction(0)
    second = make_faction(1, capital=5)
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.FOOD},
            5: {"owner_id": 1, "resource_type": ResourceType.GOLD},
        },
    )

    updated, _ = run_rule(state)

    assert updated.trade_routes == ()


def test_war_breaks_routes() -> None:
    """Война рвёт торговые маршруты."""
    first = make_faction(0)
    second = make_faction(1, capital=1)
    war = War(
        id=0,
        attacker_id=0,
        defender_id=1,
        started_year=0,
        battles=1,
        active=True,
    )
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.FOOD},
            1: {"owner_id": 1, "resource_type": ResourceType.GOLD},
        },
        wars=(war,),
    )

    updated, chronicle = run_rule(state)

    assert updated.trade_routes == ()
    assert chronicle.filter(type=EventType.TRADE) == ()
    assert updated.factions[0].treasury == 0.0


def test_truce_blocks_routes() -> None:
    """Перемирие запрещает торговлю."""
    first = make_faction(0)
    second = make_faction(1, capital=1)
    truce = War(
        id=0,
        attacker_id=0,
        defender_id=1,
        started_year=0,
        battles=1,
        active=False,
        truce_until_year=10,
    )
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.FOOD},
            1: {"owner_id": 1, "resource_type": ResourceType.GOLD},
        },
        wars=(truce,),
    )

    updated, _ = run_rule(state)

    assert updated.trade_routes == ()


def test_trade_income_is_positive() -> None:
    """Обе фракции получают доход в казну и ресурсы."""
    first = make_faction(0)
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.WOOD},
            1: {"owner_id": 1, "resource_type": ResourceType.WOOD},
        },
    )

    updated, _ = run_rule(state)

    assert updated.factions[0].treasury > 0.0
    assert updated.factions[1].treasury > 0.0
    assert updated.factions[0].resources["wood"] > 0.0
    assert updated.factions[1].resources["wood"] > 0.0


def test_trade_is_deterministic() -> None:
    """Одинаковый сид даёт одинаковые маршруты."""
    first = make_faction(0)
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        overrides={
            0: {"owner_id": 0, "resource_type": ResourceType.FOOD},
            1: {"owner_id": 1, "resource_type": ResourceType.GOLD},
        },
        seed=6,
    )

    first_run, _ = run_rule(state)
    second_run, _ = run_rule(state)

    assert first_run.snapshot_hash() == second_run.snapshot_hash()
