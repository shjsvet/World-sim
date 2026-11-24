"""Конфигурация мира и иммутабельный снимок состояния."""

from __future__ import annotations

import hashlib
import json
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from worldsim.core.culture import Culture, Religion
from worldsim.core.diplomacy import War
from worldsim.core.faction import Faction
from worldsim.core.geography import WorldMap


class WorldConfig(BaseModel):
    """Параметры генерации и развития мира."""

    model_config = ConfigDict(frozen=True)

    seed: int
    size: int = Field(ge=4, le=512)
    initial_factions: int = Field(default=2, ge=0, le=4)
    aggression: float = Field(default=0.5, ge=0, le=1)
    growth_rate: float = Field(default=0.02, ge=0)
    plague_chance: float = Field(default=0.01, ge=0, le=1)
    magic_level: float = Field(default=0.0, ge=0, le=1)

    def evolve(self, **changes: object) -> WorldConfig:
        """Возвращает копию конфигурации с изменениями и повторной валидацией."""
        data: dict[str, object] = {**self.model_dump(), **changes}
        return WorldConfig.model_validate(data)


class WorldState(BaseModel):
    """Неизменяемый снимок мира на конкретный год.

    Каждый шаг симуляции создаёт новый снимок через :meth:`evolve`; исходный
    объект не меняется. ``snapshot_hash`` зависит только от содержимого
    снимка, поэтому одинаковый мир и сид дают одинаковый хеш в любом процессе.

    Инварианты: идентификаторы, имена и цвета фракций уникальны; каждый
    ``owner_id`` ссылается на существующую фракцию; вода не имеет владельца и
    армии; армия может стоять только в чужом или своём владении; столица
    фракции принадлежит ей.

    Attributes:
        config: Параметры мира.
        year: Текущий год.
        map: Сетка тайлов.
        factions: Фракции мира.
        wars: Активные и завершённые войны.
        cultures: Культуры мира.
        religions: Религии мира.
    """

    model_config = ConfigDict(frozen=True)

    config: WorldConfig
    year: int = Field(ge=0)
    map: WorldMap
    factions: tuple[Faction, ...] = ()
    wars: tuple[War, ...] = ()
    cultures: tuple[Culture, ...] = ()
    religions: tuple[Religion, ...] = ()

    @model_validator(mode="after")
    def _validate_factions(self) -> Self:
        """Проверяет согласованность фракций и владения тайлами."""
        if len({faction.id for faction in self.factions}) != len(self.factions):
            raise ValueError("идентификаторы фракций должны быть уникальны")
        if len({faction.name for faction in self.factions}) != len(self.factions):
            raise ValueError("имена фракций должны быть уникальны")
        if len({faction.color for faction in self.factions}) != len(self.factions):
            raise ValueError("цвета фракций должны быть уникальны")

        faction_ids = {faction.id for faction in self.factions}
        for tile in self.map.tiles:
            if tile.biome.is_water:
                if tile.owner_id is not None:
                    raise ValueError(f"водный тайл {tile.id} не может принадлежать фракции")
                if tile.army_presence > 0:
                    raise ValueError(f"на водном тайле {tile.id} не может быть армии")
                continue
            if tile.owner_id is not None and tile.owner_id not in faction_ids:
                raise ValueError(f"тайл {tile.id} принадлежит несуществующей фракции")
            if tile.army_presence > 0 and tile.owner_id is None:
                raise ValueError(f"на нейтральном тайле {tile.id} не может быть армии")

        for faction in self.factions:
            if faction.capital_tile_id is None:
                continue
            if not 0 <= faction.capital_tile_id < len(self.map.tiles):
                raise ValueError(f"столица фракции {faction.id} вне карты")
            capital = self.map.by_id(faction.capital_tile_id)
            if capital.owner_id != faction.id:
                raise ValueError(f"столица фракции {faction.id} не принадлежит ей")

        if len({war.id for war in self.wars}) != len(self.wars):
            raise ValueError("идентификаторы войн должны быть уникальны")
        for war in self.wars:
            if war.attacker_id == war.defender_id:
                raise ValueError("фракция не может воевать сама с собой")
            if war.attacker_id not in faction_ids or war.defender_id not in faction_ids:
                raise ValueError("война ссылается на несуществующую фракцию")

        if len({culture.id for culture in self.cultures}) != len(self.cultures):
            raise ValueError("идентификаторы культур должны быть уникальны")
        if len({culture.name.casefold() for culture in self.cultures}) != len(self.cultures):
            raise ValueError("имена культур должны быть уникальны")
        culture_ids = {culture.id for culture in self.cultures}
        if len({religion.id for religion in self.religions}) != len(self.religions):
            raise ValueError("идентификаторы религий должны быть уникальны")
        for religion in self.religions:
            if religion.culture_id not in culture_ids:
                raise ValueError("религия ссылается на несуществующую культуру")
        religion_ids = {religion.id for religion in self.religions}

        for tile in self.map.tiles:
            if tile.culture_id is not None and tile.culture_id not in culture_ids:
                raise ValueError(f"тайл {tile.id} ссылается на несуществующую культуру")
            if tile.religion_id is not None and tile.religion_id not in religion_ids:
                raise ValueError(f"тайл {tile.id} ссылается на несуществующую религию")

        if self.cultures:
            culture_names = {culture.name.casefold() for culture in self.cultures}
            for faction in self.factions:
                if faction.culture.casefold() not in culture_names:
                    raise ValueError(f"культура фракции {faction.id} отсутствует в списке культур")
        return self

    def evolve(self, **changes: object) -> WorldState:
        """Создаёт новый провалидированный снимок с изменениями.

        Args:
            **changes: Поля снимка, которые нужно заменить (например, ``year=1``).

        Returns:
            Новый объект ``WorldState``; текущий снимок не изменяется.

        Raises:
            ValidationError: Если изменения нарушают инварианты модели.
        """
        data = self.model_dump()
        data.update(changes)
        return WorldState.model_validate(data)

    def snapshot_hash(self) -> str:
        """Возвращает стабильный sha256-хеш содержимого снимка."""
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Сериализует снимок в JSON."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, payload: str) -> Self:
        """Восстанавливает снимок из JSON.

        Args:
            payload: Строка, полученная из :meth:`to_json`.

        Returns:
            Провалидированный снимок мира.
        """
        return cls.model_validate_json(payload)
