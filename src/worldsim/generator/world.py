"""Сборка стартового мира из сгенерированной карты."""

from __future__ import annotations

from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.factions import (
    assign_territories,
    distribute_territory_army,
    spawn_factions,
)
from worldsim.generator.terrain import generate_map

ARMY_POPULATION_SHARE = 0.5


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
    scaled_factions = tuple(
        faction.evolve(
            army_size=max(
                1.0,
                sum(tile.population for tile in world_map.tiles if tile.owner_id == faction.id)
                * faction.ideology.army_share
                * ARMY_POPULATION_SHARE,
            )
        )
        for faction in factions
    )
    world_map = distribute_territory_army(world_map, scaled_factions)
    return WorldState(
        config=config,
        year=0,
        map=world_map,
        factions=scaled_factions,
    )
