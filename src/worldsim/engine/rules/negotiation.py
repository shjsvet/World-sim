"""Применение итогов переписки: мир, отказ и торговые маршруты."""

from __future__ import annotations

from worldsim.core.diplomacy import War
from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.geography import ResourceType
from worldsim.core.resources import TradeRoute
from worldsim.core.rulers import DiplomaticMessage, MessageKind
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome

TRUCE_YEARS = 10
PEACE_MORALE_BONUS = 0.1
PEACE_AGGRESSION_DROP = 0.1
PEACE_OPPONENT_MORALE = 0.5
FORCE_RATIO = 0.75


def resolve_message(
    state: WorldState,
    message: DiplomaticMessage,
    responder: Faction,
) -> RuleOutcome:
    """Разрешает предложение и возвращает изменения мира.

    Мир закрывает активную войну и ставит перемирие, торговля создаёт
    маршрут между соседними тайлами. Отказ меняет только флаг ``accepted``
    у сообщения и не трогает войны и маршруты.

    Raises:
        ValueError: Если ответчик не является получателем или фракции нет.
    """
    factions = {faction.id: faction for faction in state.factions}
    if responder.id != message.recipient_id:
        raise ValueError("ответчик не является получателем сообщения")
    if message.sender_id not in factions or responder.id not in factions:
        raise ValueError("фракция отсутствует в снимке")
    sender = factions[message.sender_id]

    if message.kind is MessageKind.PEACE:
        war = _active_war(state, sender.id, responder.id)
        if war is None:
            return _refusal(state, message)
        if not _accepts_peace(war, sender, responder):
            return _refusal(state, message)
        wars = tuple(
            item.model_copy(
                update={
                    "active": False,
                    "truce_until_year": state.year + TRUCE_YEARS,
                }
            )
            if item.id == war.id
            else item
            for item in state.wars
        )
        updates = tuple(
            FactionUpdate(
                faction_id=faction.id,
                changes={
                    "morale": min(1.0, faction.morale + PEACE_MORALE_BONUS),
                    "aggressiveness": max(0.0, faction.aggressiveness - PEACE_AGGRESSION_DROP),
                },
            )
            for faction in (sender, responder)
        )
        event = Event(
            id=0,
            year=state.year,
            type=EventType.PEACE_TREATY,
            summary=f"Мир между фракциями {sender.id} и {responder.id}",
            faction_ids=(sender.id, responder.id),
            severity=1.0,
        )
        return RuleOutcome(
            faction_updates=updates,
            events=(event,),
            wars=wars,
            diplomatic_messages=_with_accepted(state, message, True),
        )

    if message.kind is MessageKind.TRADE:
        if _active_war(state, sender.id, responder.id) is not None:
            return _refusal(state, message)
        route = _find_trade_route(state, sender.id, responder.id)
        if route is None:
            return _refusal(state, message)
        event = Event(
            id=0,
            year=state.year,
            type=EventType.TRADE,
            summary=(
                f"Торговый маршрут {route.from_tile} → {route.to_tile} ({route.resource.value})"
            ),
            tile_ids=(route.from_tile, route.to_tile),
            faction_ids=(sender.id, responder.id),
            severity=0.5,
        )
        return RuleOutcome(
            events=(event,),
            trade_routes=(*state.trade_routes, route),
            diplomatic_messages=_with_accepted(state, message, True),
        )

    if message.kind is MessageKind.OFFER:
        accepted = responder.morale >= 0.4
        return RuleOutcome(
            diplomatic_messages=_with_accepted(state, message, accepted),
        )

    return _refusal(state, message)


def _active_war(state: WorldState, first_id: int, second_id: int) -> War | None:
    """Возвращает активную войну между фракциями или ``None``."""
    for war in state.wars:
        if {war.attacker_id, war.defender_id} == {first_id, second_id} and war.active:
            return war
    return None


def _accepts_peace(war: War, sender: Faction, responder: Faction) -> bool:
    """Решает, принимает ли ответчик мир (детерминированно)."""
    responder_losses = (
        war.attacker_losses if war.attacker_id == responder.id else war.defender_losses
    )
    sender_losses = war.attacker_losses if war.attacker_id == sender.id else war.defender_losses
    if responder.morale < PEACE_OPPONENT_MORALE:
        return True
    if responder_losses > sender_losses:
        return True
    return responder.army_size < sender.army_size * FORCE_RATIO


def _find_trade_route(
    state: WorldState,
    sender_id: int,
    recipient_id: int,
) -> TradeRoute | None:
    """Ищет соседнюю пару тайлов с ресурсом для маршрута."""
    existing = {(route.from_tile, route.to_tile, route.resource) for route in state.trade_routes}
    candidates: list[tuple[int, int, ResourceType, float]] = []
    for tile in state.map.tiles:
        if tile.owner_id != sender_id:
            continue
        for neighbor in state.map.neighbors(tile.x, tile.y):
            if neighbor.owner_id != recipient_id:
                continue
            for source, target in ((tile, neighbor), (neighbor, tile)):
                if source.resource_type is ResourceType.NONE:
                    continue
                if (source.id, target.id, source.resource_type) in existing:
                    continue
                capacity = max(1.0, min(5.0, source.resource_amount / 10.0))
                candidates.append((source.id, target.id, source.resource_type, capacity))
    if not candidates:
        return None
    from_tile, to_tile, resource, capacity = sorted(
        candidates,
        key=lambda item: (item[0], item[1], item[2].value),
    )[0]
    return TradeRoute(
        from_tile=from_tile,
        to_tile=to_tile,
        resource=resource,
        capacity=capacity,
    )


def _with_accepted(
    state: WorldState,
    message: DiplomaticMessage,
    accepted: bool,
) -> tuple[DiplomaticMessage, ...]:
    """Возвращает переписку с обновлённым флагом сообщения."""
    updated = message.model_copy(update={"accepted": accepted})
    found = False
    messages: list[DiplomaticMessage] = []
    for item in state.diplomatic_messages:
        if item.id == message.id:
            messages.append(updated)
            found = True
        else:
            messages.append(item)
    if not found:
        messages.append(updated)
    return tuple(messages)


def _refusal(state: WorldState, message: DiplomaticMessage) -> RuleOutcome:
    """Отказ без изменения войн и маршрутов."""
    return RuleOutcome(
        diplomatic_messages=_with_accepted(state, message, False),
    )
