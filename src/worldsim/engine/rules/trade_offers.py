"""ИИ-торговля едой и ресурсами: предложения и обмен."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction
from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.state import WorldState
from worldsim.engine.rules import (
    AICommand,
    FactionUpdate,
    RuleOutcome,
    StepContext,
)

FAMINE_THRESHOLD = 20.0
RESOURCE_NEED = 5.0
PRICE_PER_UNIT = 2.0
DEFAULT_AMOUNT = 10


class TradeOfferRule:
    """Исполняет ``OFFER_TRADE``: еда или ресурс в обмен на золото."""

    name = "trade_offers"
    priority = 6

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Проводит сделки без отрицательных значений."""
        original = {faction.id: faction for faction in state.factions}
        working = dict(original)
        events: list[Event] = []
        for command in ctx.ai_decisions:
            if command.decision.action is not RulerAction.OFFER_TRADE:
                continue
            self._trade(state, command, working, events)
        return RuleOutcome(
            faction_updates=_faction_updates(original, working),
            events=tuple(events),
        )

    def _trade(
        self,
        state: WorldState,
        command: AICommand,
        working: dict[int, Faction],
        events: list[Event],
    ) -> None:
        """Проводит одну сделку, если она выгодна и возможна."""
        sender = working.get(command.faction_id)
        target_id = command.decision.target_tile_id
        if sender is None or target_id is None or target_id >= len(state.map.tiles):
            return
        target = state.map.by_id(target_id)
        if target.owner_id is None or target.owner_id == sender.id:
            return
        recipient = working.get(target.owner_id)
        if recipient is None:
            return
        if not _is_border_tile(state, sender.id, target_id):
            return
        if _has_conflict(state, sender.id, recipient.id):
            return

        resource = (command.decision.trade_resource or "food").strip().lower()
        amount = command.decision.amount or DEFAULT_AMOUNT
        available, needed = _available_and_need(sender, recipient, resource)
        if available <= 0 or not needed:
            return
        affordable = int(recipient.treasury // PRICE_PER_UNIT)
        transfer = min(amount, available, affordable)
        if transfer <= 0:
            return

        if resource == "food":
            working[sender.id] = sender.evolve(
                food_stockpile=sender.food_stockpile - transfer,
                treasury=sender.treasury + transfer * PRICE_PER_UNIT,
            )
            working[recipient.id] = recipient.evolve(
                food_stockpile=recipient.food_stockpile + transfer,
                treasury=recipient.treasury - transfer * PRICE_PER_UNIT,
            )
        else:
            sender_resources = dict(sender.resources)
            sender_resources[resource] = sender_resources.get(resource, 0.0) - transfer
            recipient_resources = dict(recipient.resources)
            recipient_resources[resource] = recipient_resources.get(resource, 0.0) + transfer
            working[sender.id] = sender.evolve(
                resources=sender_resources,
                treasury=sender.treasury + transfer * PRICE_PER_UNIT,
            )
            working[recipient.id] = recipient.evolve(
                resources=recipient_resources,
                treasury=recipient.treasury - transfer * PRICE_PER_UNIT,
            )

        from worldsim.core.events import Event

        events.append(
            Event(
                id=0,
                year=state.year,
                type=EventType.TRADE,
                summary=(
                    f"Сделка: фракция {sender.id} передала {transfer} {resource} "
                    f"фракции {recipient.id} за {int(transfer * PRICE_PER_UNIT)} золота"
                ),
                faction_ids=(sender.id, recipient.id),
                severity=0.4,
            )
        )


def _available_and_need(
    sender: Faction,
    recipient: Faction,
    resource: str,
) -> tuple[int, bool]:
    """Сколько можно отдать и нужен ли ресурс получателю."""
    if resource == "food":
        available = max(0, int(sender.food_stockpile - FAMINE_THRESHOLD))
        needed = recipient.food_stockpile < FAMINE_THRESHOLD
        return available, needed
    available = max(0, int(sender.resources.get(resource, 0.0)))
    needed = recipient.resources.get(resource, 0.0) < RESOURCE_NEED
    return available, needed


def _is_border_tile(state: WorldState, faction_id: int, target_id: int) -> bool:
    """Проверяет, что цель граничит с владением фракции."""
    for tile in state.map.tiles:
        if tile.owner_id != faction_id:
            continue
        if any(neighbor.id == target_id for neighbor in state.map.neighbors(tile.x, tile.y)):
            return True
    return False


def _has_conflict(state: WorldState, first_id: int, second_id: int) -> bool:
    """Проверяет войну или перемирие."""
    for war in state.wars:
        if {war.attacker_id, war.defender_id} != {first_id, second_id}:
            continue
        if war.active:
            return True
        if war.truce_until_year is not None and war.truce_until_year >= state.year:
            return True
    return False


def _faction_updates(
    before: dict[int, Faction],
    after: dict[int, Faction],
) -> tuple[FactionUpdate, ...]:
    """Собирает изменения фракций после сделки."""
    fields = ("treasury", "food_stockpile", "resources")
    updates: list[FactionUpdate] = []
    for faction_id, original in before.items():
        current = after[faction_id]
        changes = {
            name: getattr(current, name)
            for name in fields
            if getattr(current, name) != getattr(original, name)
        }
        if changes:
            updates.append(FactionUpdate(faction_id=faction_id, changes=changes))
    return tuple(updates)
