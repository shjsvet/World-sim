"""Конфигурация мира и иммутабельный снимок состояния."""

from __future__ import annotations

import hashlib
import json
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from worldsim.core.geography import WorldMap


class WorldConfig(BaseModel):
    """Параметры генерации и развития мира."""

    model_config = ConfigDict(frozen=True)

    seed: int
    size: int = Field(ge=4, le=512)
    initial_factions: int = Field(default=0, ge=0, le=4)
    aggression: float = Field(default=0.5, ge=0, le=1)
    growth_rate: float = Field(default=0.02, ge=0)
    plague_chance: float = Field(default=0.01, ge=0, le=1)
    magic_level: float = Field(default=0.0, ge=0, le=1)


class WorldState(BaseModel):
    """Неизменяемый снимок мира на конкретный год.

    Каждый шаг симуляции создаёт новый снимок через :meth:`evolve`; исходный
    объект не меняется. ``snapshot_hash`` зависит только от содержимого
    снимка, поэтому одинаковый мир и сид дают одинаковый хеш в любом процессе.
    """

    model_config = ConfigDict(frozen=True)

    config: WorldConfig
    year: int = Field(ge=0)
    map: WorldMap

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
