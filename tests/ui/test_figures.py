"""Тесты построения карт для интерфейса."""

from __future__ import annotations

import sys

import plotly.graph_objects as go
import pytest

from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.world import create_world
from worldsim.ui.figures import (
    LAYERS,
    NEUTRAL_COLOR,
    biome_figure,
    political_figure,
    tile_layer_figure,
)


def make_state(size: int = 8, seed: int = 1, factions: int = 2) -> WorldState:
    """Создаёт небольшой мир для проверки фигур."""
    return create_world(WorldConfig(seed=seed, size=size, initial_factions=factions))


def test_figure_has_point_per_tile() -> None:
    """На каждый тайл строится ровно одна точка."""
    state = make_state()
    figure = biome_figure(state)

    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    trace = figure.data[0]
    assert len(trace.x) == state.map.size * state.map.size
    assert len(trace.y) == state.map.size * state.map.size


def test_colors_match_biomes() -> None:
    """Цвет точки совпадает с цветом биома тайла."""
    state = make_state()
    trace = biome_figure(state).data[0]

    assert list(trace.marker.color) == [tile.biome.color for tile in state.map.tiles]


def test_hover_text_contains_biome_and_population() -> None:
    """Наведение показывает биом и население."""
    state = make_state()
    trace = biome_figure(state).data[0]

    assert trace.hovertemplate is not None
    assert "население" in trace.text[0]
    assert state.map.tiles[0].biome.value in trace.text[0]


def test_title_contains_year() -> None:
    """Заголовок карты содержит текущий год."""
    state = make_state()

    assert biome_figure(state).layout.title.text == "Мир, год 0"
    assert biome_figure(state.evolve(year=5)).layout.title.text == "Мир, год 5"


def test_figures_do_not_require_streamlit() -> None:
    """Модуль фигур не тянет Streamlit."""
    import worldsim.ui.figures as figures

    assert figures.biome_figure is biome_figure
    assert "streamlit" not in sys.modules


def make_mixed_state() -> WorldState:
    """Создаёт мир, где фракция владеет только одним тайлом."""
    from worldsim.core.faction import Faction, Ideology
    from worldsim.core.geography import Biome, RegionData, WorldMap

    faction = Faction(
        id=0,
        name="Альянс",
        color="#112233",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=0,
        army_size=10.0,
    )
    tiles = tuple(
        RegionData(
            id=index,
            x=index % 4,
            y=index // 4,
            biome=Biome.PLAINS,
            fertility=50.0,
            elevation=100.0,
            population=10,
            population_capacity=100,
            owner_id=0 if index == 0 else None,
        )
        for index in range(16)
    )
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=1),
        year=0,
        map=WorldMap(size=4, tiles=tiles),
        factions=(faction,),
    )


def test_political_colors_match_factions() -> None:
    """Политическая карта красит тайлы цветом фракции, нейтральные — серым."""
    state = make_mixed_state()
    figure = political_figure(state)
    factions = {faction.id: faction for faction in state.factions}

    expected = [
        factions[tile.owner_id].color if tile.owner_id is not None else NEUTRAL_COLOR
        for tile in state.map.tiles
    ]

    assert list(figure.data[0].marker.color) == expected
    assert expected.count(NEUTRAL_COLOR) == 15


def test_political_without_factions_is_gray() -> None:
    """Без фракций политическая карта полностью серая."""
    state = make_state(factions=0)

    figure = political_figure(state)

    assert len(figure.data[0].x) == state.map.size * state.map.size
    assert set(figure.data[0].marker.color) == {NEUTRAL_COLOR}


def test_political_hover_mentions_population() -> None:
    """Подсказка политической карты содержит население и владельца."""
    state = make_mixed_state()
    texts = political_figure(state).data[0].text

    assert any("население" in text for text in texts)
    assert any("нейтральная" in text for text in texts)
    assert any("Альянс" in text for text in texts)


def test_all_layers_build_points() -> None:
    """Каждый слой строит точку на каждый тайл."""
    state = make_state()

    for layer in LAYERS:
        figure = tile_layer_figure(state, layer)
        trace = figure.data[0]
        assert len(trace.x) == len(state.map.tiles)
        assert len(trace.marker.color) == len(state.map.tiles)


def test_layers_use_different_colors() -> None:
    """Биомный и политический слои различаются цветами."""
    state = make_state()

    biome_colors = list(tile_layer_figure(state, "biomes").data[0].marker.color)
    political_colors = list(tile_layer_figure(state, "political").data[0].marker.color)

    assert biome_colors != political_colors


def test_unknown_layer_is_rejected() -> None:
    """Неизвестный слой карты отклоняется."""
    state = make_state()

    with pytest.raises(ValueError, match="неизвестный слой"):
        tile_layer_figure(state, "unknown")
