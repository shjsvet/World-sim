"""Культуры и религии мира."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Culture(BaseModel):
    """Культура с набором признаков."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    traits: tuple[str, ...] = ()


class Religion(BaseModel):
    """Религия, связанная с культурой."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    culture_id: int = Field(ge=0)
    zeal: float = Field(default=0.5, ge=0, le=1)
