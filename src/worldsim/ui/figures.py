"""Построение карт мира для интерфейса (не зависит от Streamlit)."""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from worldsim.core.faction import Faction
from worldsim.core.geography import RegionData, ResourceType
from worldsim.core.state import WorldState
from worldsim.vcs.commit import Commit

NEUTRAL_COLOR = "#9e9e9e"
LAYERS: tuple[str, ...] = (
    "biomes",
    "political",
    "culture",
    "resources",
    "happiness",
    "unrest",
    "army",
    "mana",
)

_CULTURE_COLORS: tuple[str, ...] = (
    "#e57373",
    "#64b5f6",
    "#81c784",
    "#ffb74d",
    "#ba68c8",
    "#4db6ac",
    "#f06292",
    "#a1887f",
)

_RESOURCE_COLORS: dict[ResourceType, str] = {
    ResourceType.NONE: NEUTRAL_COLOR,
    ResourceType.FOOD: "#8bc34a",
    ResourceType.WOOD: "#6d4c41",
    ResourceType.IRON: "#78909c",
    ResourceType.GOLD: "#fbc02d",
    ResourceType.MANA: "#7e57c2",
}


def biome_figure(state: WorldState) -> go.Figure:
    """Строит карту биомов текущего снимка мира."""
    tiles = state.map.tiles
    return _scatter_figure(
        state,
        colors=[tile.biome.color for tile in tiles],
        texts=[_tile_hover(state, tile) for tile in tiles],
        title=f"Мир, год {state.year}",
    )


def political_figure(state: WorldState) -> go.Figure:
    """Строит политическую карту: цвет фракции, нейтральные тайлы серые."""
    factions = {faction.id: faction for faction in state.factions}
    tiles = state.map.tiles
    colors: list[str] = []
    texts: list[str] = []
    for tile in tiles:
        faction = factions.get(tile.owner_id) if tile.owner_id is not None else None
        if faction is None:
            colors.append(NEUTRAL_COLOR)
            texts.append(
                f"({tile.x}, {tile.y}) нейтральная территория; население {tile.population}"
            )
        else:
            colors.append(faction.color)
            texts.append(
                f"({tile.x}, {tile.y}) {faction.name} ({faction.culture}); "
                f"население {tile.population}; армия {faction.army_size:.0f}; "
                f"мощь {faction.military_power:.0f}"
            )
    return _scatter_figure(
        state,
        colors=colors,
        texts=texts,
        title=f"Политическая карта, год {state.year}",
    )


def tile_layer_figure(state: WorldState, layer: str) -> go.Figure:
    """Строит слой карты по выбранному показателю.

    Args:
        state: Снимок мира.
        layer: Один из ``LAYERS``: биомы, политика, ресурсы, счастье,
            недовольство, армия или мана.

    Raises:
        ValueError: Если слой неизвестен.
    """
    if layer not in LAYERS:
        raise ValueError(f"неизвестный слой карты: {layer!r}")
    tiles = state.map.tiles
    colors = _layer_colors(state, layer)
    return _scatter_figure(
        state,
        colors=colors,
        texts=[_tile_hover(state, tile) for tile in tiles],
        title=f"Слой «{layer}», год {state.year}",
    )


def _layer_colors(state: WorldState, layer: str) -> list[str]:
    """Считает цвета всех тайлов для выбранного слоя."""
    tiles = state.map.tiles
    factions = {faction.id: faction for faction in state.factions}
    if layer == "happiness":
        populated = [tile for tile in tiles if tile.is_land and tile.population > 0]
        if not populated:
            return [NEUTRAL_COLOR for _ in tiles]
        low = min(tile.happiness for tile in populated)
        high = max(tile.happiness for tile in populated)
        colors: list[str] = []
        for tile in tiles:
            if not tile.is_land or tile.population <= 0:
                colors.append(NEUTRAL_COLOR)
            else:
                ratio = _normalize(tile.happiness, low, high)
                colors.append(_lerp_color("#c62828", "#2e7d32", ratio))
        return colors
    if layer == "unrest":
        populated = [tile for tile in tiles if tile.is_land and tile.population > 0]
        if not populated:
            return [NEUTRAL_COLOR for _ in tiles]
        low = min(tile.unrest for tile in populated)
        high = max(tile.unrest for tile in populated)
        colors = []
        for tile in tiles:
            if not tile.is_land or tile.population <= 0:
                colors.append(NEUTRAL_COLOR)
            else:
                ratio = _normalize(tile.unrest, low, high)
                colors.append(_lerp_color("#e0e0e0", "#b71c1c", ratio))
        return colors
    if layer == "army":
        present = [tile.army_presence for tile in tiles if tile.army_presence > 0]
        if not present:
            return [NEUTRAL_COLOR for _ in tiles]
        high = max(present)
        colors = []
        for tile in tiles:
            if tile.army_presence <= 0:
                colors.append(NEUTRAL_COLOR)
            else:
                ratio = _normalize(tile.army_presence, 0.0, float(high))
                colors.append(_lerp_color("#ffe0b2", "#bf360c", ratio))
        return colors
    return [_layer_color(tile, layer, factions) for tile in tiles]


def _normalize(value: float, low: float, high: float) -> float:
    """Нормализует значение в диапазон 0–1; при равных значениях — 0.5."""
    if high - low < 1e-9:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


def timeline_figure(commits: Sequence[Commit]) -> go.Figure:
    """Строит граф истории: узлы — коммиты, рёбра — родитель → ребёнок.

    Ось X — год коммита, ось Y — ветка; hover показывает сообщение, год,
    ветку и короткий хеш.
    """
    ordered = sorted(
        commits,
        key=lambda commit: (commit.year, commit.created_at, commit.id),
    )
    branches = sorted({commit.branch for commit in ordered})
    positions = {name: index for index, name in enumerate(branches)}
    by_id = {commit.id: commit for commit in ordered}

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for commit in ordered:
        if commit.parent_id is None:
            continue
        parent = by_id.get(commit.parent_id)
        if parent is None:
            continue
        edge_x.extend([float(parent.year), float(commit.year), None])
        edge_y.extend(
            [
                float(positions[parent.branch]),
                float(positions[commit.branch]),
                None,
            ]
        )

    figure = go.Figure()
    if edge_x:
        figure.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line={"color": "#9e9e9e", "width": 2},
                hoverinfo="skip",
                name="Родитель → ребёнок",
            )
        )
    figure.add_trace(
        go.Scatter(
            x=[float(commit.year) for commit in ordered],
            y=[float(positions[commit.branch]) for commit in ordered],
            mode="markers",
            marker={"size": 12, "color": "#2e7d32"},
            text=[
                f"{commit.message}\n{commit.year}, {commit.branch}\n{commit.id[:8]}"
                for commit in ordered
            ],
            hovertemplate="%{text}<extra></extra>",
            name="Коммиты",
        )
    )
    figure.update_layout(
        title="История мира",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        xaxis={"title": "Год", "dtick": 1},
        yaxis={
            "tickmode": "array",
            "tickvals": [float(value) for value in positions.values()],
            "ticktext": branches,
            "title": "Ветка",
        },
        showlegend=False,
    )
    return figure


def _scatter_figure(
    state: WorldState,
    *,
    colors: list[str],
    texts: list[str],
    title: str,
) -> go.Figure:
    """Собирает фигуру из точек с заданными цветами и подсказками."""
    tiles = state.map.tiles
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[tile.x for tile in tiles],
                y=[tile.y for tile in tiles],
                mode="markers",
                marker={
                    "color": colors,
                    "size": 12,
                    "symbol": "square",
                    "line": {"width": 0},
                },
                text=texts,
                hovertemplate="%{text}<extra></extra>",
                name="Тайлы",
            )
        ]
    )
    figure.update_layout(
        title=title,
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False, "autorange": "reversed"},
    )
    return figure


def _layer_color(tile: RegionData, layer: str, factions: dict[int, Faction]) -> str:
    """Возвращает цвет тайла для выбранного слоя."""
    if layer == "biomes":
        return tile.biome.color
    if layer == "political":
        faction = factions.get(tile.owner_id) if tile.owner_id is not None else None
        return faction.color if faction is not None else NEUTRAL_COLOR
    if layer == "culture":
        return _culture_color(tile)
    if layer == "resources":
        return _RESOURCE_COLORS[tile.resource_type]
    if tile.ley_line:
        return "#00e5ff"
    return _lerp_color("#e3f2fd", "#4a148c", tile.mana_density / 100.0)


def _culture_color(tile: RegionData) -> str:
    """Цвет культуры тайла."""
    if tile.culture_id is not None:
        return _CULTURE_COLORS[tile.culture_id % len(_CULTURE_COLORS)]
    if tile.culture is not None:
        index = sum(ord(char) for char in tile.culture) % len(_CULTURE_COLORS)
        return _CULTURE_COLORS[index]
    return NEUTRAL_COLOR


def _tile_hover(state: WorldState, tile: RegionData) -> str:
    """Собирает подробную подсказку тайла."""
    factions = {faction.id: faction for faction in state.factions}
    faction = factions.get(tile.owner_id) if tile.owner_id is not None else None
    owner = f"{faction.name} ({faction.culture})" if faction is not None else "нейтраль"
    river = "да" if tile.has_river else "нет"
    ley = ", лей-линия" if tile.ley_line else ""
    return (
        f"({tile.x}, {tile.y}) {tile.biome.value}; владелец: {owner}; "
        f"население {tile.population}/{tile.population_capacity}; "
        f"плодородие {tile.fertility:.0f}; высота {tile.elevation:.0f}; река: {river}; "
        f"ресурс: {tile.resource_type.value} ({tile.resource_amount:.0f}), "
        f"запас {tile.resource_depletion:.0f}; инфраструктура {tile.infrastructure:.0f}; "
        f"счастье {tile.happiness:.0f}; урбанизация {tile.urbanization:.0f}; "
        f"армия {tile.army_presence}; фортификация {tile.fortification:.0f}; "
        f"недовольство {tile.unrest:.0f}; "
        f"мана {tile.mana_density}/{tile.mana_regeneration}{ley}"
    )


def _lerp_color(start: str, end: str, ratio: float) -> str:
    """Линейно смешивает два hex-цвета."""
    ratio = max(0.0, min(1.0, ratio))
    start_rgb = _parse_hex(start)
    end_rgb = _parse_hex(end)
    mixed = tuple(
        round(first + (second - first) * ratio)
        for first, second in zip(start_rgb, end_rgb, strict=True)
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _parse_hex(color: str) -> tuple[int, int, int]:
    """Разбирает ``#RRGGBB`` в три компоненты."""
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
