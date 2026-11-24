"""Тесты модели магической академии."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.faction import Faction, Ideology, MagicSchool
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.magic import MagicAcademy
from worldsim.core.state import WorldConfig, WorldState


def make_faction(faction_id: int = 0, *, capital: int = 0) -> Faction:
    """Создаёт фракцию для тестов магии."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.SCHOLARLY,
        culture="Люди",
        capital_tile_id=capital,
    )


def make_state(
    *,
    factions: tuple[Faction, ...],
    academies: tuple[MagicAcademy, ...] = (),
    owners: dict[int, int] | None = None,
    mana_density: dict[int, int] | None = None,
) -> WorldState:
    """Создаёт мир с академиями."""
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
            "mana_density": (mana_density or {}).get(index, 60),
        }
        if owners is not None and index in owners:
            data["owner_id"] = owners[index]
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        academies=academies,
    )


def test_academy_model() -> None:
    """Модель академии валидирует поля."""
    academy = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.FIRE,
        level=2,
        founded_year=5,
    )

    assert academy.level == 2
    with pytest.raises(ValidationError):
        MagicAcademy(
            id=1,
            tile_id=0,
            faction_id=0,
            school=MagicSchool.FIRE,
            level=0,
            founded_year=0,
        )


def test_valid_academy_in_state() -> None:
    """Академия на тайле фракции с достаточной маной валидна."""
    academy = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.ICE,
        founded_year=0,
    )
    state = make_state(
        factions=(make_faction(),),
        academies=(academy,),
        owners={0: 0},
    )

    assert state.academies == (academy,)


def test_academy_requires_owner() -> None:
    """Академия должна стоять на тайле своей фракции."""
    academy = MagicAcademy(
        id=0,
        tile_id=1,
        faction_id=0,
        school=MagicSchool.FIRE,
        founded_year=0,
    )

    with pytest.raises(ValidationError):
        make_state(
            factions=(make_faction(),),
            academies=(academy,),
            owners={0: 0},
        )


def test_academy_requires_mana_density() -> None:
    """Для академии нужна плотность маны не ниже 50."""
    academy = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.FIRE,
        founded_year=0,
    )

    with pytest.raises(ValidationError):
        make_state(
            factions=(make_faction(),),
            academies=(academy,),
            owners={0: 0},
            mana_density={0: 40},
        )


def test_one_academy_per_tile() -> None:
    """На одном тайле не может быть двух академий."""
    first = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.FIRE,
        founded_year=0,
    )
    second = MagicAcademy(
        id=1,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.ICE,
        founded_year=1,
    )

    with pytest.raises(ValidationError):
        make_state(
            factions=(make_faction(),),
            academies=(first, second),
            owners={0: 0},
        )


def test_academy_unknown_faction_is_rejected() -> None:
    """Академия несуществующей фракции отклоняется."""
    academy = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=5,
        school=MagicSchool.FIRE,
        founded_year=0,
    )

    with pytest.raises(ValidationError):
        make_state(factions=(make_faction(),), academies=(academy,), owners={0: 0})
