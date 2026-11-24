"""Модели ИИ-правителей: профили, мысли, приказы и переписка."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RulerStyle(StrEnum):
    """Стиль правления, влияющий на приоритеты ИИ."""

    WARLORD = "warlord"
    MERCHANT = "merchant"
    PRIEST = "priest"
    SCHOLAR = "scholar"
    DIPLOMAT = "diplomat"
    BUILDER = "builder"


class MessageKind(StrEnum):
    """Тип дипломатического сообщения."""

    OFFER = "offer"
    ACCEPT = "accept"
    REJECT = "reject"
    THREAT = "threat"
    PEACE = "peace"
    TRADE = "trade"


class RulerProfile(BaseModel):
    """Настройки ИИ-правителя фракции."""

    model_config = ConfigDict(frozen=True)

    faction_id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    style: RulerStyle = RulerStyle.DIPLOMAT
    traits: tuple[str, ...] = ()
    decision_interval: int = Field(default=1, ge=1, le=20)
    model: str | None = None


class RulerThought(BaseModel):
    """Запись дневника правителя: мысль и выбранное действие."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    faction_id: int = Field(ge=0)
    year: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=1000)
    action: str = ""
    target_tile_id: int | None = Field(default=None, ge=0)


class StandingOrder(BaseModel):
    """Долгосрочный приказ, который движок исполняет несколько лет."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    faction_id: int = Field(ge=0)
    kind: str = Field(min_length=1, max_length=64)
    target_tile_id: int | None = Field(default=None, ge=0)
    payload: dict[str, object] = Field(default_factory=dict)
    years_left: int = Field(ge=0)
    created_year: int = Field(ge=0)


class DiplomaticMessage(BaseModel):
    """Сообщение в переписке двух правителей."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    year: int = Field(ge=0)
    sender_id: int = Field(ge=0)
    recipient_id: int = Field(ge=0)
    kind: MessageKind = MessageKind.OFFER
    text: str = Field(min_length=1, max_length=1000)
    accepted: bool | None = None

    @model_validator(mode="after")
    def _validate_recipient(self) -> DiplomaticMessage:
        """Правитель не может писать сам себе."""
        if self.sender_id == self.recipient_id:
            raise ValueError("отправитель и получатель должны различаться")
        return self
