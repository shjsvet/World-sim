"""Тесты ИИ-торговли едой и ресурсами."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction, RulerDecision, fallback_decision
from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules import AICommand, StepContext
from worldsim.engine.rules.trade_offers import TradeOfferRule


def make_faction(
    faction_id: int,
    *,
    food: float,
    treasury: float,
    resources: dict[str, float] | None = None,
) -> Faction:
    """Создаёт фракцию для сделки."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=faction_id,
        food_stockpile=food,
        treasury=treasury,
        resources=resources or {},
    )


def make_state(
    *,
    sender_food: float = 100.0,
    recipient_food: float = 0.0,
    recipient_gold: float = 100.0,
    war: War | None = None,
    resource_target: int = 1,
) -> WorldState:
    """Создаёт мир с двумя фракциями и границей."""
    factions = (
        make_faction(0, food=sender_food, treasury=0.0, resources={"wood": 20.0}),
        make_faction(
            1,
            food=recipient_food,
            treasury=recipient_gold,
        ),
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
        elif index == 1 or index == resource_target:
            data["owner_id"] = 1
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=2),
        year=3,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        wars=(war,) if war is not None else (),
    )


def make_decision(
    *,
    amount: int = 10,
    resource: str = "food",
    target: int = 1,
) -> RulerDecision:
    """Создаёт решение о сделке."""
    return RulerDecision(
        action=RulerAction.OFFER_TRADE,
        target_tile_id=target,
        amount=amount,
        trade_resource=resource,
        thought="Предлагаю обмен.",
        confidence=0.5,
    )


def run_trade(state: WorldState, decision: RulerDecision) -> object:
    """Выполняет правило сделки."""
    context = StepContext(
        year=3,
        config=state.config,
        rng=Rng(1),
        ai_decisions=[AICommand(0, decision)],
    )
    return TradeOfferRule().apply(state, context)


def test_food_trade() -> None:
    """Голодающий сосед покупает еду за золото."""
    state = make_state()

    outcome = run_trade(state, make_decision())

    changes = {update.faction_id: update.changes for update in outcome.faction_updates}  # type: ignore[attr-defined]
    assert changes[0]["food_stockpile"] == 90.0
    assert changes[0]["treasury"] == 20.0
    assert changes[1]["food_stockpile"] == 10.0
    assert changes[1]["treasury"] == 80.0
    assert any(event.type is EventType.TRADE for event in outcome.events)  # type: ignore[attr-defined]


def test_no_trade_without_hunger() -> None:
    """Сытая фракция не покупает еду."""
    state = make_state(recipient_food=100.0)

    outcome = run_trade(state, make_decision())

    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_no_trade_at_war() -> None:
    """Во время войны сделка не проводится."""
    war = War(id=0, attacker_id=0, defender_id=1, started_year=1, active=True)
    state = make_state(war=war)

    outcome = run_trade(state, make_decision())

    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_partial_trade_with_limited_gold() -> None:
    """Нехватка золота уменьшает объём, но не уводит в минус."""
    state = make_state(recipient_gold=5.0)

    outcome = run_trade(state, make_decision())

    changes = {update.faction_id: update.changes for update in outcome.faction_updates}  # type: ignore[attr-defined]
    assert changes[1]["treasury"] == 1.0
    assert changes[1]["food_stockpile"] == 2.0
    assert changes[0]["food_stockpile"] == 98.0


def test_resource_trade() -> None:
    """Ресурсный обмен переносит ресурс и золото."""
    state = make_state()

    outcome = run_trade(state, make_decision(resource="wood"))

    changes = {update.faction_id: update.changes for update in outcome.faction_updates}  # type: ignore[attr-defined]
    assert changes[0]["resources"]["wood"] == 10.0
    assert changes[0]["treasury"] == 20.0
    assert changes[1]["resources"]["wood"] == 10.0


def test_no_resource_to_give() -> None:
    """Нельзя продать ресурс, которого нет."""
    state = make_state()

    outcome = run_trade(state, make_decision(resource="gold"))

    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_non_border_target_is_rejected() -> None:
    """Сделка возможна только через границу."""
    state = make_state(resource_target=15)

    outcome = run_trade(state, make_decision(target=15))

    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_fallback_offers_food_to_hungry_neighbour() -> None:
    """Без ИИ fallback замечает голодного соседа."""
    state = make_state()

    decision = fallback_decision(state, state.factions[0])

    assert decision.action is RulerAction.OFFER_TRADE
    assert decision.target_tile_id == 1
    assert decision.trade_resource == "food"


def test_trade_is_deterministic() -> None:
    """Сделка детерминирована."""
    state = make_state()

    first = run_trade(state, make_decision())
    second = run_trade(state, make_decision())

    assert first == second
