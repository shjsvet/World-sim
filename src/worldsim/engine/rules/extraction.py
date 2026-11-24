"""Добыча ресурсов на принадлежащих фракциям тайлах."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.geography import ResourceType
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext, TileUpdate


class ExtractionRule:
    """Добывает ресурсы и истощает месторождения.

    Доход зависит от инфраструктуры, реки и статуса города. ``FOOD``
    пополняет запасы еды, ``GOLD`` — казну, остальные ресурсы — склад
    фракции. При нулевом остатке пишется ``RESOURCE_DEPLETED``.
    """

    name = "extraction"
    priority = 6

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Считает добычу по всем месторождениям."""
        factions = {faction.id: faction for faction in state.factions}
        updates: list[TileUpdate] = []
        events: list[Event] = []
        treasury: dict[int, float] = {}
        food: dict[int, float] = {}
        resources: dict[int, dict[str, float]] = {}

        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            if tile.resource_type is ResourceType.NONE:
                continue
            if tile.resource_amount <= 0.0 or tile.resource_depletion <= 0.0:
                continue

            factor = 1.0 + tile.infrastructure / 100.0
            if tile.has_river:
                factor *= 1.25
            if tile.is_city:
                factor *= 1.2
            extracted = min(tile.resource_amount * factor, tile.resource_depletion)
            remaining = max(0.0, tile.resource_depletion - extracted)
            updates.append(TileUpdate(tile_id=tile.id, resource_depletion=remaining))

            if tile.resource_type is ResourceType.FOOD:
                food[tile.owner_id] = food.get(tile.owner_id, 0.0) + extracted
            elif tile.resource_type is ResourceType.GOLD:
                treasury[tile.owner_id] = treasury.get(tile.owner_id, 0.0) + extracted
            else:
                bucket = resources.setdefault(tile.owner_id, {})
                key = tile.resource_type.value
                bucket[key] = bucket.get(key, 0.0) + extracted

            if remaining <= 0.0:
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.RESOURCE_DEPLETED,
                        summary=f"Месторождение тайла {tile.id} истощено",
                        tile_ids=(tile.id,),
                        faction_ids=(tile.owner_id,),
                        severity=1.0,
                    )
                )

        faction_updates: list[FactionUpdate] = []
        for faction_id, faction in factions.items():
            changes: dict[str, object] = {}
            if treasury.get(faction_id):
                changes["treasury"] = faction.treasury + treasury[faction_id]
            if food.get(faction_id):
                changes["food_stockpile"] = faction.food_stockpile + food[faction_id]
            if resources.get(faction_id):
                merged = dict(faction.resources)
                for key, amount in resources[faction_id].items():
                    merged[key] = merged.get(key, 0.0) + amount
                changes["resources"] = merged
            if changes:
                faction_updates.append(FactionUpdate(faction_id=faction_id, changes=changes))

        return RuleOutcome(
            tile_updates=tuple(updates),
            faction_updates=tuple(faction_updates),
            events=tuple(events),
        )
