"""Streamlit-приложение WorldSim: генерация мира, шаг времени и летопись."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import worldsim
from worldsim.ai.chronicler import fallback_chapter, save_chapter
from worldsim.ai.client import AIUnavailableError
from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.metrics import compute_faction_stats
from worldsim.engine.rules import Rule
from worldsim.engine.rules.magic import AcademyRule, MagicResearchRule, ManaRule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.engine.rules.random_events import FamineRule, PlagueRule
from worldsim.generator.world import create_world
from worldsim.ui.ai_panel import (
    create_ai_world,
    manual_config,
    safe_client,
    write_chapter_for_engine,
)
from worldsim.ui.figures import LAYERS, tile_layer_figure, timeline_figure
from worldsim.ui.history import (
    checkout_snapshot,
    commit_world,
    diff_to_parent,
    run_alternative,
)
from worldsim.vcs.repo import RepositoryError, WorldRepo

_DEFAULT_RULES: list[Rule] = [
    PlagueRule(),
    FamineRule(),
    PopulationGrowthRule(),
    ManaRule(),
    AcademyRule(),
    MagicResearchRule(),
]


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
        layer = st.selectbox("Слой карты", LAYERS, index=0)
        repo_dir = st.text_input("Каталог истории", value=".worldsim")

    engine: SimulationEngine | None = st.session_state.get("engine", None)
    if engine is None:
        st.info("Сгенерируйте мир в панели слева, чтобы начать симуляцию.")
        return

    with st.sidebar.expander("Подключённые правила"):
        st.dataframe(
            [
                {
                    "Правило": rule.name,
                    "Приоритет": rule.priority,
                    "Включено": getattr(rule, "enabled", True),
                }
                for rule in engine.rules
            ],
            use_container_width=True,
        )

    world_tab, history_tab, ai_tab = st.tabs(["Мир", "История", "ИИ"])

    with world_tab:
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
        st.plotly_chart(tile_layer_figure(state, layer), use_container_width=True)

        population = sum(tile.population for tile in state.map.tiles)
        metrics = st.columns(3)
        metrics[0].metric("Год", state.year)
        metrics[1].metric("Население", population)
        metrics[2].metric("Событий", len(engine.chronicle))

        _render_factions(state)
        _render_trade(state)
        _render_tile_panel(state)
        _render_chronicle(engine)

    with history_tab:
        _render_history(engine, repo_dir)

    with ai_tab:
        _render_ai(engine)


def _render_ai(engine: SimulationEngine) -> None:
    """Вкладка ИИ: генерация мира по описанию и глава летописи."""
    st.subheader("Мир по описанию")
    description = st.text_area(
        "Описание мира",
        value="Мир двух фракций: северные милитаристы и южные торговцы.",
        height=120,
    )
    config = engine.state.config
    fallback = manual_config(
        seed=config.seed,
        size=config.size,
        initial_factions=config.initial_factions,
        aggression=config.aggression,
        growth_rate=config.growth_rate,
        plague_chance=config.plague_chance,
        magic_level=config.magic_level,
    )
    with st.expander("Ручная конфигурация (fallback)"):
        st.json(fallback.model_dump())

    if st.button("Создать мир по описанию"):
        client, error = safe_client()
        if client is None:
            st.warning(f"ИИ недоступен: {error}. Использую ручную конфигурацию.")
            st.session_state["engine"] = build_engine(create_world(fallback))
            st.rerun()
        else:
            with st.spinner("ИИ проектирует мир..."):
                try:
                    world, _blueprint, path = create_ai_world(description, client)
                except AIUnavailableError as exc:
                    st.error(f"Не удалось создать мир: {exc}")
                else:
                    st.session_state["engine"] = build_engine(world)
                    st.success(f"Мир создан, черновик сохранён: {path}")
                    st.rerun()

    st.divider()
    st.subheader("Глава летописи")
    max_year = max(0, engine.state.year)
    columns = st.columns(2)
    with columns[0]:
        year_from = st.number_input("С года", min_value=0, max_value=max_year, value=0)
    with columns[1]:
        year_to = st.number_input("По год", min_value=0, max_value=max_year, value=max_year)
    directory = st.text_input("Каталог глав", value="chronicle")

    if st.button("Написать главу"):
        client, error = safe_client()
        if client is None:
            st.warning(f"ИИ недоступен: {error}. Сохраняю fallback-главу.")
            events = engine.chronicle.between(int(year_from), int(year_to))
            text = fallback_chapter(events, int(year_from), int(year_to))
            path = save_chapter(
                Path(directory),
                text,
                year_from=int(year_from),
                year_to=int(year_to),
                seed=engine.state.config.seed,
            )
            st.session_state["chapter_text"] = text
            st.session_state["chapter_path"] = str(path)
        else:
            with st.spinner("Хронист пишет главу..."):
                try:
                    path = write_chapter_for_engine(
                        engine,
                        client,
                        int(year_from),
                        int(year_to),
                        directory=Path(directory),
                        seed=engine.state.config.seed,
                    )
                except AIUnavailableError as exc:
                    st.error(f"Не удалось написать главу: {exc}")
                else:
                    st.session_state["chapter_text"] = path.read_text(encoding="utf-8")
                    st.session_state["chapter_path"] = str(path)
                    st.success(f"Глава сохранена: {path}")

    chapter_text = st.session_state.get("chapter_text")
    if isinstance(chapter_text, str):
        st.markdown(chapter_text)
        chapter_path = Path(st.session_state["chapter_path"])
        st.download_button(
            "Скачать главу .md",
            data=chapter_text,
            file_name=chapter_path.name,
        )


def _render_factions(state: WorldState) -> None:
    """Показывает таблицу фракций и ресурсы выбранной фракции."""
    if not state.factions:
        return
    stats = compute_faction_stats(state)
    rows = [
        {
            "Цвет": faction.color,
            "Имя": faction.name,
            "Культура": faction.culture,
            "Идеология": faction.ideology.value,
            "Территории": stats[faction.id].tiles,
            "Население": stats[faction.id].population,
            "Казна": round(faction.treasury, 1),
            "Еда": round(faction.food_stockpile, 1),
            "Технологии": round(faction.tech_level, 2),
            "Армия": round(faction.army_size, 1),
            "Мощь": round(stats[faction.id].military_power, 1),
            "Магия": round(faction.magic_power(), 2),
            "Мана": faction.mana_pool,
            "Мораль": round(faction.morale, 2),
        }
        for faction in state.factions
    ]
    st.subheader("Фракции")
    st.dataframe(rows, use_container_width=True)

    names = {faction.id: faction.name for faction in state.factions}
    selected = st.selectbox(
        "Ресурсы фракции",
        list(names),
        format_func=lambda faction_id: names[faction_id],
    )
    faction = next(item for item in state.factions if item.id == selected)
    st.json(faction.resources)


def _render_trade(state: WorldState) -> None:
    """Показывает действующие торговые маршруты."""
    if not state.trade_routes:
        return
    st.subheader("Торговля")
    st.dataframe(
        [
            {
                "От": route.from_tile,
                "К": route.to_tile,
                "Ресурс": route.resource.value,
                "Ёмкость": round(route.capacity, 2),
            }
            for route in state.trade_routes
        ],
        use_container_width=True,
    )


def _render_tile_panel(state: WorldState) -> None:
    """Показывает параметры выбранного тайла."""
    st.subheader("Тайл")
    tile_id = st.number_input(
        "Идентификатор тайла",
        min_value=0,
        max_value=len(state.map.tiles) - 1,
        value=0,
        step=1,
    )
    tile = state.map.by_id(int(tile_id))
    columns = st.columns(4)
    columns[0].metric("Население", f"{tile.population}/{tile.population_capacity}")
    columns[1].metric("Плодородие", f"{tile.fertility:.0f}")
    columns[2].metric("Счастье", f"{tile.happiness:.0f}")
    columns[3].metric("Недовольство", f"{tile.unrest:.0f}")
    st.write(
        f"Координаты ({tile.x}, {tile.y}), биом {tile.biome.value}, "
        f"высота {tile.elevation:.0f}, река: {'да' if tile.has_river else 'нет'}, "
        f"ресурс {tile.resource_type.value} ({tile.resource_amount:.0f}, "
        f"запас {tile.resource_depletion:.0f}), инфраструктура {tile.infrastructure:.0f}, "
        f"урбанизация {tile.urbanization:.0f}, армия {tile.army_presence}, "
        f"фортификация {tile.fortification:.0f}, "
        f"мана {tile.mana_density}/{tile.mana_regeneration}"
        f"{', лей-линия' if tile.ley_line else ''}"
    )


def _render_history(engine: SimulationEngine, repo_dir: str) -> None:
    """Панель истории: коммиты, checkout, ветки и альтернативные реальности."""
    st.subheader("История версий")
    repo = WorldRepo(Path(repo_dir))
    commits = repo.log()
    selected_id: str | None = None

    if not commits:
        st.info("Коммитов пока нет — сохраните текущий мир ниже.")
    else:
        st.plotly_chart(timeline_figure(commits), use_container_width=True)
        labels = {
            commit.id: (f"{commit.year} · {commit.branch} · {commit.id[:8]} — {commit.message}")
            for commit in commits
        }
        selected_id = st.selectbox(
            "Коммит",
            list(labels),
            format_func=lambda commit_id: labels[commit_id],
        )
        selected = next(commit for commit in commits if commit.id == selected_id)
        st.markdown(diff_to_parent(repo, selected).to_markdown())

        st.text_input("Имя новой ветки", value="alt", key="branch_name")
        columns = st.columns(2)
        if columns[0].button("Checkout"):
            state, chronicle = checkout_snapshot(repo, selected.id)
            st.session_state["engine"] = SimulationEngine(
                _DEFAULT_RULES,
                chronicle,
                initial_state=state,
            )
            st.rerun()
        if columns[1].button("Создать ветку"):
            try:
                repo.create_branch(st.session_state["branch_name"], from_ref=selected.id)
            except RepositoryError as exc:
                st.error(str(exc))
            else:
                st.rerun()

        with st.expander("Создать альтернативную реальность"):
            aggression = st.slider(
                "Агрессивность мира",
                min_value=0.0,
                max_value=1.0,
                value=float(engine.state.config.aggression),
                step=0.05,
            )
            years = st.number_input("Лет вперёд", min_value=1, max_value=200, value=50)
            alt_branch = st.text_input("Ветка", value="alt", key="alt_branch")
            if st.button("Запустить альтернативу"):
                try:
                    commit, diff = run_alternative(
                        repo,
                        selected.id,
                        alt_branch,
                        aggression=aggression,
                        years=int(years),
                        rules=_DEFAULT_RULES,
                        message=f"alt: агрессия {aggression}",
                    )
                except (RepositoryError, ValueError) as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Коммит {commit.id[:8]} в ветке {alt_branch}")
                    st.markdown(diff.to_markdown())
                    state, chronicle = repo.checkout_branch(alt_branch)
                    st.session_state["engine"] = SimulationEngine(
                        _DEFAULT_RULES,
                        chronicle,
                        initial_state=state,
                    )
                    st.rerun()

    with st.expander("Закоммитить текущий мир"):
        message = st.text_input(
            "Сообщение коммита",
            value=f"год {engine.state.year}",
            key="commit_message",
        )
        if st.button("Создать коммит"):
            commit_world(repo, engine.state, engine.chronicle, message)
            st.rerun()


def _render_chronicle(engine: SimulationEngine) -> None:
    """Показывает летопись событий."""
    st.subheader("Летопись")
    st.markdown(engine.chronicle.to_markdown())


if __name__ == "__main__":
    main()
