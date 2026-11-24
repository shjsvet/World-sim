"""Магические академии и константы магии."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from worldsim.core.faction import MagicSchool

ACADEMY_MIN_DENSITY = 50
LEY_LINE_MANA_BONUS = 2
ACADEMY_COST_GOLD = 100
ACADEMY_COST_MANA = 50
RESEARCH_COST_MANA = 20
RESEARCH_AFFINITY_STEP = 1
ACADEMY_MAX_LEVEL = 10


class MagicAcademy(BaseModel):
    """Магическая академия на тайле фракции."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    tile_id: int = Field(ge=0)
    faction_id: int = Field(ge=0)
    school: MagicSchool
    level: int = Field(default=1, ge=1, le=ACADEMY_MAX_LEVEL)
    founded_year: int = Field(ge=0)
