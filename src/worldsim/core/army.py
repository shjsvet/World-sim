"""Марши армий: перемещение между тайлами за несколько лет."""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from worldsim.core.state import WorldState

MARCH_SPEED = 2.0


class ArmyMarch(BaseModel):
    """Идущая армия: покинула тайл и прибудет в году ``arrival_year``."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    faction_id: int = Field(ge=0)
    from_tile: int = Field(ge=0)
    to_tile: int = Field(ge=0)
    amount: int = Field(gt=0)
    departure_year: int = Field(ge=0)
    arrival_year: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_route(self) -> ArmyMarch:
        """Проверяет направление и срок марша."""
        if self.from_tile == self.to_tile:
            raise ValueError("марш не может идти в тот же тайл")
        if self.arrival_year < self.departure_year:
            raise ValueError("прибытие не может быть раньше отправления")
        return self


def march_duration(state: WorldState, from_tile: int, to_tile: int) -> int:
    """Считает время марша в годах по расстоянию и стоимости биома."""
    source = state.map.by_id(from_tile)
    target = state.map.by_id(to_tile)
    distance = abs(source.x - target.x) + abs(source.y - target.y)
    cost = (source.biome.movement_cost + target.biome.movement_cost) / 2.0
    return max(1, ceil(distance * max(0.1, cost) / MARCH_SPEED))
