"""Модель войны между фракциями."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class War(BaseModel):
    """Неизменяемая запись войны; перемирие задаётся ``truce_until_year``."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    attacker_id: int = Field(ge=0)
    defender_id: int = Field(ge=0)
    started_year: int = Field(ge=0)
    battles: int = Field(default=0, ge=0)
    attacker_losses: float = Field(default=0.0, ge=0)
    defender_losses: float = Field(default=0.0, ge=0)
    active: bool = True
    truce_until_year: int | None = Field(default=None, ge=0)
