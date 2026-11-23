"""Тесты конфигурации и снимка мира."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState


def make_map(size: int = 4, population: int = 10) -> WorldMap:
    """Создаёт квадратную карту с однородными тайлами."""
    tiles = tuple(
        RegionData(
            id=index,
            x=index % size,
            y=index // size,
            biome=Biome.PLAINS,
            fertility=50.0,
            elevation=100.0,
            population=population,
            population_capacity=100,
        )
        for index in range(size * size)
    )
    return WorldMap(size=size, tiles=tiles)


def make_state(**config_overrides: object) -> WorldState:
    """Создаёт снимок мира на нулевом году."""
    config = WorldConfig.model_validate({"seed": 42, "size": 4, **config_overrides})
    return WorldState(config=config, year=0, map=make_map(config.size))


def test_config_defaults() -> None:
    """У конфигурации осмысленные значения по умолчанию."""
    config = WorldConfig(seed=42, size=8)

    assert config.initial_factions == 0
    assert config.aggression == 0.5
    assert config.growth_rate == 0.02
    assert config.plague_chance == 0.01
    assert config.magic_level == 0.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("size", 3),
        ("size", 513),
        ("initial_factions", -1),
        ("initial_factions", 5),
        ("aggression", -0.1),
        ("aggression", 1.1),
        ("growth_rate", -0.01),
        ("plague_chance", 1.5),
        ("magic_level", -0.5),
    ],
)
def test_config_validation(field: str, value: object) -> None:
    """Недопустимые параметры конфигурации отклоняются."""
    with pytest.raises(ValidationError):
        WorldConfig.model_validate({"seed": 1, "size": 8, **{field: value}})


def test_config_is_frozen() -> None:
    """Конфигурация неизменяема."""
    config = WorldConfig(seed=42, size=8)

    with pytest.raises(ValidationError):
        config.seed = 1  # type: ignore[misc]


def test_state_is_frozen() -> None:
    """Снимок мира неизменяем."""
    state = make_state()

    with pytest.raises(ValidationError):
        state.year = 5  # type: ignore[misc]


def test_evolve_returns_new_validated_state() -> None:
    """``evolve`` создаёт новый объект, не меняя исходный снимок."""
    state = make_state()

    updated = state.evolve(year=1)

    assert updated is not state
    assert state.year == 0
    assert updated.year == 1
    assert updated != state


def test_evolve_validates_changes() -> None:
    """Некорректные изменения отклоняются валидацией."""
    state = make_state()

    with pytest.raises(ValidationError):
        state.evolve(year=-1)


def test_evolve_can_replace_map() -> None:
    """Через ``evolve`` можно заменить карту целиком."""
    state = make_state()
    changed_map = make_map(size=4, population=20)

    updated = state.evolve(map=changed_map)

    assert updated.map.tiles[0].population == 20
    assert state.map.tiles[0].population == 10


def test_snapshot_hash_is_stable() -> None:
    """Одинаковые снимки дают одинаковый хеш."""
    first = make_state()
    second = make_state()

    assert first.snapshot_hash() == second.snapshot_hash()
    assert len(first.snapshot_hash()) == 64
    int(first.snapshot_hash(), 16)


def test_snapshot_hash_changes_with_content() -> None:
    """Хеш меняется при изменении населения, года или конфигурации."""
    state = make_state()

    assert state.evolve(year=1).snapshot_hash() != state.snapshot_hash()
    assert state.evolve(map=make_map(size=4, population=99)).snapshot_hash() != (
        state.snapshot_hash()
    )
    assert (
        state.evolve(config=state.config.model_copy(update={"seed": 43})).snapshot_hash()
        != state.snapshot_hash()
    )


def test_json_round_trip() -> None:
    """Снимок переживает сериализацию в JSON и обратно."""
    state = make_state()
    payload = state.to_json()
    restored = WorldState.from_json(payload)

    assert restored == state
    assert restored.snapshot_hash() == state.snapshot_hash()
    assert restored.config.seed == 42


def test_snapshot_hash_is_stable_across_processes() -> None:
    """Хеш одинаков при расчёте в отдельном процессе."""
    state = make_state()
    code = (
        "import sys\n"
        "from worldsim.core.state import WorldState\n"
        "print(WorldState.from_json(sys.argv[1]).snapshot_hash())\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code, state.to_json()],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == state.snapshot_hash()
