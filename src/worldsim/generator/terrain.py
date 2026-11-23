"""Процедурная генерация карты мира."""

from __future__ import annotations

from collections import deque

from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig

_SEED_BIOME_WEIGHTS: dict[Biome, float] = {
    Biome.OCEAN: 30.0,
    Biome.PLAINS: 22.0,
    Biome.FOREST: 16.0,
    Biome.HILLS: 8.0,
    Biome.MOUNTAINS: 6.0,
    Biome.DESERT: 8.0,
    Biome.TUNDRA: 5.0,
    Biome.SWAMP: 5.0,
}

_MANA_BASE: dict[Biome, int] = {
    Biome.OCEAN: 0,
    Biome.COAST: 15,
    Biome.PLAINS: 10,
    Biome.FOREST: 40,
    Biome.HILLS: 35,
    Biome.MOUNTAINS: 60,
    Biome.DESERT: 5,
    Biome.TUNDRA: 15,
    Biome.SWAMP: 50,
}

_RESOURCE_WEIGHTS: dict[Biome, dict[ResourceType, float]] = {
    Biome.COAST: {ResourceType.FOOD: 1.0},
    Biome.PLAINS: {ResourceType.FOOD: 1.0},
    Biome.FOREST: {ResourceType.WOOD: 1.0},
    Biome.HILLS: {ResourceType.IRON: 0.6, ResourceType.GOLD: 0.4},
    Biome.MOUNTAINS: {ResourceType.IRON: 0.5, ResourceType.GOLD: 0.5},
    Biome.DESERT: {ResourceType.NONE: 0.6, ResourceType.GOLD: 0.4},
    Biome.TUNDRA: {ResourceType.NONE: 0.6, ResourceType.GOLD: 0.4},
    Biome.SWAMP: {ResourceType.MANA: 1.0},
}

_DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def generate_map(config: WorldConfig, rng: Rng) -> WorldMap:
    """Генерирует карту мира по конфигурации.

    Единственный источник случайности — переданный ``rng``; одинаковый сид
    даёт идентичную карту.

    Args:
        config: Параметры мира (размер и сид).
        rng: Детерминированный генератор.

    Returns:
        Сетка тайлов с биомами, реками, ресурсами, маной и населением.
    """
    size = config.size
    total = size * size

    seeded = _seed_biomes(total, rng)
    grown = _grow_biomes(seeded, size)
    biomes = _smooth(_require_biomes(grown), size)
    biomes = _add_coasts(biomes, size)
    elevations = _elevations(biomes, rng)
    rivers = _rivers(biomes, elevations, size, rng)
    fertilities = _fertilities(biomes, rivers, rng)
    resource_types, resource_amounts, resource_depletions = _resources(biomes, rng)
    mana_densities, mana_regenerations, ley_lines = _mana(biomes, size, rng)
    capacities, populations = _population(biomes, fertilities, rng)

    tiles = tuple(
        RegionData(
            id=index,
            x=index % size,
            y=index // size,
            biome=biomes[index],
            fertility=fertilities[index],
            elevation=elevations[index],
            has_river=index in rivers,
            resource_type=resource_types[index],
            resource_amount=resource_amounts[index],
            resource_depletion=resource_depletions[index],
            population=populations[index],
            population_capacity=capacities[index],
            happiness=60.0,
            urbanization=min(100.0, populations[index] / 20.0),
            mana_density=mana_densities[index],
            mana_regeneration=mana_regenerations[index],
            ley_line=index in ley_lines,
        )
        for index in range(total)
    )
    return WorldMap(size=size, tiles=tiles)


def _neighbor_indices(index: int, size: int) -> list[int]:
    """Возвращает индексы соседей тайла по четырём направлениям."""
    x = index % size
    y = index // size
    result: list[int] = []
    for delta_x, delta_y in _DIRECTIONS:
        next_x = x + delta_x
        next_y = y + delta_y
        if 0 <= next_x < size and 0 <= next_y < size:
            result.append(next_y * size + next_x)
    return result


def _seed_biomes(total: int, rng: Rng) -> list[Biome | None]:
    """Размечает стартовые точки будущих областей биомов."""
    seed_count = max(3, total // 20)
    indices = list(range(total))
    rng.shuffle(indices)

    biomes: list[Biome | None] = [None] * total
    for index in indices[:seed_count]:
        biomes[index] = rng.weighted_choice(_SEED_BIOME_WEIGHTS)
    return biomes


def _grow_biomes(biomes: list[Biome | None], size: int) -> list[Biome | None]:
    """Распространяет биомы от стартовых точек через BFS-flood-fill."""
    queue: deque[tuple[int, Biome]] = deque()
    for index, biome in enumerate(biomes):
        if biome is not None:
            queue.append((index, biome))

    while queue:
        index, biome = queue.popleft()
        for neighbor in _neighbor_indices(index, size):
            if biomes[neighbor] is None:
                biomes[neighbor] = biome
                queue.append((neighbor, biome))
    return biomes


def _require_biomes(biomes: list[Biome | None]) -> list[Biome]:
    """Приводит карту к списку биомов, проверяя полноту заливки."""
    if any(biome is None for biome in biomes):
        raise RuntimeError("flood fill не покрыл всю карту")
    return [biome for biome in biomes if biome is not None]


def _smooth(biomes: list[Biome], size: int) -> list[Biome]:
    """Выполняет majority-фильтр для сглаживания границ биомов."""
    current = list(biomes)
    for _ in range(2):
        updated = list(current)
        for index in range(len(current)):
            counts: dict[Biome, int] = {}
            for neighbor in (index, *_neighbor_indices(index, size)):
                biome = current[neighbor]
                counts[biome] = counts.get(biome, 0) + 1
            best_biome = current[index]
            best_count = -1
            for biome, count in counts.items():
                if count > best_count or (count == best_count and biome is current[index]):
                    best_biome = biome
                    best_count = count
            updated[index] = best_biome
        current = updated
    return current


def _add_coasts(biomes: list[Biome], size: int) -> list[Biome]:
    """Превращает сушу, граничащую с океаном, в побережье."""
    updated = list(biomes)
    for index, biome in enumerate(biomes):
        if biome is Biome.OCEAN:
            continue
        if any(biomes[neighbor] is Biome.OCEAN for neighbor in _neighbor_indices(index, size)):
            updated[index] = Biome.COAST
    return updated


def _elevations(biomes: list[Biome], rng: Rng) -> list[float]:
    """Рассчитывает высоту тайлов над уровнем моря."""
    result: list[float] = []
    for biome in biomes:
        if biome is Biome.OCEAN:
            result.append(0.0)
        elif biome is Biome.COAST:
            result.append(10.0)
        else:
            value = biome.base_elevation + rng.uniform(-60.0, 60.0)
            result.append(max(0.0, min(9000.0, value)))
    return result


def _rivers(
    biomes: list[Biome],
    elevations: list[float],
    size: int,
    rng: Rng,
) -> set[int]:
    """Прокладывает реки от гор к ближайшей воде по убыванию высоты."""
    candidates = [index for index, biome in enumerate(biomes) if biome is Biome.MOUNTAINS]
    rng.shuffle(candidates)

    rivers: set[int] = set()
    max_rivers = max(1, size // 8)
    created = 0
    for start in candidates:
        if created >= max_rivers:
            break
        path = _trace_river(start, biomes, elevations, size)
        if path is not None:
            rivers.update(path)
            created += 1

    if not rivers:
        land = [index for index, biome in enumerate(biomes) if biome is not Biome.OCEAN]
        if land:
            start = max(land, key=lambda index: elevations[index])
            path = _trace_river(start, biomes, elevations, size)
            if path is not None:
                rivers.update(path)
    return rivers


def _trace_river(
    start: int,
    biomes: list[Biome],
    elevations: list[float],
    size: int,
) -> list[int] | None:
    """Прослеживает русло от тайла вниз до океана; ``None``, если вода не найдена."""
    path: list[int] = [start]
    current = start
    for _ in range(size * 2):
        neighbors = _neighbor_indices(current, size)
        if not neighbors:
            return None
        lowest = min(neighbors, key=lambda index: elevations[index])
        if elevations[lowest] >= elevations[current]:
            return None
        current = lowest
        if biomes[current] is Biome.OCEAN:
            return [index for index in path if biomes[index] is not Biome.OCEAN]
        path.append(current)
    return None


def _fertilities(biomes: list[Biome], rivers: set[int], rng: Rng) -> list[float]:
    """Рассчитывает плодородие тайлов с учётом рек."""
    result: list[float] = []
    for index, biome in enumerate(biomes):
        if biome is Biome.OCEAN:
            result.append(0.0)
            continue
        value = biome.base_fertility + rng.uniform(-10.0, 10.0)
        if index in rivers:
            value += 10.0
        result.append(max(0.0, min(100.0, value)))
    return result


def _resources(
    biomes: list[Biome],
    rng: Rng,
) -> tuple[list[ResourceType], list[float], list[float]]:
    """Распределяет по тайлам главный ресурс и запас в земле."""
    resource_types: list[ResourceType] = []
    amounts: list[float] = []
    depletions: list[float] = []
    for biome in biomes:
        if biome is Biome.OCEAN:
            resource = ResourceType.NONE
        else:
            resource = rng.weighted_choice(_RESOURCE_WEIGHTS[biome])
        resource_types.append(resource)
        if resource is ResourceType.NONE:
            amounts.append(0.0)
            depletions.append(0.0)
        else:
            amount = rng.uniform(5.0, 20.0)
            amounts.append(amount)
            depletions.append(amount * rng.uniform(50.0, 200.0))
    return resource_types, amounts, depletions


def _mana(
    biomes: list[Biome],
    size: int,
    rng: Rng,
) -> tuple[list[int], list[int], set[int]]:
    """Рассчитывает плотность и регенерацию маны, расставляет лей-линии."""
    densities: list[int] = []
    regenerations: list[int] = []
    for biome in biomes:
        if biome is Biome.OCEAN:
            densities.append(0)
            regenerations.append(0)
            continue
        value = _MANA_BASE[biome] + rng.uniform(-10.0, 10.0)
        density = int(max(0.0, min(100.0, value)))
        densities.append(density)
        regenerations.append(max(1, density // 10))

    land = [index for index, biome in enumerate(biomes) if biome is not Biome.OCEAN]
    rng.shuffle(land)
    target = min(8, max(1, size // 12))
    spacing = max(2, size // 8)
    ley_lines: set[int] = set()
    for index in land:
        if len(ley_lines) >= target:
            break
        x = index % size
        y = index // size
        if all(
            max(abs(x - chosen % size), abs(y - chosen // size)) >= spacing for chosen in ley_lines
        ):
            ley_lines.add(index)

    for index in ley_lines:
        densities[index] = 100
        regenerations[index] = 50
    return densities, regenerations, ley_lines


def _population(
    biomes: list[Biome],
    fertilities: list[float],
    rng: Rng,
) -> tuple[list[int], list[int]]:
    """Рассчитывает ёмкость и стартовое население тайлов."""
    capacities: list[int] = []
    populations: list[int] = []
    for index, biome in enumerate(biomes):
        if biome is Biome.OCEAN:
            capacities.append(0)
            populations.append(0)
            continue
        capacity = int(fertilities[index] * 5 + 20)
        capacities.append(capacity)
        populations.append(rng.int(0, capacity // 2))
    return capacities, populations
