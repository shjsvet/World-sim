"""Агрегированные метрики фракций для правил симуляции."""

from __future__ import annotations

from dataclasses import dataclass

from worldsim.core.geography import RegionData
from worldsim.core.state import WorldState

FOOD_PER_CAPITA = 0.5
MORALE_PEACE_THRESHOLD = 0.3


@dataclass(frozen=True)
class FactionStats:
    """Сводные показатели одной фракции на текущем шаге."""

    faction_id: int
    culture: str
    tiles: int
    population: int
    food_production: float
    food_consumption: float
    treasury: float
    food_stockpile: float
    tech_level: float
    army_size: float
    military_power: float
    morale: float
    mana_pool: int
    mana_income: int
    magic_affinity: int
    mana_density_avg: float
    ley_lines: int
    happiness_avg: float
    unrest_avg: float
    cities: int
    is_starving: bool
    is_low_morale: bool
    border_contact: tuple[int, ...] = ()
    enemies: tuple[int, ...] = ()


def compute_faction_stats(state: WorldState) -> dict[int, FactionStats]:
    """Считает метрики всех фракций мира.

    Args:
        state: Снимок мира.

    Returns:
        Отображение «id фракции → метрики». Фракция без территорий получает
        нулевые агрегаты без деления на ноль.
    """
    owned: dict[int, list[RegionData]] = {faction.id: [] for faction in state.factions}
    borders: dict[int, set[int]] = {faction.id: set() for faction in state.factions}
    for tile in state.map.tiles:
        if tile.owner_id is None:
            continue
        if tile.owner_id in owned:
            owned[tile.owner_id].append(tile)

    for tile in state.map.tiles:
        if tile.owner_id is None:
            continue
        for neighbor in state.map.neighbors(tile.x, tile.y):
            if (
                neighbor.owner_id is not None
                and neighbor.owner_id != tile.owner_id
                and tile.owner_id in borders
            ):
                borders[tile.owner_id].add(neighbor.owner_id)

    stats: dict[int, FactionStats] = {}
    for faction in state.factions:
        tiles = owned[faction.id]
        population = sum(tile.population for tile in tiles)
        food_production = sum(tile.food_output() for tile in tiles)
        food_consumption = population * FOOD_PER_CAPITA
        populated = [tile for tile in tiles if tile.population > 0]
        happiness_avg = (
            sum(tile.happiness for tile in populated) / len(populated) if populated else 0.0
        )
        unrest_avg = sum(tile.unrest for tile in populated) / len(populated) if populated else 0.0
        stats[faction.id] = FactionStats(
            faction_id=faction.id,
            culture=faction.culture,
            tiles=len(tiles),
            population=population,
            food_production=food_production,
            food_consumption=food_consumption,
            treasury=faction.treasury,
            food_stockpile=faction.food_stockpile,
            tech_level=faction.tech_level,
            army_size=faction.army_size,
            military_power=faction.military_power,
            morale=faction.morale,
            mana_pool=faction.mana_pool,
            mana_income=sum(tile.mana_regeneration for tile in tiles),
            magic_affinity=faction.magic_affinity,
            mana_density_avg=(
                sum(tile.mana_density for tile in tiles) / len(tiles) if tiles else 0.0
            ),
            ley_lines=sum(1 for tile in tiles if tile.ley_line),
            happiness_avg=happiness_avg,
            unrest_avg=unrest_avg,
            cities=sum(1 for tile in tiles if tile.is_city),
            is_starving=(
                faction.food_stockpile <= 0
                or faction.food_stockpile + food_production < food_consumption
            ),
            is_low_morale=faction.morale < MORALE_PEACE_THRESHOLD,
            border_contact=tuple(sorted(borders[faction.id])),
            enemies=_enemies(state, faction.id),
        )
    return stats


def _enemies(state: WorldState, faction_id: int) -> tuple[int, ...]:
    """Возвращает противников по активным войнам.

    Поле ``wars`` появится в T21; до этого метрика пуста.
    """
    wars: object = getattr(state, "wars", ())
    if not isinstance(wars, tuple):
        return ()
    enemies: set[int] = set()
    for war in wars:
        if not getattr(war, "active", False):
            continue
        attacker = getattr(war, "attacker_id", None)
        defender = getattr(war, "defender_id", None)
        if attacker == faction_id and isinstance(defender, int):
            enemies.add(defender)
        elif defender == faction_id and isinstance(attacker, int):
            enemies.add(attacker)
    return tuple(sorted(enemies))
