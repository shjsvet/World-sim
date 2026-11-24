"""Streamlit-приложение WorldSim: генерация мира, шаг времени и летопись."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import worldsim
from worldsim.ai.chronicler import fallback_chapter, save_chapter
from worldsim.ai.client import AIUnavailableError
from worldsim.core.chronicle import Chronicle
from worldsim.core.faction import Faction
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.metrics import FactionStats, compute_faction_stats
from worldsim.engine.rules import Rule
from worldsim.engine.rules.army import ArmyMovementRule
from worldsim.engine.rules.magic import AcademyRule, MagicResearchRule, ManaRule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.engine.rules.random_events import FamineRule, PlagueRule
from worldsim.engine.rules.social import HappinessRule, UnrestRule, UrbanizationRule
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
    ArmyMovementRule(),
    HappinessRule(),
    UnrestRule(),
    UrbanizationRule(),
    ManaRule(),
    AcademyRule(),
    MagicResearchRule(),
]

_LAYER_LABELS = {
    "biomes": "Биомы",
    "political": "Политическая карта",
    "culture": "Культуры",
    "resources": "Ресурсы",
    "happiness": "Счастье",
    "unrest": "Недовольство",
    "army": "Армии",
    "mana": "Мана",
}

_LAYER_HINTS = {
    "biomes": "Цвет биома: леса, равнины, пустыни, горы, океан.",
    "political": "Цвет фракции-владельца; серый — нейтральная территория.",
    "culture": "Культура населения; серый — культура не задана.",
    "resources": "Главный ресурс тайла: еда, дерево, железо, золото, мана.",
    "happiness": (
        "Только населённые тайлы: красный — низкое счастье, "
        "зелёный — высокое; шкала растянута по текущему миру."
    ),
    "unrest": (
        "Только населённые тайлы: светлый — спокойно, тёмно-красный — "
        "высокое недовольство; шкала растянута по текущему миру."
    ),
    "army": (
        "Только тайлы с гарнизоном: чем темнее, тем больше солдат "
        "относительно максимального гарнизона в мире."
    ),
    "mana": "Плотность маны; голубой — лей-линия.",
}


def build_engine(state: WorldState) -> SimulationEngine:
    """Создаёт движок с правилами базовой симуляции."""
    return SimulationEngine(_DEFAULT_RULES, Chronicle(), initial_state=state)


def main() -> None:
    """Точка входа Streamlit-страницы."""
    st.set_page_config(
        page_title="WorldSim",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("🌍 WorldSim")
    st.caption(
        f"Симулятор мира · версия {worldsim.__version__} · "
        "карта, фракции, летопись и альтернативные реальности"
    )

    with st.sidebar:
        st.header("Параметры мира")
        seed = st.number_input(
            "Сид генерации",
            min_value=0,
            max_value=2**31 - 1,
            value=42,
            step=1,
            help="Одинаковый сид даёт одинаковый мир.",
        )
        size = st.slider(
            "Размер карты",
            min_value=32,
            max_value=128,
            value=64,
            step=8,
            help="Больше карта — больше фракций и деталей, но медленнее шаг.",
        )
        initial_factions = st.slider(
            "Фракций на старте",
            min_value=0,
            max_value=4,
            value=2,
            help="0 — мир без фракций, 4 — максимальная плотность.",
        )
        aggression = st.slider("Агрессивность", 0.0, 1.0, 0.5, 0.05)
        growth_rate = st.slider("Темп роста", 0.0, 0.2, 0.02, 0.01)
        plague_chance = st.slider("Шанс эпидемии", 0.0, 0.2, 0.01, 0.01)
        magic_level = st.slider("Уровень магии", 0.0, 1.0, 0.0, 0.05)
        if st.button("✨ Сгенерировать мир", type="primary", width="stretch"):
            st.session_state["engine"] = build_engine(
                create_world(
                    WorldConfig(
                        seed=int(seed),
                        size=int(size),
                        initial_factions=int(initial_factions),
                        aggression=float(aggression),
                        growth_rate=float(growth_rate),
                        plague_chance=float(plague_chance),
                        magic_level=float(magic_level),
                    )
                )
            )
            st.session_state.pop("chapter_text", None)
            st.rerun()

        st.divider()
        st.header("Отображение")
        layer = st.selectbox(
            "Слой карты",
            LAYERS,
            format_func=lambda name: _LAYER_LABELS.get(name, name),
        )
        repo_dir = st.text_input(
            "Каталог истории",
            value=".worldsim",
            help="Где хранить коммиты, ветки и теги.",
        )

    engine: SimulationEngine | None = st.session_state.get("engine")
    if engine is None:
        with st.spinner("Создаю стартовый мир…"):
            engine = build_engine(
                create_world(
                    WorldConfig(
                        seed=int(seed),
                        size=int(size),
                        initial_factions=int(initial_factions),
                        aggression=float(aggression),
                        growth_rate=float(growth_rate),
                        plague_chance=float(plague_chance),
                        magic_level=float(magic_level),
                    )
                )
            )
        st.session_state["engine"] = engine
        st.toast("Стартовый мир создан — нажмите «Следующий год»", icon="🌍")

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
            width="stretch",
            hide_index=True,
        )

    world_tab, history_tab, ai_tab = st.tabs(["🌍 Мир", "🕰 История", "✨ ИИ"])

    with world_tab:
        _render_world(engine, layer)
    with history_tab:
        _render_history(engine, repo_dir)
    with ai_tab:
        _render_ai(engine)


def _render_world(engine: SimulationEngine, layer: str) -> None:
    """Вкладка «Мир»: управление временем, карта, фракции и летопись."""
    state = engine.state
    controls = st.columns([1, 1, 1, 2])
    if controls[0].button("▶ Следующий год", width="stretch"):
        engine.step()
    if controls[1].button("⏩ +10 лет", width="stretch"):
        with st.spinner("Идёт 10 лет…"):
            engine.run(10)
    if controls[2].button("⏭ +50 лет", width="stretch"):
        with st.spinner("Идёт 50 лет…"):
            engine.run(50)
    controls[3].caption(
        f"Год {state.year} · фракций {len(state.factions)} · событий {len(engine.chronicle)}"
    )

    _render_metrics(engine)
    st.divider()

    st.subheader(f"Карта: {_LAYER_LABELS.get(layer, layer)}")
    with st.expander("Обозначения слоя"):
        st.caption(_LAYER_HINTS.get(layer, ""))
        st.caption("Наведите курсор на тайл, чтобы увидеть все параметры.")
    st.plotly_chart(
        tile_layer_figure(state, layer),
        width="stretch",
        config={"displayModeBar": False, "scrollZoom": True},
    )
    st.divider()

    _render_factions(state)
    _render_trade(state)
    _render_tile_panel(state)
    _render_chronicle(engine)


def _render_metrics(engine: SimulationEngine) -> None:
    """Верхние карточки с состоянием мира."""
    state = engine.state
    population = sum(tile.population for tile in state.map.tiles)
    happiness = sum(tile.happiness for tile in state.map.tiles if tile.owner_id is not None) / max(
        1, sum(1 for tile in state.map.tiles if tile.owner_id is not None)
    )
    wars = sum(1 for war in state.wars if war.active)
    metrics = st.columns(6)
    metrics[0].metric("Год", state.year)
    metrics[1].metric("Население", f"{population:,}".replace(",", " "))
    metrics[2].metric("Фракции", len(state.factions))
    metrics[3].metric("События", len(engine.chronicle))
    metrics[4].metric("Войны", wars)
    metrics[5].metric("Счастье", f"{happiness:.0f}")


def _render_factions(state: WorldState) -> None:
    """Таблица фракций и подробная карточка выбранной фракции."""
    if not state.factions:
        st.info("В этом мире нет фракций.")
        return
    stats = compute_faction_stats(state)
    st.subheader("Фракции")
    st.dataframe(
        [
            {
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
        ],
        width="stretch",
        hide_index=True,
    )

    names = {faction.id: faction.name for faction in state.factions}
    selected = st.selectbox(
        "Подробнее о фракции",
        list(names),
        format_func=lambda faction_id: names[faction_id],
    )
    faction = next(item for item in state.factions if item.id == selected)
    _render_faction_card(state, faction, stats[faction.id])


def _render_faction_card(state: WorldState, faction: Faction, stats: FactionStats) -> None:
    """Карточка выбранной фракции: статус, экономика, магия и ресурсы."""
    with st.container(border=True):
        st.markdown(f"### {faction.name}")
        status = _faction_status(state, faction.id)
        st.caption(
            f"Культура: {faction.culture} · идеология: {faction.ideology.value} · "
            f"столица: {faction.capital_tile_id if faction.capital_tile_id is not None else '—'} · "
            f"{status}"
        )
        columns = st.columns(6)
        columns[0].metric("Армия", f"{faction.army_size:.1f}")
        columns[1].metric("Боевая мощь", f"{stats.military_power:.0f}")
        columns[2].metric("Магия", f"{faction.magic_power():.2f}")
        columns[3].metric("Казна", f"{faction.treasury:.0f}")
        columns[4].metric("Еда", f"{faction.food_stockpile:.0f}")
        columns[5].metric("Мораль", f"{faction.morale:.2f}")

        left, right = st.columns(2)
        with left:
            st.caption("Ресурсы на складе")
            if faction.resources:
                st.dataframe(
                    [
                        {"Ресурс": key, "Количество": round(value, 1)}
                        for key, value in sorted(faction.resources.items())
                    ],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.caption("Склад пуст.")
        with right:
            schools = ", ".join(school.value for school in faction.magic_schools)
            st.caption(
                f"Школы магии: {schools or '—'} · "
                f"мана: {faction.mana_pool} · доход: {stats.mana_income}"
            )
            academies = [item for item in state.academies if item.faction_id == faction.id]
            st.caption(
                "Академии: "
                + (
                    ", ".join(
                        f"{item.school.value} (ур. {item.level}, тайл {item.tile_id})"
                        for item in academies
                    )
                    if academies
                    else "—"
                )
            )


def _faction_status(state: WorldState, faction_id: int) -> str:
    """Кратко описывает войну или перемирие фракции."""
    for war in state.wars:
        if faction_id not in {war.attacker_id, war.defender_id}:
            continue
        other = war.defender_id if war.attacker_id == faction_id else war.attacker_id
        if war.active:
            return f"в войне с фракцией {other}"
        if war.truce_until_year is not None and war.truce_until_year >= state.year:
            return f"перемирие с фракцией {other} до {war.truce_until_year}"
    return "в мире"


def _render_trade(state: WorldState) -> None:
    """Показывает действующие торговые маршруты."""
    if not state.trade_routes:
        return
    with st.expander(f"Торговые маршруты ({len(state.trade_routes)})"):
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
            width="stretch",
            hide_index=True,
        )


def _render_tile_panel(state: WorldState) -> None:
    """Показывает тайл по ID или по координатам."""
    st.subheader("Тайл")
    size = state.map.size
    if "tile_id" not in st.session_state:
        st.session_state["tile_id"] = 0
    if not 0 <= int(st.session_state["tile_id"]) < len(state.map.tiles):
        st.session_state["tile_id"] = 0
    for key in ("coord_x", "coord_y"):
        if key in st.session_state and not 0 <= int(st.session_state[key]) < size:
            st.session_state[key] = 0
    tile = state.map.by_id(int(st.session_state["tile_id"]))

    mode = st.radio(
        "Как выбрать тайл",
        ["По ID", "По координатам"],
        horizontal=True,
        key="tile_mode",
    )
    if mode == "По ID":
        controls = st.columns([1, 1, 3])
        if controls[0].button("Следующий тайл"):
            next_tile = state.map.by_id((tile.id + 1) % len(state.map.tiles))
            st.session_state["tile_id"] = next_tile.id
            st.session_state["coord_x"] = next_tile.x
            st.session_state["coord_y"] = next_tile.y
        st.number_input(
            "Идентификатор тайла",
            min_value=0,
            max_value=len(state.map.tiles) - 1,
            step=1,
            key="tile_id",
        )
        tile = state.map.by_id(int(st.session_state["tile_id"]))
        controls[2].caption("Координаты тайла — (x, y) от левого верхнего угла карты.")
    else:
        if "coord_x" not in st.session_state:
            st.session_state["coord_x"] = tile.x
        if "coord_y" not in st.session_state:
            st.session_state["coord_y"] = tile.y
        controls = st.columns([1, 1, 2])
        x = controls[0].number_input(
            "X",
            min_value=0,
            max_value=size - 1,
            step=1,
            key="coord_x",
        )
        y = controls[1].number_input(
            "Y",
            min_value=0,
            max_value=size - 1,
            step=1,
            key="coord_y",
        )
        tile = state.map.at(int(x), int(y))
        st.session_state["tile_id"] = tile.id
        controls[2].caption(
            f"Тайл #{tile.id} по координатам ({tile.x}, {tile.y}). "
            "X и Y можно менять стрелками или вводить вручную."
        )

    owner = "нейтральный"
    if tile.owner_id is not None:
        owner_faction = next(
            (item for item in state.factions if item.id == tile.owner_id),
            None,
        )
        if owner_faction is not None:
            owner = owner_faction.name

    culture = tile.culture or "—"
    if tile.culture_id is not None:
        culture_obj = next(
            (item for item in state.cultures if item.id == tile.culture_id),
            None,
        )
        if culture_obj is not None:
            culture = culture_obj.name

    religion = "—"
    if tile.religion_id is not None:
        religion_obj = next(
            (item for item in state.religions if item.id == tile.religion_id),
            None,
        )
        if religion_obj is not None:
            religion = religion_obj.name

    with st.container(border=True):
        st.markdown(f"### Тайл #{tile.id} · координаты ({tile.x}, {tile.y})")
        st.caption(
            f"{tile.biome.value} · владелец: {owner} · культура: {culture} · религия: {religion}"
        )
        metrics = st.columns(4)
        metrics[0].metric(
            "Население",
            f"{tile.population:,} / {tile.population_capacity:,}".replace(",", " "),
        )
        metrics[1].metric("Счастье", f"{tile.happiness:.0f}")
        metrics[2].metric("Недовольство", f"{tile.unrest:.0f}")
        metrics[3].metric("Плодородие", f"{tile.fertility:.0f}")

        left, right = st.columns(2)
        with left:
            st.markdown("**Природа и ресурсы**")
            st.dataframe(
                [
                    {"Параметр": "Биом", "Значение": tile.biome.value},
                    {"Параметр": "Климат", "Значение": tile.climate_zone.value},
                    {"Параметр": "Высота", "Значение": f"{tile.elevation:.0f} м"},
                    {
                        "Параметр": "Река",
                        "Значение": "да" if tile.has_river else "нет",
                    },
                    {"Параметр": "Ресурс", "Значение": tile.resource_type.value},
                    {
                        "Параметр": "Добыча / запас",
                        "Значение": (f"{tile.resource_amount:.1f} / {tile.resource_depletion:.1f}"),
                    },
                    {
                        "Параметр": "Инфраструктура",
                        "Значение": f"{tile.infrastructure:.0f}",
                    },
                    {
                        "Параметр": "Мана (плотность / регенерация)",
                        "Значение": f"{tile.mana_density} / {tile.mana_regeneration}",
                    },
                    {
                        "Параметр": "Лей-линия",
                        "Значение": "да" if tile.ley_line else "нет",
                    },
                ],
                width="stretch",
                hide_index=True,
            )
        with right:
            st.markdown("**Общество и армия**")
            st.dataframe(
                [
                    {"Параметр": "Владелец", "Значение": owner},
                    {"Параметр": "Культура", "Значение": culture},
                    {"Параметр": "Религия", "Значение": religion},
                    {
                        "Параметр": "Урбанизация",
                        "Значение": f"{tile.urbanization:.0f}",
                    },
                    {
                        "Параметр": "Армия (гарнизон)",
                        "Значение": f"{tile.army_presence}",
                    },
                    {
                        "Параметр": "Фортификация",
                        "Значение": f"{tile.fortification:.0f}",
                    },
                    {
                        "Параметр": "Ассимиляция",
                        "Значение": f"{tile.assimilation:.2f}",
                    },
                    {
                        "Параметр": "Культурное напряжение",
                        "Значение": f"{tile.cultural_tension:.0f}",
                    },
                    {
                        "Параметр": "Город",
                        "Значение": "да" if tile.is_city else "нет",
                    },
                ],
                width="stretch",
                hide_index=True,
            )


def _render_chronicle(engine: SimulationEngine) -> None:
    """Показывает летопись с фильтрами и выгрузкой."""
    st.subheader("Летопись")
    events = engine.chronicle.all_events()
    if not events:
        st.info("Событий пока нет — нажмите «Следующий год».")
        return

    event_types = sorted({event.type.value for event in events})
    factions = sorted({item for event in events for item in event.faction_ids})
    with st.expander("Фильтры летописи", expanded=False):
        columns = st.columns(3)
        type_filter = columns[0].selectbox(
            "Тип события",
            ["Все", *event_types],
        )
        faction_filter = columns[1].selectbox(
            "Фракция",
            ["Все", *factions],
        )
        year_min = min(event.year for event in events)
        year_max = max(event.year for event in events)
        if year_min == year_max:
            year_from, year_to = year_min, year_max
            columns[2].caption(f"Год: {year_min}")
        else:
            year_from, year_to = columns[2].slider(
                "Годы",
                min_value=year_min,
                max_value=year_max,
                value=(year_min, year_max),
            )

    filtered = [
        event
        for event in events
        if (type_filter == "Все" or event.type.value == type_filter)
        and (faction_filter == "Все" or faction_filter in event.faction_ids)
        and year_from <= event.year <= year_to
    ]
    st.caption(f"Показано событий: {len(filtered)} из {len(events)}")
    if filtered:
        chronicle = Chronicle()
        for event in filtered:
            chronicle.add(event)
        st.markdown(chronicle.to_markdown())
        st.download_button(
            "Скачать летопись .md",
            data=chronicle.to_markdown(),
            file_name=f"chronicle_{year_from}_{year_to}.md",
        )
    else:
        st.info("Под выбранные фильтры событий нет.")


def _render_history(engine: SimulationEngine, repo_dir: str) -> None:
    """Панель истории: коммиты, checkout, ветки и альтернативные реальности."""
    st.subheader("История версий")
    repo = WorldRepo(Path(repo_dir))
    commits = repo.log()
    st.caption(
        f"Репозиторий: `{Path(repo_dir).resolve()}` · ветка: "
        f"{repo.current_branch()} · коммитов: {len(commits)}"
    )
    selected_id: str | None = None

    if not commits:
        st.info("Коммитов пока нет — сохраните текущий мир ниже.")
    else:
        st.plotly_chart(
            timeline_figure(commits),
            width="stretch",
            config={"displayModeBar": False},
        )
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
        if columns[0].button("Переключиться на коммит", width="stretch"):
            state, chronicle = checkout_snapshot(repo, selected.id)
            st.session_state["engine"] = SimulationEngine(
                _DEFAULT_RULES,
                chronicle,
                initial_state=state,
            )
            st.rerun()
        if columns[1].button("Создать ветку", width="stretch"):
            try:
                repo.create_branch(st.session_state["branch_name"], from_ref=selected.id)
            except RepositoryError as exc:
                st.error(str(exc))
            else:
                st.success(f"Ветка {st.session_state['branch_name']} создана.")
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


def _render_ai(engine: SimulationEngine) -> None:
    """Вкладка ИИ: генерация мира по описанию и глава летописи."""
    st.subheader("Мир по описанию")
    st.caption(
        "ИИ опционален: без ключей провайдера доступны ручная конфигурация и fallback-глава."
    )
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

    if st.button("Создать мир по описанию", type="primary"):
        client, error = safe_client()
        if client is None:
            st.warning(f"ИИ недоступен: {error}. Использую ручную конфигурацию.")
            st.session_state["engine"] = build_engine(create_world(fallback))
            st.rerun()
        else:
            with st.spinner("ИИ проектирует мир…"):
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
            with st.spinner("Хронист пишет главу…"):
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


if __name__ == "__main__":
    main()
