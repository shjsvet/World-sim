"""Тесты оркестратора ИИ-правителей."""

from __future__ import annotations

import json
from collections.abc import Sequence

from worldsim.ai.client import Message
from worldsim.ai.orchestrator import AIRulerOrchestrator
from worldsim.ai.ruler import RulerAction, RulerDecision
from worldsim.core.chronicle import Chronicle
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rulers import RulerProfile, StandingOrder
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.ai_ruler import AIRulerRule
from worldsim.engine.rules.orders import StandingOrderRule


class FakeClient:
    """Клиент, всегда возвращающий HOLD."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Считает вызовы и отдаёт валидный JSON."""
        self.calls += 1
        return json.dumps(
            {
                "action": "hold",
                "target_tile_id": None,
                "amount": 0,
                "message": "",
                "thought": "Жду удобного момента.",
                "confidence": 0.5,
            },
            ensure_ascii=False,
        )


def make_faction(
    faction_id: int,
    *,
    capital: int,
    morale: float = 0.8,
    treasury: float = 100.0,
) -> Faction:
    """Создаёт фракцию для оркестратора."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        morale=morale,
        treasury=treasury,
        food_stockpile=100.0,
    )


def make_state(
    *,
    factions: tuple[Faction, ...],
    rulers: tuple[RulerProfile, ...],
    orders: tuple[StandingOrder, ...] = (),
) -> WorldState:
    """Создаёт мир с фракциями и правителями."""
    capitals = {faction.capital_tile_id: faction.id for faction in factions}
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
        if index in capitals:
            data["owner_id"] = capitals[index]
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        rulers=rulers,
        standing_orders=orders,
    )


def make_engine(state: WorldState) -> SimulationEngine:
    """Создаёт движок с правилом ИИ."""
    return SimulationEngine([AIRulerRule()], Chronicle(), initial_state=state)


def test_run_year_records_thoughts() -> None:
    """Оркестратор сохраняет мысли каждой фракции."""
    first = make_faction(0, capital=0)
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        rulers=(
            RulerProfile(faction_id=0, name="Король"),
            RulerProfile(faction_id=1, name="Вождь"),
        ),
    )
    engine = make_engine(state)
    client = FakeClient()

    result = AIRulerOrchestrator(client).run_year(engine)

    assert result.year == 1
    assert len(result.thoughts) == 2
    assert {thought.faction_id for thought in result.thoughts} == {0, 1}
    assert all(thought.action == RulerAction.HOLD.value for thought in result.thoughts)
    assert all(thought.text for thought in result.thoughts)
    assert client.calls == 2
    assert engine.pending_ai_decisions == ()


def test_without_client_uses_fallback() -> None:
    """Без клиента работает детерминированный fallback."""
    faction = make_faction(0, capital=0, morale=0.2)
    state = make_state(
        factions=(faction,),
        rulers=(RulerProfile(faction_id=0, name="Король"),),
    )
    engine = make_engine(state)

    result = AIRulerOrchestrator().run_year(engine)

    assert result.year == 1
    assert len(result.thoughts) == 1
    assert result.thoughts[0].action == RulerAction.PROPOSE_PEACE.value


def test_decision_interval_skips_years() -> None:
    """Фракция с интервалом 2 думает не каждый год."""
    first = make_faction(0, capital=0)
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        rulers=(
            RulerProfile(faction_id=0, name="Король", decision_interval=1),
            RulerProfile(faction_id=1, name="Вождь", decision_interval=2),
        ),
    )
    engine = make_engine(state)
    orchestrator = AIRulerOrchestrator(FakeClient())

    orchestrator.run_year(engine)
    assert {thought.faction_id for thought in engine.state.thoughts} == {0, 1}
    orchestrator.run_year(engine)
    assert [thought.faction_id for thought in engine.state.thoughts].count(1) == 1
    orchestrator.run_year(engine)
    assert [thought.faction_id for thought in engine.state.thoughts].count(1) == 2


def test_queue_decision_is_applied_and_cleared() -> None:
    """Очередь движка применяет решение и очищается после шага."""
    faction = make_faction(0, capital=0, treasury=100.0)
    state = make_state(
        factions=(faction,),
        rulers=(RulerProfile(faction_id=0, name="Король"),),
    )
    engine = make_engine(state)
    engine.queue_decision(
        0,
        RulerDecision(
            action=RulerAction.RECRUIT,
            amount=5,
            thought="Наберу солдат.",
            confidence=0.5,
        ),
    )

    result = engine.step()

    assert engine.pending_ai_decisions == ()
    assert result.factions[0].treasury == 90.0
    assert result.factions[0].army_size == 5.0


def test_thought_ids_are_unique_between_years() -> None:
    """Мысли разных лет получают уникальные id."""
    faction = make_faction(0, capital=0)
    state = make_state(
        factions=(faction,),
        rulers=(RulerProfile(faction_id=0, name="Король"),),
    )
    engine = make_engine(state)
    orchestrator = AIRulerOrchestrator(FakeClient())

    orchestrator.run_year(engine)
    orchestrator.run_year(engine)

    ids = [thought.id for thought in engine.state.thoughts]
    assert ids == [0, 1]


def test_no_rulers_still_advances_year() -> None:
    """Без профилей правителей год всё равно наступает."""
    faction = make_faction(0, capital=0)
    state = make_state(factions=(faction,), rulers=())
    engine = make_engine(state)

    result = AIRulerOrchestrator().run_year(engine)

    assert result.year == 1
    assert result.thoughts == ()


def test_order_executes_on_skipped_year() -> None:
    """Приказ работает и в год, когда ИИ не принимает решение."""
    faction = make_faction(0, capital=0, treasury=100.0)
    order = StandingOrder(
        id=0,
        faction_id=0,
        kind="accumulate_gold",
        payload={"amount": 10},
        years_left=3,
        created_year=0,
    )
    state = make_state(
        factions=(faction,),
        rulers=(RulerProfile(faction_id=0, name="Король", decision_interval=2),),
        orders=(order,),
    )
    engine = SimulationEngine(
        [StandingOrderRule(), AIRulerRule()],
        Chronicle(),
        initial_state=state,
    )
    orchestrator = AIRulerOrchestrator(FakeClient())

    orchestrator.run_year(engine)
    orchestrator.run_year(engine)

    assert engine.state.factions[0].treasury == 120.0
    assert engine.state.standing_orders[0].years_left == 1
    assert len(engine.state.thoughts) == 1


def test_same_input_gives_same_state() -> None:
    """Одинаковые входные данные дают одинаковый снимок."""
    first = make_faction(0, capital=0)
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        rulers=(
            RulerProfile(faction_id=0, name="Король"),
            RulerProfile(faction_id=1, name="Вождь"),
        ),
    )
    left = make_engine(state)
    right = make_engine(state)

    AIRulerOrchestrator(FakeClient()).run_year(left)
    AIRulerOrchestrator(FakeClient()).run_year(right)

    assert left.state == right.state
