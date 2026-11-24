"""Тесты моделей культуры и религии."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.culture import Culture, Religion
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState


def make_faction(faction_id: int = 0, *, culture: str = "Люди", capital: int = 0) -> Faction:
    """Создаёт фракцию с заданной культурой."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture=culture,
        capital_tile_id=capital,
    )


def make_state(
    *,
    cultures: tuple[Culture, ...] = (),
    religions: tuple[Religion, ...] = (),
    factions: tuple[Faction, ...] = (),
    tile_updates: dict[int, dict[str, object]] | None = None,
) -> WorldState:
    """Создаёт небольшой мир с культурами."""
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
        if tile_updates is not None:
            data.update(tile_updates.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        cultures=cultures,
        religions=religions,
    )


def test_culture_and_religion_models() -> None:
    """Модели культуры и религии валидируют поля."""
    culture = Culture(id=0, name="Люди", traits=("торговля",))
    religion = Religion(id=0, name="Свет", culture_id=0, zeal=0.8)

    assert culture.traits == ("торговля",)
    assert religion.culture_id == 0
    with pytest.raises(ValidationError):
        Religion(id=1, name="Тьма", culture_id=0, zeal=1.5)


def test_valid_references() -> None:
    """Корректные ссылки на культуры и религии проходят валидацию."""
    culture = Culture(id=0, name="Люди")
    religion = Religion(id=0, name="Свет", culture_id=0, zeal=0.5)
    state = make_state(
        cultures=(culture,),
        religions=(religion,),
        factions=(make_faction(),),
        tile_updates={0: {"owner_id": 0, "culture_id": 0, "religion_id": 0}},
    )

    assert state.map.tiles[0].culture_id == 0
    assert state.cultures == (culture,)


def test_faction_culture_matches_case_insensitive() -> None:
    """Культура фракции сравнивается с Culture.name без учёта регистра."""
    state = make_state(
        cultures=(Culture(id=0, name="Люди"),),
        factions=(make_faction(culture="люди"),),
        tile_updates={0: {"owner_id": 0}},
    )

    assert state.factions[0].culture == "люди"


def test_faction_culture_must_exist() -> None:
    """При наличии культур неизвестная культура фракции отклоняется."""
    with pytest.raises(ValidationError):
        make_state(
            cultures=(Culture(id=0, name="Люди"),),
            factions=(make_faction(culture="Орки"),),
            tile_updates={0: {"owner_id": 0}},
        )


def test_unknown_tile_culture_is_rejected() -> None:
    """Тайл не может ссылаться на несуществующую культуру."""
    with pytest.raises(ValidationError):
        make_state(
            cultures=(Culture(id=0, name="Люди"),),
            factions=(make_faction(),),
            tile_updates={0: {"owner_id": 0, "culture_id": 5}},
        )


def test_unknown_tile_religion_is_rejected() -> None:
    """Тайл не может ссылаться на несуществующую религию."""
    with pytest.raises(ValidationError):
        make_state(
            cultures=(Culture(id=0, name="Люди"),),
            factions=(make_faction(),),
            tile_updates={0: {"owner_id": 0, "religion_id": 3}},
        )


def test_religion_requires_known_culture() -> None:
    """Религия обязана ссылаться на существующую культуру."""
    with pytest.raises(ValidationError):
        make_state(
            cultures=(Culture(id=0, name="Люди"),),
            religions=(Religion(id=0, name="Свет", culture_id=9),),
        )


def test_world_without_cultures_is_valid() -> None:
    """Обратная совместимость: мир без культур и религий валиден."""
    state = make_state(
        factions=(make_faction(culture="Что угодно"),),
        tile_updates={0: {"owner_id": 0}},
    )

    assert state.cultures == ()
    assert state.religions == ()
