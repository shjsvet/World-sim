"""Модели карты: биомы, ресурсы, климат, тайлы и сетка мира."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CITY_POPULATION_THRESHOLD = 1000
CITY_URBANIZATION_THRESHOLD = 50.0


class Biome(StrEnum):
    """Тип местности тайла и его базовые характеристики."""

    OCEAN = "ocean"
    COAST = "coast"
    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAINS = "mountains"
    DESERT = "desert"
    TUNDRA = "tundra"
    SWAMP = "swamp"

    @property
    def is_water(self) -> bool:
        """Является ли биом водой."""
        return self is Biome.OCEAN

    @property
    def base_fertility(self) -> float:
        """Базовое плодородие биома (0–100) до шума генератора."""
        return _BASE_FERTILITY[self]

    @property
    def base_elevation(self) -> float:
        """Базовая высота биома в метрах до шума генератора."""
        return _BASE_ELEVATION[self]

    @property
    def movement_cost(self) -> float:
        """Стоимость перемещения армии через тайл."""
        return _MOVEMENT_COST[self]

    @property
    def defense_bonus(self) -> float:
        """Бонус к защите тайла в бою."""
        return _DEFENSE_BONUS[self]

    @property
    def food_modifier(self) -> float:
        """Множитель производства еды биома."""
        return _FOOD_MODIFIER[self]

    @property
    def color(self) -> str:
        """Цвет биома в формате ``#RRGGBB`` для карты."""
        return _COLORS[self]

    @property
    def emoji(self) -> str:
        """Эмодзи биома для интерфейса."""
        return _EMOJI[self]


class ResourceType(StrEnum):
    """Главный ресурс тайла: один тайл — один ресурс."""

    NONE = "none"
    FOOD = "food"
    WOOD = "wood"
    IRON = "iron"
    GOLD = "gold"
    MANA = "mana"


class ClimateZone(StrEnum):
    """Климатический пояс тайла (задел под глобальное похолодание)."""

    TROPICAL = "tropical"
    TEMPERATE = "temperate"
    ARCTIC = "arctic"


class RegionData(BaseModel):
    """Неизменяемый тайл карты со всеми параметрами (TASK.md, раздел 7)."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    biome: Biome
    fertility: float = Field(ge=0, le=100)
    elevation: float = Field(ge=0, le=9000)
    has_river: bool = False
    climate_zone: ClimateZone = ClimateZone.TEMPERATE
    resource_type: ResourceType = ResourceType.NONE
    resource_amount: float = Field(default=0.0, ge=0)
    resource_depletion: float = Field(default=0.0, ge=0)
    infrastructure: float = Field(default=0.0, ge=0, le=100)
    population: int = Field(ge=0)
    population_capacity: int = Field(ge=0)
    culture: str | None = Field(default=None, min_length=1, max_length=64)
    happiness: float = Field(default=50.0, ge=0, le=100)
    urbanization: float = Field(default=0.0, ge=0, le=100)
    owner_id: int | None = Field(default=None, ge=0)
    army_presence: int = Field(default=0, ge=0)
    fortification: float = Field(default=0.0, ge=0, le=100)
    unrest: float = Field(default=0.0, ge=0, le=100)
    assimilation: float = Field(default=0.0, ge=0, le=1)
    mana_density: int = Field(default=0, ge=0, le=100)
    mana_regeneration: int = Field(default=0, ge=0)
    ley_line: bool = False

    @property
    def is_land(self) -> bool:
        """Является ли тайл сушей."""
        return not self.biome.is_water

    @property
    def is_city(self) -> bool:
        """Стал ли тайл городом (население и урбанизация выше порогов)."""
        return (
            self.population > CITY_POPULATION_THRESHOLD
            and self.urbanization >= CITY_URBANIZATION_THRESHOLD
        )

    def defense_multiplier(self) -> float:
        """Множитель защиты тайла с учётом фортификации и биома."""
        return 1.0 + self.fortification / 200.0 + self.biome.defense_bonus

    def food_output(self) -> float:
        """Производство еды тайла за год.

        Учитывает население, плодородие, биом, реку и инфраструктуру.
        """
        river_bonus = 0.1 if self.has_river else 0.0
        return (
            self.population
            * self.fertility
            / 100.0
            * self.biome.food_modifier
            * (1.0 + river_bonus + self.infrastructure / 200.0)
        )


class WorldMap(BaseModel):
    """Неизменяемая квадратная сетка тайлов с проверкой координат."""

    model_config = ConfigDict(frozen=True)

    size: int = Field(ge=1, le=1024)
    tiles: tuple[RegionData, ...]

    @model_validator(mode="after")
    def _validate_grid(self) -> Self:
        """Проверяет размер сетки и соответствие id и координат индексу."""
        expected = self.size * self.size
        if len(self.tiles) != expected:
            raise ValueError(f"ожидалось {expected} тайлов, получено {len(self.tiles)}")
        for index, tile in enumerate(self.tiles):
            expected_x = index % self.size
            expected_y = index // self.size
            if (tile.id, tile.x, tile.y) != (index, expected_x, expected_y):
                raise ValueError(
                    f"тайл #{index}: id={tile.id}, x={tile.x}, y={tile.y}; "
                    f"ожидалось id={index}, x={expected_x}, y={expected_y}"
                )
        return self

    def at(self, x: int, y: int) -> RegionData:
        """Возвращает тайл по координатам.

        Raises:
            IndexError: Если координаты выходят за границы карты.
        """
        if not (0 <= x < self.size and 0 <= y < self.size):
            raise IndexError(f"координаты ({x}, {y}) вне карты {self.size}x{self.size}")
        return self.tiles[y * self.size + x]

    def by_id(self, tile_id: int) -> RegionData:
        """Возвращает тайл по идентификатору.

        Raises:
            IndexError: Если идентификатор вне диапазона.
        """
        if not 0 <= tile_id < len(self.tiles):
            raise IndexError(f"тайл #{tile_id} вне диапазона 0..{len(self.tiles) - 1}")
        return self.tiles[tile_id]

    def neighbors(self, x: int, y: int, diagonal: bool = False) -> tuple[RegionData, ...]:
        """Возвращает соседей тайла в порядке N, E, S, W (и диагоналей).

        Args:
            x: Координата по горизонтали.
            y: Координата по вертикали.
            diagonal: Учитывать ли диагональных соседей.

        Returns:
            Кортеж существующих соседей в детерминированном порядке.
        """
        directions: list[tuple[int, int]] = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        if diagonal:
            directions += [(1, -1), (1, 1), (-1, 1), (-1, -1)]
        result: list[RegionData] = []
        for delta_x, delta_y in directions:
            next_x = x + delta_x
            next_y = y + delta_y
            if 0 <= next_x < self.size and 0 <= next_y < self.size:
                result.append(self.at(next_x, next_y))
        return tuple(result)

    def land_tiles(self) -> tuple[RegionData, ...]:
        """Возвращает все тайлы суши."""
        return tuple(tile for tile in self.tiles if tile.is_land)

    def cities(self) -> tuple[RegionData, ...]:
        """Возвращает все тайлы-города."""
        return tuple(tile for tile in self.tiles if tile.is_city)

    def tiles_with(self, owner_id: int | None) -> tuple[RegionData, ...]:
        """Возвращает тайлы, принадлежащие фракции (или никому при ``None``)."""
        return tuple(tile for tile in self.tiles if tile.owner_id == owner_id)

    def center(self) -> RegionData:
        """Возвращает центральный тайл карты."""
        return self.at(self.size // 2, self.size // 2)


_BASE_FERTILITY: dict[Biome, float] = {
    Biome.OCEAN: 0.0,
    Biome.COAST: 50.0,
    Biome.PLAINS: 80.0,
    Biome.FOREST: 60.0,
    Biome.HILLS: 45.0,
    Biome.MOUNTAINS: 20.0,
    Biome.DESERT: 10.0,
    Biome.TUNDRA: 15.0,
    Biome.SWAMP: 30.0,
}

_BASE_ELEVATION: dict[Biome, float] = {
    Biome.OCEAN: 0.0,
    Biome.COAST: 10.0,
    Biome.PLAINS: 100.0,
    Biome.FOREST: 200.0,
    Biome.HILLS: 500.0,
    Biome.MOUNTAINS: 2000.0,
    Biome.DESERT: 300.0,
    Biome.TUNDRA: 150.0,
    Biome.SWAMP: 20.0,
}

_MOVEMENT_COST: dict[Biome, float] = {
    Biome.OCEAN: 99.0,
    Biome.COAST: 1.0,
    Biome.PLAINS: 1.0,
    Biome.FOREST: 2.0,
    Biome.HILLS: 2.0,
    Biome.MOUNTAINS: 4.0,
    Biome.DESERT: 2.0,
    Biome.TUNDRA: 2.0,
    Biome.SWAMP: 3.0,
}

_DEFENSE_BONUS: dict[Biome, float] = {
    Biome.OCEAN: 0.0,
    Biome.COAST: 0.0,
    Biome.PLAINS: 0.0,
    Biome.FOREST: 0.2,
    Biome.HILLS: 0.3,
    Biome.MOUNTAINS: 0.5,
    Biome.DESERT: 0.1,
    Biome.TUNDRA: 0.1,
    Biome.SWAMP: 0.2,
}

_FOOD_MODIFIER: dict[Biome, float] = {
    Biome.OCEAN: 0.0,
    Biome.COAST: 0.8,
    Biome.PLAINS: 1.0,
    Biome.FOREST: 0.7,
    Biome.HILLS: 0.5,
    Biome.MOUNTAINS: 0.2,
    Biome.DESERT: 0.3,
    Biome.TUNDRA: 0.3,
    Biome.SWAMP: 0.4,
}

_COLORS: dict[Biome, str] = {
    Biome.OCEAN: "#1f4e79",
    Biome.COAST: "#5dade2",
    Biome.PLAINS: "#7cb342",
    Biome.FOREST: "#2e7d32",
    Biome.HILLS: "#8d6e63",
    Biome.MOUNTAINS: "#616161",
    Biome.DESERT: "#e0c068",
    Biome.TUNDRA: "#b0bec5",
    Biome.SWAMP: "#4e6e58",
}

_EMOJI: dict[Biome, str] = {
    Biome.OCEAN: "🌊",
    Biome.COAST: "🏖️",
    Biome.PLAINS: "🌾",
    Biome.FOREST: "🌲",
    Biome.HILLS: "⛰️",
    Biome.MOUNTAINS: "🏔️",
    Biome.DESERT: "🏜️",
    Biome.TUNDRA: "❄️",
    Biome.SWAMP: "🐸",
}
