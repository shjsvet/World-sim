"""Тесты модели фракции."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.faction import (
    CULTURE_CONFLICT_BASE,
    Faction,
    Ideology,
    MagicSchool,
    culture_conflict_factor,
)


def make_faction(**overrides: object) -> Faction:
    """Создаёт фракцию с минимально допустимыми значениями."""
    payload: dict[str, object] = {
        "id": 1,
        "name": "Эльдарион",
        "color": "#3366CC",
        "ideology": Ideology.MILITARIST,
        "culture": "Эльфы",
    }
    payload.update(overrides)
    return Faction.model_validate(payload)


def test_defaults() -> None:
    """У фракции осмысленные значения по умолчанию."""
    faction = make_faction()

    assert faction.capital_tile_id is None
    assert faction.aggressiveness == 0.5
    assert faction.treasury == 0.0
    assert faction.food_stockpile == 0.0
    assert faction.tech_level == 1.0
    assert faction.resources == {}
    assert faction.army_size == 0.0
    assert faction.morale == 0.8
    assert faction.mana_pool == 0
    assert faction.magic_affinity == 0
    assert faction.magic_schools == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("treasury", -1.0),
        ("food_stockpile", -1.0),
        ("tech_level", 11.0),
        ("culture", ""),
        ("name", "   "),
        ("color", "red"),
        ("color", "#12345"),
        ("color", "#GGGGGG"),
        ("resources", {"": 1.0}),
        ("resources", {"iron": -5.0}),
        ("magic_affinity", 101),
        ("morale", 1.1),
        ("aggressiveness", -0.1),
        ("mana_pool", -1),
        ("army_size", -1.0),
        ("capital_tile_id", -1),
    ],
)
def test_field_validation(field: str, value: object) -> None:
    """Недопустимые значения полей отклоняются."""
    with pytest.raises(ValidationError):
        make_faction(**{field: value})


def test_name_and_culture_are_trimmed() -> None:
    """Пробелы по краям имени и культуры убираются."""
    faction = make_faction(name="  Орда  ", culture="  Орки  ")

    assert faction.name == "Орда"
    assert faction.culture == "Орки"


def test_magic_affinity_requires_schools() -> None:
    """Склонность к магии без школ отклоняется."""
    with pytest.raises(ValidationError, match="магическая школа"):
        make_faction(magic_affinity=50)

    faction = make_faction(magic_affinity=50, magic_schools=(MagicSchool.FIRE,))
    assert faction.magic_affinity == 50


def test_duplicate_magic_schools_are_rejected() -> None:
    """Школы не должны повторяться."""
    with pytest.raises(ValidationError, match="повторяться"):
        make_faction(magic_schools=(MagicSchool.FIRE, MagicSchool.FIRE))


def test_faction_is_frozen() -> None:
    """Фракция неизменяема."""
    faction = make_faction()

    with pytest.raises(ValidationError):
        faction.morale = 0.1  # type: ignore[misc]


def test_military_power_formula() -> None:
    """Боевая мощь учитывает армию, технологии и идеологию."""
    faction = make_faction(army_size=100.0, tech_level=2.0)

    assert faction.military_power == pytest.approx(100.0 * 1.2 * 1.25)
    assert make_faction(army_size=0.0).military_power == 0.0

    mercantile = make_faction(army_size=100.0, tech_level=2.0, ideology=Ideology.MERCANTILE)
    assert faction.military_power > mercantile.military_power


def test_magic_power_formula() -> None:
    """Магическая мощь зависит от склонности, технологий и числа школ."""
    plain = make_faction(magic_affinity=0)
    assert plain.magic_power() == 0.0

    one_school = make_faction(
        magic_affinity=80,
        tech_level=2.0,
        magic_schools=(MagicSchool.FIRE,),
    )
    two_schools = make_faction(
        magic_affinity=80,
        tech_level=2.0,
        magic_schools=(MagicSchool.FIRE, MagicSchool.ICE),
    )

    assert one_school.magic_power() == pytest.approx(0.8 * 1.2 * 1.25)
    assert two_schools.magic_power() > one_school.magic_power()


def test_evolve_returns_new_faction_without_mutation() -> None:
    """``evolve`` создаёт новую фракцию и не меняет исходную."""
    faction = make_faction(resources={"iron": 10.0})
    updated = faction.evolve(morale=0.5, treasury=100.0)

    assert updated is not faction
    assert faction.morale == 0.8
    assert faction.treasury == 0.0
    assert updated.morale == 0.5
    assert updated.treasury == 100.0
    assert updated.id == faction.id


def test_evolve_copies_resources() -> None:
    """Словарь ресурсов не разделяется между снимками фракции."""
    faction = make_faction(resources={"iron": 10.0})
    updated = faction.evolve(resources={"gold": 5.0})

    assert faction.resources == {"iron": 10.0}
    assert updated.resources == {"gold": 5.0}
    assert updated.resources is not faction.resources


def test_evolve_validates_changes() -> None:
    """Некорректные изменения отклоняются."""
    faction = make_faction()

    with pytest.raises(ValidationError):
        faction.evolve(morale=2.0)


def test_json_round_trip() -> None:
    """Фракция переживает сериализацию в JSON и обратно."""
    faction = make_faction(
        resources={"iron": 10.0},
        magic_affinity=80,
        magic_schools=(MagicSchool.FIRE,),
        army_size=50.0,
    )
    restored = Faction.model_validate_json(faction.model_dump_json())

    assert restored == faction
    assert restored.military_power == faction.military_power
    assert restored.magic_schools == (MagicSchool.FIRE,)


def test_military_power_is_computed_field() -> None:
    """Боевая мощь попадает в сериализацию как вычисляемое поле."""
    faction = make_faction(army_size=10.0)

    assert "military_power" in faction.model_dump()
    assert faction.model_dump()["military_power"] == pytest.approx(faction.military_power)


def test_culture_conflict_factor() -> None:
    """Одинаковые культуры реже конфликтуют, неизвестные — базовый фактор."""
    elven = make_faction(culture="Эльфы")
    other_elven = make_faction(id=2, culture="Эльфы")
    orcish = make_faction(id=3, culture="Орки")
    alien = make_faction(id=4, culture="Пришельцы")

    assert culture_conflict_factor(elven, other_elven) == 0.2
    assert culture_conflict_factor(elven, orcish) == 1.0
    assert culture_conflict_factor(elven, alien) == CULTURE_CONFLICT_BASE


def test_ideology_properties_are_sane() -> None:
    """Свойства идеологий лежат в разумных границах."""
    for ideology in Ideology:
        assert 0.0 <= ideology.army_share <= 1.0
        assert -1.0 <= ideology.aggression_bonus <= 1.0
        assert ideology.military_multiplier > 0.0
