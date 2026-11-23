"""Модель сухого события: данные, по которым ИИ пишет летопись."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

PayloadValue: TypeAlias = int | float | str | bool | None


class EventType(StrEnum):
    """Тип события в летописи."""

    PLAGUE = "plague"
    FAMINE = "famine"
    STARVATION = "starvation"
    EXPANSION = "expansion"
    WAR = "war"
    BATTLE_WON = "battle_won"
    BATTLE_LOST = "battle_lost"
    CAPITAL_FALL = "capital_fall"
    MIGRATION = "migration"
    CULTURE_CLASH = "culture_clash"
    TRADE = "trade"
    RECRUITMENT = "recruitment"
    DESERTION = "desertion"
    TECH_ADVANCE = "tech_advance"
    PEACE_OFFER = "peace_offer"
    PEACE_TREATY = "peace_treaty"
    RIOT = "riot"
    SECESSION = "secession"
    DEFECTION = "defection"
    CITY_RISE = "city_rise"
    RESOURCE_DEPLETED = "resource_depleted"
    OCCUPATION = "occupation"
    ACADEMY_FOUNDED = "academy_founded"
    MAGIC_BREAKTHROUGH = "magic_breakthrough"
    LEY_LINE_CLAIMED = "ley_line_claimed"
    CUSTOM = "custom"


class Event(BaseModel):
    """Неизменяемое событие: сухие данные без литературных оборотов.

    События сериализуются в JSON целиком, чтобы попадать в снимок мира и
    использоваться ИИ-хронистом как исходный материал.
    """

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    year: int = Field(ge=0)
    type: EventType
    summary: str = Field(min_length=1, max_length=300)
    tile_ids: tuple[int, ...] = ()
    faction_ids: tuple[int, ...] = ()
    severity: float = Field(ge=0, le=1)
    payload: dict[str, PayloadValue] = Field(default_factory=dict)

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: object) -> object:
        """Убирает пробелы по краям и запрещает пустую строку."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("summary не может быть пустым")
            return normalized
        return value

    @field_validator("tile_ids", "faction_ids")
    @classmethod
    def _validate_ids(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Проверяет, что идентификаторы неотрицательны."""
        if any(item < 0 for item in value):
            raise ValueError("идентификаторы должны быть неотрицательными")
        return value

    @field_validator("payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, PayloadValue]) -> dict[str, PayloadValue]:
        """Запрещает пустые ключи в полезной нагрузке."""
        if any(not key for key in value):
            raise ValueError("ключи payload не могут быть пустыми")
        return value

    def as_dict(self) -> dict[str, Any]:
        """Возвращает JSON-совместимое представление события."""
        return self.model_dump(mode="json")

    @classmethod
    def plague(
        cls,
        *,
        year: int,
        tile_ids: Sequence[int] = (),
        severity: float = 0.0,
        event_id: int = 0,
        summary: str | None = None,
    ) -> Event:
        """Создаёт событие эпидемии."""
        tiles = tuple(tile_ids)
        return cls(
            id=event_id,
            year=year,
            type=EventType.PLAGUE,
            summary=summary or f"Эпидемия: тайлы {list(tiles)}, потери {severity:.0%}",
            tile_ids=tiles,
            severity=severity,
        )

    @classmethod
    def expansion(
        cls,
        *,
        year: int,
        faction_id: int,
        tile_id: int,
        event_id: int = 0,
        summary: str | None = None,
    ) -> Event:
        """Создаёт событие экспансии фракции на тайл."""
        return cls(
            id=event_id,
            year=year,
            type=EventType.EXPANSION,
            summary=summary or f"Фракция {faction_id} заняла тайл {tile_id}",
            tile_ids=(tile_id,),
            faction_ids=(faction_id,),
            severity=0.0,
        )

    @classmethod
    def war(
        cls,
        *,
        year: int,
        attacker_id: int,
        defender_id: int,
        tile_id: int,
        severity: float = 0.5,
        event_id: int = 0,
        summary: str | None = None,
    ) -> Event:
        """Создаёт событие войны между фракциями."""
        payload: dict[str, PayloadValue] = {
            "attacker_id": attacker_id,
            "defender_id": defender_id,
        }
        return cls(
            id=event_id,
            year=year,
            type=EventType.WAR,
            summary=summary
            or f"Война: фракция {attacker_id} атакует {defender_id} в тайле {tile_id}",
            tile_ids=(tile_id,),
            faction_ids=(attacker_id, defender_id),
            severity=severity,
            payload=payload,
        )

    @classmethod
    def starvation(
        cls,
        *,
        year: int,
        faction_id: int,
        tile_ids: Sequence[int] = (),
        severity: float = 0.0,
        event_id: int = 0,
        summary: str | None = None,
    ) -> Event:
        """Создаёт событие голода во фракции."""
        tiles = tuple(tile_ids)
        return cls(
            id=event_id,
            year=year,
            type=EventType.STARVATION,
            summary=summary or f"Голод во фракции {faction_id}: потери {severity:.0%}",
            tile_ids=tiles,
            faction_ids=(faction_id,),
            severity=severity,
        )

    @classmethod
    def peace(
        cls,
        *,
        year: int,
        faction_ids: Sequence[int],
        event_id: int = 0,
        summary: str | None = None,
    ) -> Event:
        """Создаёт событие заключения мира."""
        parties = tuple(faction_ids)
        return cls(
            id=event_id,
            year=year,
            type=EventType.PEACE_TREATY,
            summary=summary or f"Мир: фракции {list(parties)}",
            faction_ids=parties,
            severity=0.0,
        )
