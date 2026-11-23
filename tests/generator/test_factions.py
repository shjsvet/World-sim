"""Тесты генератора стартовых фракций и территорий."""

from __future__ import annotations

import pytest

from worldsim.core.faction import MagicSchool
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.factions import CULTURES, assign_territories, spawn_factions
from worldsim.generator.world import create_world

_MAGIC_BY_CULTURE: dict[str, tuple[int, tuple[MagicSchool, ...]]] = {
    "Люди": (50, (MagicSchool.NATURE,)),
    "Эльфы": (90, (MagicSchool.NATURE, MagicSchool.ICE)),
    "Орки": (40, (MagicSchool.FIRE,)),
    "Гномы": (20, (MagicSchool.FIRE,)),
    "Нежить": (70, (MagicSchool.NECROMANCY,)),
}


def make_world(
    *,
    size: int = 32,
    seed: int = 42,
    factions: int = 2,
    aggression: float = 0.5,
) -> WorldState:
    """Создаёт мир с заданным числом фракций."""
    config = WorldConfig(
        seed=seed,
        size=size,
        initial_factions=factions,
        aggression=aggression,
    )
    return create_world(config)


def test_zero_factions_leaves_map_neutral() -> None:
    """При нуле фракций вся карта нейтральна."""
    world = make_world(factions=0)

    assert world.factions == ()
    assert all(tile.owner_id is None for tile in world.map.tiles)


def test_default_config_creates_two_factions() -> None:
    """По умолчанию мир создаётся с двумя фракциями."""
    world = create_world(WorldConfig(seed=42, size=32))

    assert len(world.factions) == 2


@pytest.mark.parametrize("count", [2, 3, 4])
def test_faction_count_matches_config(count: int) -> None:
    """Число фракций соответствует конфигурации."""
    world = make_world(factions=count)

    assert len(world.factions) == count


def test_names_colors_and_cultures_are_unique() -> None:
    """Имена, цвета и культуры фракций не повторяются."""
    world = make_world(factions=4)

    assert len({faction.name for faction in world.factions}) == 4
    assert len({faction.color for faction in world.factions}) == 4
    assert len({faction.culture for faction in world.factions}) == 4
    for faction in world.factions:
        assert faction.culture in CULTURES
        assert faction.color.startswith("#")
        assert len(faction.color) == 7


def test_capitals_are_land_and_owned() -> None:
    """Столицы стоят на суше и принадлежат своим фракциям."""
    world = make_world(factions=4)
    coordinates = set()

    for faction in world.factions:
        assert faction.capital_tile_id is not None
        capital = world.map.by_id(faction.capital_tile_id)
        assert capital.is_land
        assert capital.owner_id == faction.id
        coordinates.add((capital.x, capital.y))

    assert len(coordinates) == 4


def test_every_faction_has_territory() -> None:
    """У каждой фракции есть хотя бы один тайл."""
    world = make_world(factions=4)

    for faction in world.factions:
        owned = [tile for tile in world.map.tiles if tile.owner_id == faction.id]
        assert owned


def test_owners_are_valid_and_land_only() -> None:
    """Владельцы тайлов существуют, а вода остаётся нейтральной."""
    world = make_world(size=64, factions=4)
    faction_ids = {faction.id for faction in world.factions}

    for tile in world.map.tiles:
        if tile.owner_id is not None:
            assert tile.owner_id in faction_ids
            assert tile.is_land
        if tile.biome.is_water:
            assert tile.owner_id is None


def test_owned_tiles_adopt_faction_culture() -> None:
    """Культура занятых тайлов совпадает с культурой владельца."""
    world = make_world(factions=4)
    culture_by_id = {faction.id: faction.culture for faction in world.factions}

    for tile in world.map.tiles:
        if tile.owner_id is not None:
            assert tile.culture == culture_by_id[tile.owner_id]


def test_starting_values() -> None:
    """Стартовые экономические и боевые значения соответствуют ТЗ."""
    world = make_world(factions=4)

    for faction in world.factions:
        assert faction.treasury == 100.0
        assert faction.food_stockpile == 200.0
        assert faction.tech_level == 1.0
        assert faction.morale == 0.8
        assert faction.mana_pool == 0
        assert faction.army_size >= 1.0
        assert 0.0 <= faction.aggressiveness <= 1.0


def test_resources_and_magic_by_culture() -> None:
    """Ресурсы, склонность и школы задаются культурой."""
    world = make_world(factions=4)

    for faction in world.factions:
        affinity, schools = _MAGIC_BY_CULTURE[faction.culture]
        assert faction.magic_affinity == affinity
        assert faction.magic_schools == schools
        assert faction.resources
        assert all(amount >= 0 for amount in faction.resources.values())

    resources_by_culture = {faction.culture: faction.resources for faction in world.factions}
    if "Эльфы" in resources_by_culture:
        assert resources_by_culture["Эльфы"] == {"mana_crystals": 10.0}
    if "Орки" in resources_by_culture:
        assert resources_by_culture["Орки"] == {"iron": 500.0}
    if "Гномы" in resources_by_culture:
        assert resources_by_culture["Гномы"] == {"iron": 300.0, "gold": 50.0}
    if "Люди" in resources_by_culture:
        assert resources_by_culture["Люди"] == {"gold": 100.0}


def test_aggressiveness_uses_config_and_ideology() -> None:
    """Агрессивность = агрессия мира плюс поправка идеологии в границах [0, 1]."""
    world = make_world(factions=3, aggression=0.0)

    for faction in world.factions:
        expected = min(1.0, max(0.0, faction.ideology.aggression_bonus))
        assert faction.aggressiveness == pytest.approx(expected)


def test_determinism_for_same_seed() -> None:
    """Одинаковый сид даёт одинаковые фракции и границы."""
    first = make_world(seed=7, factions=4)
    second = make_world(seed=7, factions=4)

    assert first.snapshot_hash() == second.snapshot_hash()
    assert [
        (faction.name, faction.color, faction.culture, faction.resources)
        for faction in first.factions
    ] == [
        (faction.name, faction.color, faction.culture, faction.resources)
        for faction in second.factions
    ]


def test_different_seeds_give_different_worlds() -> None:
    """Разные сиды дают разные миры."""
    assert make_world(seed=1).snapshot_hash() != make_world(seed=2).snapshot_hash()


def test_spawn_and_assign_helpers() -> None:
    """``spawn_factions`` и ``assign_territories`` работают вместе."""
    from worldsim.core.rng import Rng
    from worldsim.generator.terrain import generate_map

    config = WorldConfig(seed=42, size=24, initial_factions=3)
    base_map = generate_map(config, Rng(config.seed))
    factions = spawn_factions(base_map, config, Rng(config.seed))
    claimed = assign_territories(base_map, factions)

    assert len(factions) == 3
    assert any(tile.owner_id is not None for tile in claimed.tiles)
    assert all(tile.owner_id is None for tile in base_map.tiles)
