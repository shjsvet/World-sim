"""Тесты применения итогов переписки."""

from __future__ import annotations

import pytest

from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.resources import TradeRoute
from worldsim.core.rulers import DiplomaticMessage, MessageKind
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules.negotiation import resolve_message


def make_faction(
    faction_id: int,
    *,
    morale: float = 0.8,
    army: float = 20.0,
) -> Faction:
    """Создаёт фракцию для переговоров."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=faction_id,
        morale=morale,
        army_size=army,
    )


def make_state(
    *,
    war: War | None = None,
    message: DiplomaticMessage | None = None,
    routes: tuple[TradeRoute, ...] = (),
    food_tile: bool = True,
) -> WorldState:
    """Создаёт мир с двумя фракциями и границей."""
    factions = (make_faction(0), make_faction(1))
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
            if food_tile:
                data["resource_type"] = ResourceType.FOOD
                data["resource_amount"] = 100.0
                data["resource_depletion"] = 100.0
        elif index == 1:
            data["owner_id"] = 1
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=2),
        year=5,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        wars=(war,) if war is not None else (),
        trade_routes=routes,
        diplomatic_messages=(message,) if message is not None else (),
    )


def make_message(
    kind: MessageKind = MessageKind.PEACE,
    *,
    sender: int = 0,
    recipient: int = 1,
) -> DiplomaticMessage:
    """Создаёт сообщение-предложение."""
    return DiplomaticMessage(
        id=0,
        year=5,
        sender_id=sender,
        recipient_id=recipient,
        kind=kind,
        text="Предложение.",
    )


def test_peace_is_accepted_with_low_morale() -> None:
    """Мир принимается при низкой морали ответчика."""
    war = War(
        id=0,
        attacker_id=0,
        defender_id=1,
        started_year=1,
        attacker_losses=10.0,
        defender_losses=20.0,
        active=True,
    )
    message = make_message()
    state = make_state(war=war, message=message)
    responder = state.factions[1]

    outcome = resolve_message(state, message, responder)

    assert outcome.diplomatic_messages is not None
    assert outcome.diplomatic_messages[0].accepted is True
    assert outcome.wars is not None
    assert outcome.wars[0].active is False
    assert outcome.wars[0].truce_until_year == 15
    assert any(event.type is EventType.PEACE_TREATY for event in outcome.events)
    assert outcome.faction_updates


def test_peace_is_rejected_by_strong_side() -> None:
    """Сильный ответчик отклоняет мир и не меняет войны."""
    war = War(
        id=0,
        attacker_id=0,
        defender_id=1,
        started_year=1,
        attacker_losses=100.0,
        defender_losses=0.0,
        active=True,
    )
    message = make_message()
    state = make_state(war=war, message=message)
    strong = state.factions[1].evolve(morale=0.9, army_size=100.0)
    state = state.model_copy(update={"factions": (state.factions[0], strong)})

    outcome = resolve_message(state, message, strong)

    assert outcome.diplomatic_messages is not None
    assert outcome.diplomatic_messages[0].accepted is False
    assert outcome.wars is None
    assert outcome.trade_routes is None
    assert outcome.events == ()
    assert outcome.faction_updates == ()


def test_trade_creates_route() -> None:
    """Принятая торговля создаёт маршрут между соседями."""
    message = make_message(MessageKind.TRADE)
    state = make_state(message=message)
    responder = state.factions[1]

    outcome = resolve_message(state, message, responder)

    assert outcome.diplomatic_messages is not None
    assert outcome.diplomatic_messages[0].accepted is True
    assert outcome.trade_routes is not None
    assert len(outcome.trade_routes) == 1
    route = outcome.trade_routes[0]
    assert route.resource is ResourceType.FOOD
    assert {route.from_tile, route.to_tile} == {0, 1}
    assert any(event.type is EventType.TRADE for event in outcome.events)


def test_trade_is_rejected_at_war() -> None:
    """Во время войны торговый маршрут не создаётся."""
    war = War(id=0, attacker_id=0, defender_id=1, started_year=1, active=True)
    message = make_message(MessageKind.TRADE)
    state = make_state(war=war, message=message)

    outcome = resolve_message(state, message, state.factions[1])

    assert outcome.diplomatic_messages is not None
    assert outcome.diplomatic_messages[0].accepted is False
    assert outcome.trade_routes is None


def test_trade_without_resource_is_rejected() -> None:
    """Без ресурса на границе торговля отклоняется."""
    message = make_message(MessageKind.TRADE)
    state = make_state(message=message, food_tile=False)

    outcome = resolve_message(state, message, state.factions[1])

    assert outcome.diplomatic_messages is not None
    assert outcome.diplomatic_messages[0].accepted is False
    assert outcome.trade_routes is None


def test_unknown_message_type_is_rejected() -> None:
    """Неподдерживаемый тип не меняет мир."""
    message = make_message(MessageKind.THREAT)
    state = make_state(message=message)

    outcome = resolve_message(state, message, state.factions[1])

    assert outcome.diplomatic_messages is not None
    assert outcome.diplomatic_messages[0].accepted is False
    assert outcome.wars is None
    assert outcome.trade_routes is None


def test_responder_must_be_recipient() -> None:
    """Отвечать может только получатель."""
    message = make_message()
    state = make_state(message=message)

    with pytest.raises(ValueError):
        resolve_message(state, message, state.factions[0])


def test_same_input_gives_same_outcome() -> None:
    """Разрешение детерминировано."""
    war = War(id=0, attacker_id=0, defender_id=1, started_year=1, active=True)
    message = make_message()
    state = make_state(war=war, message=message)

    first = resolve_message(state, message, state.factions[1])
    second = resolve_message(state, message, state.factions[1])

    assert first == second
