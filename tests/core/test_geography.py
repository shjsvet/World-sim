"""Тесты моделей карты."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.geography import (
    CITY_POPULATION_THRESHOLD,
    CITY_URBANIZATION_THRESHOLD,
    Biome,
    ClimateZone,
    RegionData,
    ResourceType,
    WorldMap,
)


def make_tile(index: int, size: int = 3, **overrides: object) -> RegionData:
    """Создаёт тайл с координатами из плоского индекса сетки."""
    payload: dict[str, object] = {
        "id": index,
        "x": index % size,
        "y": index // size,
        "biome": Biome.PLAINS,
        "fertility": 50.0,
        "elevation": 100.0,
        "population": 10,
        "population_capacity": 100,
    }
    payload.update(overrides)
    return RegionData.model_validate(payload)


def make_map(size: int = 3, **overrides: object) -> WorldMap:
    """Создаёт квадратную карту с однородными тайлами."""
    tiles = tuple(make_tile(index, size, **overrides) for index in range(size * size))
    return WorldMap(size=size, tiles=tiles)


def test_biome_properties() -> None:
    """Водой считается только океан, характеристики биомов осмысленны."""
    assert Biome.OCEAN.is_water is True
    assert all(not biome.is_water for biome in Biome if biome is not Biome.OCEAN)

    assert Biome.DESERT.base_fertility == 10.0
    assert Biome.PLAINS.base_fertility == 80.0
    assert Biome.MOUNTAINS.base_elevation > Biome.PLAINS.base_elevation
    assert Biome.MOUNTAINS.defense_bonus > Biome.PLAINS.defense_bonus
    assert Biome.MOUNTAINS.movement_cost > Biome.PLAINS.movement_cost
    assert Biome.FOREST.food_modifier < Biome.PLAINS.food_modifier

    for biome in Biome:
        assert biome.color.startswith("#")
        assert len(biome.color) == 7
        assert biome.emoji


def test_tile_defaults() -> None:
    """У тайла корректные значения по умолчанию."""
    tile = make_tile(0)

    assert tile.is_land is True
    assert tile.has_river is False
    assert tile.climate_zone is ClimateZone.TEMPERATE
    assert tile.resource_type is ResourceType.NONE
    assert tile.resource_amount == 0.0
    assert tile.resource_depletion == 0.0
    assert tile.infrastructure == 0.0
    assert tile.culture is None
    assert tile.happiness == 50.0
    assert tile.urbanization == 0.0
    assert tile.owner_id is None
    assert tile.army_presence == 0
    assert tile.fortification == 0.0
    assert tile.unrest == 0.0
    assert tile.assimilation == 0.0
    assert tile.mana_density == 0
    assert tile.mana_regeneration == 0
    assert tile.ley_line is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fertility", 101.0),
        ("fertility", -1.0),
        ("happiness", -1.0),
        ("unrest", 101.0),
        ("elevation", 9001.0),
        ("assimilation", 1.1),
        ("population", -1),
        ("population_capacity", -1),
        ("infrastructure", 101.0),
        ("mana_density", 101),
        ("culture", ""),
        ("army_presence", -1),
        ("fortification", -0.1),
        ("urbanization", 100.1),
        ("owner_id", -2),
    ],
)
def test_tile_validation(field: str, value: object) -> None:
    """Недопустимые значения полей отклоняются валидацией."""
    with pytest.raises(ValidationError):
        make_tile(0, **{field: value})


def test_tile_is_frozen() -> None:
    """Тайл неизменяем после создания."""
    tile = make_tile(0)

    with pytest.raises(ValidationError):
        tile.population = 5  # type: ignore[misc]


def test_is_city_thresholds() -> None:
    """Город появляется только при населении больше порога и урбанизации не ниже 50."""
    assert CITY_POPULATION_THRESHOLD == 1000
    assert CITY_URBANIZATION_THRESHOLD == 50.0
    assert make_tile(0, population=1000, urbanization=50.0).is_city is False
    assert make_tile(0, population=1001, urbanization=50.0).is_city is True
    assert make_tile(0, population=5000, urbanization=49.9).is_city is False
    assert make_tile(0, population=5000, urbanization=50.0).is_city is True


def test_defense_multiplier() -> None:
    """Фортификация и биом усиливают защиту тайла."""
    assert make_tile(0).defense_multiplier() == pytest.approx(1.0)
    assert make_tile(0, fortification=100.0).defense_multiplier() == pytest.approx(1.5)
    assert make_tile(0, biome=Biome.MOUNTAINS).defense_multiplier() == pytest.approx(1.5)


def test_food_output() -> None:
    """Производство еды учитывает реку, инфраструктуру и биом."""
    base = make_tile(0, population=100, fertility=80.0)
    assert base.food_output() == pytest.approx(80.0)

    river = make_tile(0, population=100, fertility=80.0, has_river=True)
    assert river.food_output() == pytest.approx(88.0)

    improved = make_tile(0, population=100, fertility=80.0, infrastructure=100.0)
    assert improved.food_output() == pytest.approx(120.0)

    forest = make_tile(0, population=100, fertility=80.0, biome=Biome.FOREST)
    assert forest.food_output() == pytest.approx(56.0)

    empty = make_tile(0, population=0, fertility=80.0)
    assert empty.food_output() == 0.0


def test_map_access() -> None:
    """Доступ по координатам, id и центру карты."""
    world = make_map(3)

    assert world.at(0, 0).id == 0
    assert world.at(2, 2).id == 8
    assert world.by_id(4).x == 1
    assert world.by_id(4).y == 1
    assert world.center().id == 4

    with pytest.raises(IndexError):
        world.at(3, 0)
    with pytest.raises(IndexError):
        world.by_id(9)


def test_neighbors_order_and_bounds() -> None:
    """Соседи возвращаются в порядке N, E, S, W и только в границах карты."""
    world = make_map(3)

    assert [tile.id for tile in world.neighbors(0, 0)] == [1, 3]
    assert [tile.id for tile in world.neighbors(1, 0)] == [2, 4, 0]
    assert [tile.id for tile in world.neighbors(1, 1)] == [1, 5, 7, 3]


def test_diagonal_neighbors() -> None:
    """Диагональные соседи добавляются после основных."""
    world = make_map(3)

    assert [tile.id for tile in world.neighbors(0, 0, diagonal=True)] == [1, 3, 4]
    assert [tile.id for tile in world.neighbors(1, 1, diagonal=True)] == [1, 5, 7, 3, 2, 8, 6, 0]


def test_map_filters() -> None:
    """Суша, города и владельцы фильтруются корректно."""
    cities = make_map(3, population=2000, urbanization=60.0)
    assert len(cities.cities()) == 9

    ocean = make_map(3, biome=Biome.OCEAN)
    assert ocean.land_tiles() == ()

    tiles = tuple(make_tile(index, 3, owner_id=1 if index % 2 == 0 else None) for index in range(9))
    mixed = WorldMap(size=3, tiles=tiles)
    assert len(mixed.tiles_with(1)) == 5
    assert len(mixed.tiles_with(None)) == 4
    assert mixed.tiles_with(2) == ()


def test_map_validation() -> None:
    """Некорректная сетка отклоняется."""
    with pytest.raises(ValidationError):
        WorldMap(size=3, tiles=make_map(2).tiles)

    bad_coords = tuple(make_tile(index, 3, x=(index % 3) + 1) for index in range(9))
    with pytest.raises(ValidationError):
        WorldMap(size=3, tiles=bad_coords)

    bad_ids = tuple(make_tile(index + 1, 3) for index in range(9))
    with pytest.raises(ValidationError):
        WorldMap(size=3, tiles=bad_ids)

    with pytest.raises(ValidationError):
        WorldMap(size=0, tiles=())


def test_map_json_round_trip() -> None:
    """Карта переживает сериализацию в JSON и обратно."""
    world = make_map(3)
    payload = world.model_dump_json()
    restored = WorldMap.model_validate_json(payload)

    assert restored == world
    assert restored.tiles[4].biome is Biome.PLAINS
