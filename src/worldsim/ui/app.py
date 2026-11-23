"""Streamlit-приложение WorldSim: генерация мира, шаг времени и летопись."""

from __future__ import annotations

import streamlit as st

import worldsim
from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import Rule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.engine.rules.random_events import FamineRule, PlagueRule
from worldsim.generator.world import create_world
from worldsim.ui.figures import biome_figure

_DEFAULT_RULES: list[Rule] = [PlagueRule(), FamineRule(), PopulationGrowthRule()]


def build_engine(state: WorldState) -> SimulationEngine:
    """Создаёт движок с правилами базовой симуляции."""
    return SimulationEngine(_DEFAULT_RULES, Chronicle(), initial_state=state)


def main() -> None:
    """Точка входа Streamlit-страницы."""
    st.set_page_config(page_title="WorldSim", page_icon="🌍", layout="wide")
    st.title("🌍 WorldSim")
    st.caption(f"Версия {worldsim.__version__}")

    with st.sidebar:
        st.header("Параметры мира")
        seed = st.number_input("Сид", min_value=0, max_value=2**31 - 1, value=42, step=1)
        size = st.slider("Размер карты", min_value=32, max_value=128, value=64, step=8)
        if st.button("Сгенерировать мир"):
            config = WorldConfig(seed=int(seed), size=int(size))
            st.session_state["engine"] = build_engine(create_world(config))

    engine: SimulationEngine | None = st.session_state.get("engine", None)
    if engine is None:
        st.info("Сгенерируйте мир в панели слева, чтобы начать симуляцию.")
        return

    left, right = st.columns(2)
    with left:
        step_one = st.button("Следующий год")
    with right:
        step_ten = st.button("+10 лет")
    if step_one:
        engine.step()
    if step_ten:
        engine.run(10)

    state = engine.state
    st.plotly_chart(biome_figure(state), use_container_width=True)

    population = sum(tile.population for tile in state.map.tiles)
    metrics = st.columns(3)
    metrics[0].metric("Год", state.year)
    metrics[1].metric("Население", population)
    metrics[2].metric("Событий", len(engine.chronicle))

    st.subheader("Летопись")
    st.markdown(engine.chronicle.to_markdown())


if __name__ == "__main__":
    main()
