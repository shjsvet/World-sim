"""Тесты изобретения религий."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction, RulerDecision
from worldsim.core.culture import Culture, Religion
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules import AICommand, StepContext
from worldsim.engine.rules.religion import ReligionFoundingRule


def make_faction(faction_id: int, *, capital: int) -> Faction:
    """Создаёт фракцию с культурой людей."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
    )


def make_state(
    *,
    factions: tuple[Faction, ...] | None = None,
    cultures: tuple[Culture, ...] | None = None,
    religions: tuple[Religion, ...] = (),
    neighbour_religion: int | None = None,
) -> WorldState:
    """Создаёт мир с границей двух фракций."""
    if factions is None:
        factions = (make_faction(0, capital=0),)
    if cultures is None:
        cultures = (Culture(id=0, name="Люди"),)
    tiles: list[RegionData] = []
    for index in range(16):
        data: dict[str, object] = {
            "id": index,
            "x": index % 4,
            "y": index // 4,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": 100,
            "population_capacity": 1_000,
        }
        if index == 0:
            data["owner_id"] = 0
        elif index == 1 and len(factions) > 1:
            data["owner_id"] = 1
            if neighbour_religion is not None:
                data["religion_id"] = neighbour_religion
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        cultures=cultures,
        religions=religions,
    )


def make_decision(
    *,
    message: str = "Новая вера",
    confidence: float = 0.9,
) -> RulerDecision:
    """Создаёт решение об основании религии."""
    return RulerDecision(
        action=RulerAction.FOUND_RELIGION,
        message=message,
        thought="Людям нужна новая вера.",
        confidence=confidence,
    )


def run_religion(state: WorldState, decision: RulerDecision) -> object:
    """Выполняет правило религии."""
    context = StepContext(
        year=0,
        config=state.config,
        rng=Rng(1),
        ai_decisions=[AICommand(0, decision)],
    )
    return ReligionFoundingRule().apply(state, context)


def test_found_religion() -> None:
    """Религия создаётся и принимается своей фракцией."""
    state = make_state()

    outcome = run_religion(state, make_decision())

    assert outcome.religions is not None  # type: ignore[attr-defined]
    religion = outcome.religions[0]  # type: ignore[attr-defined]
    assert religion.name == "Новая вера"
    assert religion.culture_id == 0
    assert any(
        update.religion_id == religion.id
        for update in outcome.tile_updates  # type: ignore[attr-defined]
    )
    assert any(
        event.type is EventType.CUSTOM
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_unique_religion_name() -> None:
    """Одинаковое имя получает суффикс."""
    state = make_state(religions=(Religion(id=0, name="Новая вера", culture_id=0, zeal=0.3),))

    outcome = run_religion(state, make_decision())

    assert outcome.religions[-1].name == "Новая вера 2"  # type: ignore[attr-defined]


def test_religion_requires_culture() -> None:
    """Без культуры фракции религия не создаётся."""
    state = make_state(cultures=())

    outcome = run_religion(state, make_decision())

    assert outcome.religions == ()  # type: ignore[attr-defined]
    assert outcome.tile_updates == ()  # type: ignore[attr-defined]


def test_neighbour_adopts_moderate_religion() -> None:
    """Умеренная религия принимается соседним тайлом."""
    factions = (make_faction(0, capital=0), make_faction(1, capital=1))
    state = make_state(factions=factions)

    outcome = run_religion(state, make_decision(confidence=0.6))

    assert any(
        update.tile_id == 1
        for update in outcome.tile_updates  # type: ignore[attr-defined]
    )
    assert outcome.wars is None  # type: ignore[attr-defined]


def test_high_zeal_starts_holy_war() -> None:
    """Высокий zeal начинает священную войну."""
    factions = (make_faction(0, capital=0), make_faction(1, capital=1))
    state = make_state(factions=factions)

    outcome = run_religion(state, make_decision(confidence=0.9))

    assert outcome.wars is not None  # type: ignore[attr-defined]
    assert outcome.wars[0].attacker_id == 0  # type: ignore[attr-defined]
    assert outcome.wars[0].defender_id == 1  # type: ignore[attr-defined]
    assert any(
        event.type is EventType.WAR
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_religion_is_deterministic() -> None:
    """Основание религии детерминировано."""
    state = make_state()

    first = run_religion(state, make_decision())
    second = run_religion(state, make_decision())

    assert first == second
