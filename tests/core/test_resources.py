"""Тесты модели торгового маршрута."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.resources import TradeRoute
from worldsim.core.state import WorldConfig, WorldState


def make_faction(faction_id: int = 0, *, capital: int = 0) -> Faction:
    """Создаёт фракцию для тестов маршрутов."""
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
    routes: tuple[TradeRoute, ...] = (),
    owners: dict[int, int] | None = None,
) -> WorldState:
    """Создаёт мир с маршрутами."""
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
        if owners is not None and index in owners:
            data["owner_id"] = owners[index]
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        trade_routes=routes,
    )


def test_valid_route() -> None:
    """Корректный маршрут проходит валидацию."""
    route = TradeRoute(from_tile=0, to_tile=1, resource=ResourceType.FOOD, capacity=2.5)

    assert route.from_tile == 0
    assert route.resource is ResourceType.FOOD


def test_route_to_itself_is_rejected() -> None:
    """Маршрут в тот же тайл запрещён."""
    with pytest.raises(ValidationError):
        TradeRoute(from_tile=1, to_tile=1, resource=ResourceType.FOOD, capacity=1.0)


def test_route_without_resource_is_rejected() -> None:
    """Маршрут не может перевозить NONE."""
    with pytest.raises(ValidationError):
        TradeRoute(from_tile=0, to_tile=1, resource=ResourceType.NONE, capacity=1.0)


def test_negative_capacity_is_rejected() -> None:
    """Отрицательная ёмкость запрещена."""
    with pytest.raises(ValidationError):
        TradeRoute(from_tile=0, to_tile=1, resource=ResourceType.FOOD, capacity=-1.0)


def test_state_accepts_valid_routes() -> None:
    """Снимок принимает маршрут между соседними тайлами."""
    route = TradeRoute(from_tile=0, to_tile=1, resource=ResourceType.FOOD, capacity=1.0)
    state = make_state(
        factions=(make_faction(),),
        routes=(route,),
        owners={0: 0, 1: 0},
    )

    assert state.trade_routes == (route,)


def test_route_outside_map_is_rejected() -> None:
    """Маршрут на тайл вне карты отклоняется."""
    route = TradeRoute(from_tile=0, to_tile=99, resource=ResourceType.FOOD, capacity=1.0)

    with pytest.raises(ValidationError):
        make_state(factions=(make_faction(),), routes=(route,), owners={0: 0})


def test_duplicate_routes_are_rejected() -> None:
    """Дубли маршрутов отклоняются."""
    route = TradeRoute(from_tile=0, to_tile=1, resource=ResourceType.FOOD, capacity=1.0)
    reverse = TradeRoute(from_tile=1, to_tile=0, resource=ResourceType.FOOD, capacity=2.0)

    with pytest.raises(ValidationError):
        make_state(
            factions=(make_faction(),),
            routes=(route, reverse),
            owners={0: 0, 1: 0},
        )


def test_old_json_without_routes_is_valid() -> None:
    """Снимок без поля trade_routes читается (обратная совместимость)."""
    state = make_state(factions=(make_faction(),), owners={0: 0})
    payload = state.model_dump()
    payload.pop("trade_routes")

    restored = WorldState.model_validate(payload)

    assert restored.trade_routes == ()
