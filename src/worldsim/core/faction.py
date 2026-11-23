"""Модель фракции: культура, экономика, армия, мораль и магия."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

CULTURE_CONFLICT_BASE = 0.5
KNOWN_CULTURES: frozenset[str] = frozenset({"Люди", "Эльфы", "Орки", "Гномы", "Нежить"})


class Ideology(StrEnum):
    """Идеология фракции, задающая её военный и экономический профиль."""

    MILITARIST = "militarist"
    MERCANTILE = "mercantile"
    AGRARIAN = "agrarian"
    THEOCRATIC = "theocratic"
    SCHOLARLY = "scholarly"
    NOMADIC = "nomadic"

    @property
    def aggression_bonus(self) -> float:
        """Поправка к агрессивности при старте мира."""
        return _AGGRESSION_BONUS[self]

    @property
    def army_share(self) -> float:
        """Доля населения, которую фракция готова держать в армии."""
        return _ARMY_SHARE[self]

    @property
    def military_multiplier(self) -> float:
        """Множитель боевой мощи."""
        return _MILITARY_MULTIPLIER[self]


class MagicSchool(StrEnum):
    """Магические школы фракции."""

    FIRE = "fire"
    ICE = "ice"
    NECROMANCY = "necromancy"
    NATURE = "nature"


class Faction(BaseModel):
    """Неизменяемая фракция мира.

    Все правила получают параметры фракции отсюда: экономика, армия, мораль,
    мана и магические школы. Уникальность имён и цветов проверяется на уровне
    мира (T17), а не внутри модели.
    """

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    ideology: Ideology
    culture: str = Field(min_length=1, max_length=64)
    capital_tile_id: int | None = Field(default=None, ge=0)
    aggressiveness: float = Field(default=0.5, ge=0, le=1)
    treasury: float = Field(default=0.0, ge=0)
    food_stockpile: float = Field(default=0.0, ge=0)
    tech_level: float = Field(default=1.0, ge=0, le=10)
    resources: dict[str, float] = Field(default_factory=dict)
    army_size: float = Field(default=0.0, ge=0)
    morale: float = Field(default=0.8, ge=0, le=1)
    mana_pool: int = Field(default=0, ge=0)
    magic_affinity: int = Field(default=0, ge=0, le=100)
    magic_schools: tuple[MagicSchool, ...] = ()

    @field_validator("name", "culture", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        """Убирает пробелы по краям у имени и культуры."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("resources")
    @classmethod
    def _validate_resources(cls, value: dict[str, float]) -> dict[str, float]:
        """Проверяет ключи и неотрицательность ресурсов."""
        for key, amount in value.items():
            if not key:
                raise ValueError("ключ ресурса не может быть пустым")
            if amount < 0:
                raise ValueError(f"ресурс {key!r} не может быть отрицательным")
        return value

    @model_validator(mode="after")
    def _validate_magic(self) -> Self:
        """Проверяет согласованность склонности к магии и школ."""
        if self.magic_affinity > 0 and not self.magic_schools:
            raise ValueError("при magic_affinity > 0 нужна хотя бы одна магическая школа")
        if len(set(self.magic_schools)) != len(self.magic_schools):
            raise ValueError("магические школы не должны повторяться")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def military_power(self) -> float:
        """Боевая мощь: именно она сравнивается при разрешении войны."""
        return self.army_size * (1.0 + 0.1 * self.tech_level) * self.ideology.military_multiplier

    def magic_power(self) -> float:
        """Магическая мощь фракции для боя и заклинаний."""
        return (
            (self.magic_affinity / 100.0)
            * (1.0 + 0.1 * self.tech_level)
            * (1.0 + 0.25 * len(self.magic_schools))
        )

    def evolve(self, **changes: object) -> Faction:
        """Создаёт новую провалидированную фракцию с изменениями.

        Args:
            **changes: Поля, которые нужно заменить.

        Returns:
            Новый объект ``Faction``; исходная фракция не меняется.
        """
        data: dict[str, object] = {name: getattr(self, name) for name in type(self).model_fields}
        data.update(changes)
        return Faction.model_validate(data)


def culture_conflict_factor(first: Faction, second: Faction) -> float:
    """Вероятностный множитель конфликта двух культур.

    Args:
        first: Первая фракция.
        second: Вторая фракция.

    Returns:
        ``0.2`` для одной культуры, ``1.0`` для известных разных культур,
        ``CULTURE_CONFLICT_BASE`` для неизвестных пар.
    """
    if first.culture == second.culture:
        return 0.2
    if first.culture in KNOWN_CULTURES and second.culture in KNOWN_CULTURES:
        return 1.0
    return CULTURE_CONFLICT_BASE


_AGGRESSION_BONUS: dict[Ideology, float] = {
    Ideology.MILITARIST: 0.2,
    Ideology.MERCANTILE: 0.0,
    Ideology.AGRARIAN: -0.1,
    Ideology.THEOCRATIC: 0.05,
    Ideology.SCHOLARLY: -0.05,
    Ideology.NOMADIC: 0.15,
}

_ARMY_SHARE: dict[Ideology, float] = {
    Ideology.MILITARIST: 0.10,
    Ideology.MERCANTILE: 0.04,
    Ideology.AGRARIAN: 0.03,
    Ideology.THEOCRATIC: 0.05,
    Ideology.SCHOLARLY: 0.03,
    Ideology.NOMADIC: 0.08,
}

_MILITARY_MULTIPLIER: dict[Ideology, float] = {
    Ideology.MILITARIST: 1.25,
    Ideology.MERCANTILE: 0.90,
    Ideology.AGRARIAN: 0.90,
    Ideology.THEOCRATIC: 1.05,
    Ideology.SCHOLARLY: 0.95,
    Ideology.NOMADIC: 1.10,
}
