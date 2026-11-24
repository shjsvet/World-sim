"""Исполнение долгосрочных приказов ИИ-правителей."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext, TileUpdate

RECRUITMENT_COST = 2.0
DEFAULT_GOLD = 5
DEFAULT_RECRUIT = 5
DEFEND_FORTIFICATION = 2.0


class StandingOrderRule:
    """Каждый год исполняет приказы и уменьшает их срок."""

    name = "standing_orders"
    priority = 3

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Применяет ``accumulate_gold``, ``recruit`` и ``defend``."""
        original = {faction.id: faction for faction in state.factions}
        working = dict(original)
        remaining = []
        tile_updates: list[TileUpdate] = []
        events: list[Event] = []

        for order in sorted(state.standing_orders, key=lambda item: item.id):
            faction = working.get(order.faction_id)
            if faction is None or order.years_left <= 0:
                continue
            if order.kind not in {"accumulate_gold", "recruit", "defend"}:
                continue
            if order.kind == "accumulate_gold":
                amount = _positive_int(order.payload.get("amount"), DEFAULT_GOLD)
                working[faction.id] = faction.evolve(treasury=faction.treasury + amount)
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.CUSTOM,
                        summary=(
                            f"Приказ фракции {faction.id}: казна +{amount} "
                            f"(осталось {order.years_left - 1} лет)"
                        ),
                        faction_ids=(faction.id,),
                        severity=0.2,
                    )
                )
            elif order.kind == "recruit":
                amount = _positive_int(order.payload.get("amount"), DEFAULT_RECRUIT)
                cost = amount * RECRUITMENT_COST
                if faction.treasury >= cost:
                    working[faction.id] = faction.evolve(
                        treasury=faction.treasury - cost,
                        army_size=faction.army_size + amount,
                    )
                    events.append(
                        Event(
                            id=0,
                            year=ctx.year,
                            type=EventType.RECRUITMENT,
                            summary=(f"Приказ фракции {faction.id}: набрано {amount} солдат"),
                            faction_ids=(faction.id,),
                            severity=0.3,
                        )
                    )
            elif order.kind == "defend":
                target = (
                    order.target_tile_id
                    if order.target_tile_id is not None
                    else faction.capital_tile_id
                )
                if target is not None and target < len(state.map.tiles):
                    tile = state.map.by_id(target)
                    if tile.owner_id == faction.id:
                        tile_updates.append(
                            TileUpdate(
                                tile_id=target,
                                fortification=min(100.0, tile.fortification + DEFEND_FORTIFICATION),
                            )
                        )
                        events.append(
                            Event(
                                id=0,
                                year=ctx.year,
                                type=EventType.CUSTOM,
                                summary=(f"Приказ фракции {faction.id}: укреплён тайл {target}"),
                                tile_ids=(target,),
                                faction_ids=(faction.id,),
                                severity=0.2,
                            )
                        )

            if order.years_left > 1:
                remaining.append(order.model_copy(update={"years_left": order.years_left - 1}))

        return RuleOutcome(
            tile_updates=tuple(tile_updates),
            faction_updates=_faction_updates(original, working),
            events=tuple(events),
            standing_orders=tuple(remaining),
        )


def _positive_int(value: object, default: int) -> int:
    """Приводит значение приказа к положительному целому."""
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _faction_updates(
    before: dict[int, Faction],
    after: dict[int, Faction],
) -> tuple[FactionUpdate, ...]:
    """Собирает изменения фракций после приказов."""
    fields = ("treasury", "army_size")
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
