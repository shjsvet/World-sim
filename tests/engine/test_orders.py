"""Тесты долгосрочных приказов ИИ-правителей."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction, RulerDecision
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.rulers import StandingOrder
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules import AICommand, StepContext
from worldsim.engine.rules.ai_ruler import AIRulerRule
from worldsim.engine.rules.orders import StandingOrderRule


def make_faction(*, treasury: float = 100.0, army: float = 10.0) -> Faction:
    """Создаёт фракцию с приказом."""
    return Faction(
        id=0,
        name="Альянс",
        color="#112233",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=0,
        treasury=treasury,
        army_size=army,
    )


def make_state(
    *,
    faction: Faction | None = None,
    orders: tuple[StandingOrder, ...] = (),
) -> WorldState:
    """Создаёт мир с одним владельцем."""
    if faction is None:
        faction = make_faction()
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
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=1),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=(faction,),
        standing_orders=orders,
    )


def make_order(
    order_id: int = 0,
    *,
    kind: str = "accumulate_gold",
    years: int = 3,
    amount: int = 10,
    target: int | None = None,
) -> StandingOrder:
    """Создаёт приказ."""
    return StandingOrder(
        id=order_id,
        faction_id=0,
        kind=kind,
        target_tile_id=target,
        payload={"amount": amount},
        years_left=years,
        created_year=0,
    )


def run_orders(state: WorldState) -> object:
    """Выполняет правило приказов."""
    context = StepContext(year=0, config=state.config, rng=Rng(1))
    return StandingOrderRule().apply(state, context)


def test_accumulate_gold() -> None:
    """Приказ копит золото и уменьшает срок."""
    state = make_state(orders=(make_order(),))

    outcome = run_orders(state)

    changes = outcome.faction_updates[0].changes  # type: ignore[attr-defined]
    assert changes["treasury"] == 110.0
    assert outcome.standing_orders[0].years_left == 2  # type: ignore[attr-defined]
    assert any(
        event.type is EventType.CUSTOM
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_recruit_order() -> None:
    """Приказ набирает армию за золото."""
    state = make_state(orders=(make_order(kind="recruit", amount=5),))

    outcome = run_orders(state)

    changes = outcome.faction_updates[0].changes  # type: ignore[attr-defined]
    assert changes["treasury"] == 90.0
    assert changes["army_size"] == 15.0
    assert any(
        event.type is EventType.RECRUITMENT
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_defend_order_fortifies_tile() -> None:
    """Приказ защиты укрепляет тайл."""
    state = make_state(orders=(make_order(kind="defend", target=0),))

    outcome = run_orders(state)

    updates = outcome.tile_updates  # type: ignore[attr-defined]
    assert updates[0].tile_id == 0
    assert updates[0].fortification == 2.0
    assert outcome.standing_orders[0].years_left == 2  # type: ignore[attr-defined]


def test_expired_order_is_removed() -> None:
    """Приказ с последним годом исчезает."""
    state = make_state(orders=(make_order(years=1),))

    outcome = run_orders(state)

    assert outcome.standing_orders == ()  # type: ignore[attr-defined]


def test_unknown_order_is_removed() -> None:
    """Неизвестный приказ не исполняется и снимается."""
    state = make_state(orders=(make_order(kind="unknown"),))

    outcome = run_orders(state)

    assert outcome.standing_orders == ()  # type: ignore[attr-defined]
    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_ai_issues_order() -> None:
    """ISSUE_ORDER создаёт приказ в снимке."""
    state = make_state()
    decision = RulerDecision(
        action=RulerAction.ISSUE_ORDER,
        order_kind="accumulate_gold",
        order_years=4,
        amount=7,
        thought="Копим золото.",
        confidence=0.5,
    )
    context = StepContext(
        year=0,
        config=state.config,
        rng=Rng(1),
        ai_decisions=[AICommand(0, decision)],
    )

    outcome = AIRulerRule().apply(state, context)

    assert outcome.standing_orders is not None
    order = outcome.standing_orders[0]
    assert order.kind == "accumulate_gold"
    assert order.years_left == 4
    assert order.payload["amount"] == 7


def test_invalid_order_kind_is_ignored() -> None:
    """Неизвестный вид приказа не создаётся."""
    state = make_state()
    decision = RulerDecision(
        action=RulerAction.ISSUE_ORDER,
        order_kind="fly",
        order_years=4,
        thought="Летаем.",
        confidence=0.5,
    )
    context = StepContext(
        year=0,
        config=state.config,
        rng=Rng(1),
        ai_decisions=[AICommand(0, decision)],
    )

    outcome = AIRulerRule().apply(state, context)

    assert outcome.standing_orders == ()


def test_orders_are_deterministic() -> None:
    """Одинаковые приказы дают одинаковый результат."""
    state = make_state(orders=(make_order(),))

    first = run_orders(state)
    second = run_orders(state)

    assert first == second
