"""Тесты процедурной генерации мира."""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from worldsim.core.geography import Biome, ResourceType
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig
from worldsim.generator.terrain import generate_map
from worldsim.generator.world import create_world


def make_config(seed: int = 42, size: int = 32) -> WorldConfig:
    """Конфигурация мира для тестов."""
    return WorldConfig(seed=seed, size=size)


def test_create_world_is_deterministic() -> None:
    """Одинаковый сид даёт идентичный снимок мира."""
    first = create_world(make_config())
    second = create_world(make_config())

    assert first.year == 0
    assert first.snapshot_hash() == second.snapshot_hash()


def test_different_seeds_produce_different_maps() -> None:
    """Разные сиды дают разные карты."""
    first = create_world(make_config(seed=1))
    second = create_world(make_config(seed=2))

    assert first.snapshot_hash() != second.snapshot_hash()


def test_generate_map_matches_world_creation() -> None:
    """``create_world`` использует тот же генератор, что и ``generate_map``."""
    config = make_config(seed=7, size=16)

    assert create_world(config).map == generate_map(config, Rng(config.seed))


def test_biomes_and_terrain_variety() -> None:
    """На большой карте достаточно биомов, рек, ресурсов и маны."""
    world = create_world(make_config(size=64))
    tiles = world.map.tiles

    biomes = {tile.biome for tile in tiles}
    assert len(biomes) >= 4
    assert any(tile.has_river for tile in tiles)
    assert any(tile.resource_type is not ResourceType.NONE for tile in tiles)
    assert any(tile.mana_density > 0 for tile in tiles)
    assert any(tile.mana_regeneration > 0 for tile in tiles)


def test_water_tiles_are_empty() -> None:
    """У воды нет населения, владельца, рек и маны."""
    world = create_world(make_config(size=32))
    water = [tile for tile in world.map.tiles if tile.biome is Biome.OCEAN]

    assert water
    for tile in water:
        assert tile.population == 0
        assert tile.population_capacity == 0
        assert tile.fertility == 0.0
        assert tile.owner_id is None
        assert tile.has_river is False
        assert tile.mana_density == 0
        assert tile.mana_regeneration == 0


def test_tile_ranges() -> None:
    """Все значения тайлов остаются в допустимых диапазонах."""
    world = create_world(make_config(size=32))

    for tile in world.map.tiles:
        assert 0.0 <= tile.fertility <= 100.0
        assert 0.0 <= tile.elevation <= 9000.0
        assert 0.0 <= tile.happiness <= 100.0
        assert 0.0 <= tile.urbanization <= 100.0
        assert 0 <= tile.mana_density <= 100
        assert tile.mana_regeneration >= 0
        assert tile.population >= 0
        assert tile.population_capacity >= 0
        assert tile.resource_amount >= 0.0
        assert tile.resource_depletion >= 0.0


def test_land_capacity_formula() -> None:
    """Ёмкость суши считается по формуле генератора."""
    world = create_world(make_config(size=32))

    for tile in world.map.tiles:
        if tile.biome is Biome.OCEAN:
            continue
        assert tile.population_capacity == int(tile.fertility * 5 + 20)
        assert tile.population <= tile.population_capacity


def test_coasts_touch_ocean() -> None:
    """Каждый тайл побережья граничит с океаном."""
    world = create_world(make_config(size=32))

    for tile in world.map.tiles:
        if tile.biome is not Biome.COAST:
            continue
        neighbors = world.map.neighbors(tile.x, tile.y)
        assert any(neighbor.biome is Biome.OCEAN for neighbor in neighbors)


def test_ley_lines_are_rare_and_powerful() -> None:
    """Лей-линии редки, лежат на суше и дают максимум маны."""
    world = create_world(make_config(size=64))
    ley_lines = [tile for tile in world.map.tiles if tile.ley_line]

    assert len(ley_lines) == 5
    for tile in ley_lines:
        assert tile.biome is not Biome.OCEAN
        assert tile.mana_density == 100
        assert tile.mana_regeneration == 50


@pytest.mark.slow
def test_generation_performance() -> None:
    """Карта 128×128 генерируется быстрее двух секунд."""
    config = make_config(size=128)

    started = time.perf_counter()
    create_world(config)
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0


def test_determinism_across_processes() -> None:
    """Хеш сгенерированного мира совпадает в отдельном процессе."""
    config = make_config(seed=42, size=16)
    code = (
        "from worldsim.core.state import WorldConfig\n"
        "from worldsim.generator.world import create_world\n"
        "print(create_world(WorldConfig(seed=42, size=16)).snapshot_hash())\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == create_world(config).snapshot_hash()
