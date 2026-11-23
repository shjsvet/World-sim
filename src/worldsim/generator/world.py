"""Сборка стартового мира из сгенерированной карты."""

from __future__ import annotations

from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.factions import assign_territories, spawn_factions
from worldsim.generator.terrain import generate_map


def create_world(config: WorldConfig) -> WorldState:
    """Создаёт снимок мира на нулевом году.

    Args:
        config: Параметры мира.

    Returns:
        Иммутабельный ``WorldState`` с картой, фракциями и их территориями.
    """
    rng = Rng(config.seed)
    base_map = generate_map(config, rng)
    factions = spawn_factions(base_map, config, rng)
    world_map = assign_territories(base_map, factions)
    return WorldState(config=config, year=0, map=world_map, factions=factions)
