"""Сборка стартового мира из сгенерированной карты."""

from __future__ import annotations

from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.terrain import generate_map


def create_world(config: WorldConfig) -> WorldState:
    """Создаёт снимок мира на нулевом году.

    Args:
        config: Параметры мира.

    Returns:
        Иммутабельный ``WorldState`` с картой, сгенерированной по сиду.
    """
    rng = Rng(config.seed)
    return WorldState(config=config, year=0, map=generate_map(config, rng))
