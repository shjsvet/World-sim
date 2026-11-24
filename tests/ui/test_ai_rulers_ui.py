"""Тесты UI-хелперов ИИ-правителей."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.ai_ruler import AIRulerRule
from worldsim.ui.ai_rulers import ensure_rulers, open_diplomacy, run_ai_year


def make_faction(faction_id: int, *, capital: int) -> Faction:
    """Создаёт фракцию для UI-тестов."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        food_stockpile=100.0,
        treasury=100.0,
    )


def make_state() -> WorldState:
    """Создаёт мир с двумя фракциями."""
    factions = (make_faction(0, capital=0), make_faction(1, capital=1))
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
        elif index == 1:
            data["owner_id"] = 1
        tiles.append(RegionData.model_validate(data))
    state = WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=2),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
    )
    return state


def make_engine(state: WorldState) -> SimulationEngine:
    """Создаёт движок с правилом ИИ."""
    return SimulationEngine([AIRulerRule()], Chronicle(), initial_state=state)


def test_ensure_rulers_adds_profiles() -> None:
    """Профили создаются для всех фракций."""
    state = ensure_rulers(make_state())

    assert len(state.rulers) == 2
    assert {profile.faction_id for profile in state.rulers} == {0, 1}


def test_ensure_rulers_is_idempotent() -> None:
    """Повторный вызов не дублирует профили."""
    first = ensure_rulers(make_state())
    second = ensure_rulers(first)

    assert second == first


def test_run_ai_year_fallback() -> None:
    """ИИ-год без клиента сохраняет мысли."""
    engine = make_engine(ensure_rulers(make_state()))

    result = run_ai_year(engine)

    assert result.year == 1
    assert len(result.thoughts) == 2


def test_open_diplomacy_records_message() -> None:
    """Канал переписки сохраняет сообщение."""
    engine = make_engine(ensure_rulers(make_state()))

    messages = open_diplomacy(engine, 0, 1, "peace")

    assert len(messages) == 1
    assert engine.state.diplomatic_messages == messages
