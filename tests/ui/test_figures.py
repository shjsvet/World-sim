"""Тесты построения карт для интерфейса."""

from __future__ import annotations

import sys

import plotly.graph_objects as go

from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.world import create_world
from worldsim.ui.figures import biome_figure


def make_state(size: int = 8, seed: int = 1) -> WorldState:
    """Создаёт небольшой мир для проверки фигур."""
    return create_world(WorldConfig(seed=seed, size=size))


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
