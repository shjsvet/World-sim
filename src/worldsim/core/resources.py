"""Ресурсы и торговые маршруты."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from worldsim.core.geography import ResourceType


class TradeRoute(BaseModel):
    """Торговый маршрут между соседними тайлами разных фракций."""

    model_config = ConfigDict(frozen=True)

    from_tile: int = Field(ge=0)
    to_tile: int = Field(ge=0)
    resource: ResourceType
    capacity: float = Field(ge=0)

    @model_validator(mode="after")
    def _validate(self) -> TradeRoute:
        """Маршрут не может вести в тот же тайл и торговать «ничем»."""
        if self.from_tile == self.to_tile:
            raise ValueError("маршрут не может соединять тайл с самим собой")
        if self.resource is ResourceType.NONE:
            raise ValueError("маршрут должен перевозить ресурс")
        return self
