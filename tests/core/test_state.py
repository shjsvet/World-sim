"""Тесты конфигурации и снимка мира."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState


def make_map(
    size: int = 4,
    population: int = 10,
    owner_id: int | None = None,
    army_presence: int = 0,
    biome: Biome = Biome.PLAINS,
) -> WorldMap:
    """Создаёт квадратную карту с однородными тайлами."""
    tiles = tuple(
        RegionData(
            id=index,
            x=index % size,
            y=index // size,
            biome=biome,
            fertility=50.0,
            elevation=100.0,
            population=population,
            population_capacity=100,
            owner_id=owner_id,
            army_presence=army_presence,
        )
        for index in range(size * size)
    )
    return WorldMap(size=size, tiles=tiles)


def make_state(
    factions: tuple[Faction, ...] = (),
    owner_id: int | None = None,
    army_presence: int = 0,
    biome: Biome = Biome.PLAINS,
    **config_overrides: object,
) -> WorldState:
    """Создаёт снимок мира на нулевом году."""
    config = WorldConfig.model_validate({"seed": 42, "size": 4, **config_overrides})
    world_map = make_map(
        config.size,
        owner_id=owner_id,
        army_presence=army_presence,
        biome=biome,
    )
    return WorldState(config=config, year=0, map=world_map, factions=factions)


def make_faction(
    faction_id: int = 0,
    name: str = "Альянс",
    color: str = "#112233",
    capital_tile_id: int | None = 0,
    culture: str = "Люди",
) -> Faction:
    """Создаёт фракцию для проверки инвариантов мира."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture=culture,
        capital_tile_id=capital_tile_id,
    )


def test_config_defaults() -> None:
    """У конфигурации осмысленные значения по умолчанию."""
    config = WorldConfig(seed=42, size=8)

    assert config.initial_factions == 2
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


def test_state_accepts_factions_and_ownership() -> None:
    """Снимок принимает фракции и принадлежащие им тайлы."""
    faction = make_faction()
    state = make_state(factions=(faction,), owner_id=faction.id)

    assert state.factions == (faction,)
    assert all(tile.owner_id == faction.id for tile in state.map.tiles)


def test_duplicate_faction_ids_are_rejected() -> None:
    """Идентификаторы фракций уникальны."""
    first = make_faction()
    second = make_faction(name="Орда", color="#445566", capital_tile_id=None)

    with pytest.raises(ValidationError, match="уникальны"):
        make_state(factions=(first, second))


def test_duplicate_faction_names_are_rejected() -> None:
    """Имена фракций уникальны."""
    first = make_faction()
    second = make_faction(faction_id=1, color="#445566", capital_tile_id=None)

    with pytest.raises(ValidationError, match="имена"):
        make_state(factions=(first, second))


def test_duplicate_faction_colors_are_rejected() -> None:
    """Цвета фракций уникальны."""
    first = make_faction()
    second = make_faction(faction_id=1, name="Орда", capital_tile_id=None)

    with pytest.raises(ValidationError, match="цвета"):
        make_state(factions=(first, second))


def test_unknown_owner_is_rejected() -> None:
    """Тайл не может принадлежать несуществующей фракции."""
    with pytest.raises(ValidationError, match="несуществующей"):
        make_state(factions=(make_faction(),), owner_id=5)


def test_water_cannot_have_owner() -> None:
    """Вода не может принадлежать фракции."""
    faction = make_faction(capital_tile_id=None)

    with pytest.raises(ValidationError, match="водный"):
        make_state(factions=(faction,), owner_id=faction.id, biome=Biome.OCEAN)


def test_water_cannot_have_army() -> None:
    """На воде не может стоять армия."""
    with pytest.raises(ValidationError, match="армии"):
        make_state(biome=Biome.OCEAN, army_presence=5)


def test_army_requires_owner() -> None:
    """На нейтральном тайле армии быть не может."""
    with pytest.raises(ValidationError, match="нейтральном"):
        make_state(army_presence=5)


def test_capital_must_belong_to_faction() -> None:
    """Столица фракции должна принадлежать ей."""
    with pytest.raises(ValidationError, match="столица"):
        make_state(factions=(make_faction(),), owner_id=None)


def test_capital_outside_map_is_rejected() -> None:
    """Столица не может находиться вне карты."""
    faction = make_faction(capital_tile_id=999)

    with pytest.raises(ValidationError, match="вне карты"):
        make_state(factions=(faction,), owner_id=faction.id)


def test_snapshot_hash_includes_factions() -> None:
    """Хеш снимка учитывает фракции и владение."""
    plain = make_state()
    with_faction = make_state(factions=(make_faction(),), owner_id=0)

    assert plain.snapshot_hash() != with_faction.snapshot_hash()


def test_backward_compatible_json_without_factions() -> None:
    """Старый JSON без фракций и owner_id читается со значениями по умолчанию."""
    faction = make_faction()
    state = make_state(factions=(faction,), owner_id=faction.id)

    payload = state.model_dump()
    payload.pop("factions")
    for tile in payload["map"]["tiles"]:
        tile.pop("owner_id", None)
        tile.pop("army_presence", None)

    restored = WorldState.model_validate(payload)

    assert restored.factions == ()
    assert restored.map.tiles[0].owner_id is None
    assert restored.map.tiles[0].army_presence == 0
