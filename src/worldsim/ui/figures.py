"""Построение карт мира для интерфейса (не зависит от Streamlit)."""

from __future__ import annotations

import plotly.graph_objects as go

from worldsim.core.state import WorldState


def biome_figure(state: WorldState) -> go.Figure:
    """Строит карту биомов текущего снимка мира.

    Args:
        state: Снимок мира.

    Returns:
        Фигура Plotly: один маркер на тайл, цвет — цвет биома, наведение
        показывает координаты, биом и население.
    """
    tiles = state.map.tiles
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[tile.x for tile in tiles],
                y=[tile.y for tile in tiles],
                mode="markers",
                marker={
                    "color": [tile.biome.color for tile in tiles],
                    "size": 12,
                    "symbol": "square",
                    "line": {"width": 0},
                },
                text=[f"{tile.biome.value}, население {tile.population}" for tile in tiles],
                hovertemplate="(%{x}, %{y})<br>%{text}<extra></extra>",
                name="Тайлы",
            )
        ]
    )
    figure.update_layout(
        title=f"Мир, год {state.year}",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False, "autorange": "reversed"},
    )
    return figure
