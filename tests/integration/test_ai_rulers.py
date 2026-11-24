"""Интеграционный сценарий этапа 6: ИИ-правители."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from worldsim.ai.client import Message
from worldsim.ai.orchestrator import AIRulerOrchestrator
from worldsim.core.chronicle import Chronicle
from worldsim.core.culture import Culture
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rulers import RulerProfile
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.ai_ruler import AIRulerRule
from worldsim.engine.rules.march import MarchRule
from worldsim.engine.rules.orders import StandingOrderRule
from worldsim.engine.rules.religion import ReligionFoundingRule
from worldsim.engine.rules.trade_offers import TradeOfferRule

pytestmark = pytest.mark.integration


class FakeClient:
    """Клиент, который всегда выбирает HOLD."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Считает годовые решения."""
        self.calls += 1
        return json.dumps(
            {
                "action": "hold",
                "target_tile_id": None,
                "amount": 0,
                "message": "",
                "thought": "Год спокойный, сохраняю курс.",
                "confidence": 0.5,
            },
            ensure_ascii=False,
        )


def make_faction(
    faction_id: int,
    *,
    capital: int,
    food: float,
    treasury: float,
) -> Faction:
    """Создаёт фракцию с культурой людей."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        food_stockpile=food,
        treasury=treasury,
        army_size=20.0,
        morale=0.8,
    )


def make_state() -> WorldState:
    """Создаёт маленький мир с двумя соседними фракциями."""
    factions = (
        make_faction(0, capital=0, food=100.0, treasury=0.0),
        make_faction(1, capital=1, food=0.0, treasury=100.0),
    )
    rulers = (
        RulerProfile(faction_id=0, name="Король"),
        RulerProfile(faction_id=1, name="Вождь"),
    )
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
            data["army_presence"] = 10
        elif index == 1:
            data["owner_id"] = 1
            data["army_presence"] = 10
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=7, size=4, initial_factions=2),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        cultures=(Culture(id=0, name="Люди"),),
        rulers=rulers,
    )


def make_engine(state: WorldState) -> SimulationEngine:
    """Создаёт движок со всеми правилами этапа 6."""
    return SimulationEngine(
        [
            AIRulerRule(),
            TradeOfferRule(),
            StandingOrderRule(),
            MarchRule(),
            ReligionFoundingRule(),
        ],
        Chronicle(),
        initial_state=state,
    )


def test_thirty_years_with_client() -> None:
    """30 лет с LLM: мысли и переписка сохраняются."""
    state = make_state()
    engine = make_engine(state)
    orchestrator = AIRulerOrchestrator(FakeClient())
    orchestrator.open_channel(engine, 0, 1, "peace")

    for _ in range(30):
        orchestrator.run_year(engine)

    result = engine.state
    assert result.year == 30
    assert len(result.thoughts) == 60
    assert len(result.diplomatic_messages) == 1
    assert all(thought.text for thought in result.thoughts)
    assert all(faction.treasury >= 0 and faction.food_stockpile >= 0 for faction in result.factions)


def test_thirty_years_without_client() -> None:
    """Fallback торгует, отдаёт приказы и не ломает инварианты."""
    state = make_state()
    engine = make_engine(state)
    orchestrator = AIRulerOrchestrator()

    for _ in range(30):
        orchestrator.run_year(engine)

    result = engine.state
    assert result.year == 30
    assert len(result.thoughts) == 60
    assert all(faction.treasury >= 0 and faction.food_stockpile >= 0 for faction in result.factions)
    assert all(tile.army_presence >= 0 for tile in result.map.tiles)
    assert len({thought.id for thought in result.thoughts}) == len(result.thoughts)
    assert WorldState.from_json(result.to_json()) == result


def test_ai_scenario_is_deterministic() -> None:
    """Одинаковый сценарий даёт одинаковый снимок."""
    left = make_engine(make_state())
    right = make_engine(make_state())
    for _ in range(20):
        AIRulerOrchestrator(FakeClient()).run_year(left)
        AIRulerOrchestrator(FakeClient()).run_year(right)

    assert left.state == right.state


def test_fallback_scenario_is_deterministic() -> None:
    """Fallback-сценарий тоже детерминирован."""
    left = make_engine(make_state())
    right = make_engine(make_state())
    for _ in range(20):
        AIRulerOrchestrator().run_year(left)
        AIRulerOrchestrator().run_year(right)

    assert left.state == right.state
