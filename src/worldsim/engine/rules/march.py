"""Марши армий: прибытие через несколько лет и отмена."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext, TileUpdate


class MarchRule:
    """Доставляет идущие армии и очищает завершённые марши."""

    name = "march"
    priority = 9

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Ждёт прибытия, добавляет гарнизон и возвращает армию."""
        factions = {faction.id: faction for faction in state.factions}
        working = dict(factions)
        remaining = []
        tile_updates: list[TileUpdate] = []
        events: list[Event] = []

        for march in sorted(state.army_marches, key=lambda item: item.id):
            faction = working.get(march.faction_id)
            if faction is None:
                continue
            if ctx.year < march.arrival_year:
                remaining.append(march)
                continue

            target = state.map.by_id(march.to_tile)
            working[faction.id] = faction.evolve(army_size=faction.army_size + march.amount)
            if target.owner_id is None or not target.is_land:
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.CUSTOM,
                        summary=(f"Марш фракции {faction.id} отменён: тайл {target.id} потерян"),
                        tile_ids=(target.id,),
                        faction_ids=(faction.id,),
                        severity=0.4,
                    )
                )
                continue

            tile_updates.append(
                TileUpdate(
                    tile_id=target.id,
                    army_presence=target.army_presence + march.amount,
                )
            )
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.MIGRATION,
                    summary=(
                        f"Армия фракции {faction.id} прибыла в тайл {target.id}: "
                        f"{march.amount} солдат"
                    ),
                    tile_ids=(march.from_tile, target.id),
                    faction_ids=(faction.id,),
                    severity=0.5,
                )
            )

        return RuleOutcome(
            tile_updates=tuple(tile_updates),
            faction_updates=tuple(
                FactionUpdate(
                    faction_id=faction_id,
                    changes={"army_size": current.army_size},
                )
                for faction_id, current in working.items()
                if current.army_size != factions[faction_id].army_size
            ),
            events=tuple(events),
            army_marches=tuple(remaining),
        )
