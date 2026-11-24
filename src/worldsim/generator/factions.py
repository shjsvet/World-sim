"""Стартовые фракции и распределение территорий."""

from __future__ import annotations

from collections import deque

from worldsim.core.faction import Faction, Ideology, MagicSchool
from worldsim.core.geography import RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig
from worldsim.generator.terrain import _neighbor_indices

CULTURES: tuple[str, ...] = ("Люди", "Эльфы", "Орки", "Гномы", "Нежить")

_NAMES: dict[str, tuple[str, ...]] = {
    "Люди": ("Альбион", "Империя Света", "Вольные города", "Арден"),
    "Эльфы": ("Аэлендил", "Сребролесье", "Лунный Дол", "Тирион"),
    "Орки": ("Кровавый Клык", "Ур-Гаш", "Степной Союз", "Горгрим"),
    "Гномы": ("Железный Кряж", "Мория", "Каменный Чертог", "Дар-Нур"),
    "Нежить": ("Тлен", "Некрополь", "Костяной Трон", "Морвейн"),
}

_COLORS: tuple[str, ...] = (
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
    "#008080",
    "#9a6324",
)

_IDEOLOGY_WEIGHTS: dict[Ideology, float] = {
    Ideology.MILITARIST: 20.0,
    Ideology.MERCANTILE: 15.0,
    Ideology.AGRARIAN: 20.0,
    Ideology.THEOCRATIC: 15.0,
    Ideology.SCHOLARLY: 15.0,
    Ideology.NOMADIC: 15.0,
}

_START_RESOURCES: dict[str, dict[str, float]] = {
    "Люди": {"gold": 100.0},
    "Эльфы": {"mana_crystals": 10.0},
    "Орки": {"iron": 500.0},
    "Гномы": {"iron": 300.0, "gold": 50.0},
    "Нежить": {"mana_crystals": 5.0},
}

_MAGIC_AFFINITY: dict[str, int] = {
    "Люди": 50,
    "Эльфы": 90,
    "Орки": 40,
    "Гномы": 20,
    "Нежить": 70,
}

_MAGIC_SCHOOLS: dict[str, tuple[MagicSchool, ...]] = {
    "Люди": (MagicSchool.NATURE,),
    "Эльфы": (MagicSchool.NATURE, MagicSchool.ICE),
    "Орки": (MagicSchool.FIRE,),
    "Гномы": (MagicSchool.FIRE,),
    "Нежить": (MagicSchool.NECROMANCY,),
}


def spawn_factions(
    world_map: WorldMap,
    config: WorldConfig,
    rng: Rng,
) -> tuple[Faction, ...]:
    """Создаёт стартовые фракции мира.

    Args:
        world_map: Сгенерированная карта.
        config: Параметры мира (количество фракций и агрессия).
        rng: Детерминированный генератор.

    Returns:
        Кортеж фракций с уникальными именами, цветами и культурами.
    """
    count = config.initial_factions
    if count == 0:
        return ()

    capitals = _pick_capitals(world_map, count, rng)
    cultures = list(CULTURES)
    rng.shuffle(cultures)
    colors = list(_COLORS)
    rng.shuffle(colors)

    factions: list[Faction] = []
    used_names: set[str] = set()
    for index in range(count):
        culture = cultures[index]
        ideology = rng.weighted_choice(_IDEOLOGY_WEIGHTS)
        capital = capitals[index]
        army_size = max(1.0, capital.population * ideology.army_share)
        aggressiveness = min(
            1.0,
            max(0.0, config.aggression + ideology.aggression_bonus),
        )
        factions.append(
            Faction(
                id=index,
                name=_pick_name(culture, rng, used_names),
                color=colors[index],
                ideology=ideology,
                culture=culture,
                capital_tile_id=capital.id,
                aggressiveness=aggressiveness,
                treasury=100.0,
                food_stockpile=200.0,
                tech_level=1.0,
                resources=dict(_START_RESOURCES[culture]),
                army_size=army_size,
                morale=0.8,
                mana_pool=0,
                magic_affinity=_MAGIC_AFFINITY[culture],
                magic_schools=_MAGIC_SCHOOLS[culture],
            )
        )
    return tuple(factions)


def assign_territories(world_map: WorldMap, factions: tuple[Faction, ...]) -> WorldMap:
    """Раздаёт территории фракциям равномерной BFS-заливкой от столиц.

    Args:
        world_map: Карта без владельцев.
        factions: Фракции со столицами.

    Returns:
        Новая карта, где суша поделена между фракциями, а вода нейтральна.
    """
    if not factions:
        return world_map

    culture_by_faction = {faction.id: faction.culture for faction in factions}
    owners: dict[int, int] = {}
    cultures: dict[int, str] = {}
    queue: deque[tuple[int, int]] = deque()

    for faction in factions:
        if faction.capital_tile_id is None:
            continue
        owners[faction.capital_tile_id] = faction.id
        cultures[faction.capital_tile_id] = faction.culture
        queue.append((faction.capital_tile_id, faction.id))

    while queue:
        index, faction_id = queue.popleft()
        for neighbor in _neighbor_indices(index, world_map.size):
            if neighbor in owners:
                continue
            if not world_map.tiles[neighbor].is_land:
                continue
            owners[neighbor] = faction_id
            cultures[neighbor] = culture_by_faction[faction_id]
            queue.append((neighbor, faction_id))

    tiles: list[RegionData] = []
    army_by_tile: dict[int, int] = {}
    for faction in factions:
        owned = sorted(tile_id for tile_id, owner in owners.items() if owner == faction.id)
        if not owned:
            continue
        total = max(0, int(faction.army_size))
        base, remainder = divmod(total, len(owned))
        for position, tile_id in enumerate(owned):
            army_by_tile[tile_id] = base + (1 if position < remainder else 0)

    for tile in world_map.tiles:
        if tile.id in owners:
            tiles.append(
                tile.model_copy(
                    update={
                        "owner_id": owners[tile.id],
                        "culture": cultures[tile.id],
                        "army_presence": army_by_tile.get(tile.id, 0),
                    }
                )
            )
        else:
            tiles.append(tile)
    return WorldMap(size=world_map.size, tiles=tuple(tiles))


def distribute_territory_army(
    world_map: WorldMap,
    factions: tuple[Faction, ...],
) -> WorldMap:
    """Раскладывает армию фракций по принадлежащим им тайлам."""
    army_by_tile: dict[int, int] = {}
    for faction in factions:
        owned = sorted(tile.id for tile in world_map.tiles if tile.owner_id == faction.id)
        if not owned:
            continue
        total = max(0, int(faction.army_size))
        base, remainder = divmod(total, len(owned))
        for position, tile_id in enumerate(owned):
            army_by_tile[tile_id] = base + (1 if position < remainder else 0)

    return WorldMap(
        size=world_map.size,
        tiles=tuple(
            tile.model_copy(update={"army_presence": army_by_tile.get(tile.id, 0)})
            if tile.owner_id is not None
            else tile
            for tile in world_map.tiles
        ),
    )


def _pick_capitals(world_map: WorldMap, count: int, rng: Rng) -> list[RegionData]:
    """Выбирает разнесённые столицы на самой плодородной суше."""
    land = [tile for tile in world_map.tiles if tile.is_land]
    if len(land) < count:
        raise ValueError(f"на карте недостаточно суши для {count} фракций")

    candidates = sorted(land, key=lambda tile: (-tile.fertility, tile.id))
    spacing = max(1, world_map.size // 4)
    capitals: list[RegionData] = []
    for tile in candidates:
        if len(capitals) >= count:
            break
        if all(
            max(abs(tile.x - chosen.x), abs(tile.y - chosen.y)) >= spacing for chosen in capitals
        ):
            capitals.append(tile)

    if len(capitals) < count:
        remaining = [tile for tile in candidates if tile not in capitals]
        rng.shuffle(remaining)
        for tile in remaining:
            if len(capitals) >= count:
                break
            capitals.append(tile)
    return capitals[:count]


def _pick_name(culture: str, rng: Rng, used: set[str]) -> str:
    """Выбирает имя из пула культуры, добавляя суффикс при коллизии."""
    base = rng.choice(_NAMES[culture])
    name = base
    suffix = 2
    while name in used:
        name = f"{base} {suffix}"
        suffix += 1
    used.add(name)
    return name
