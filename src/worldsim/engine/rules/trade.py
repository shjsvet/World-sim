"""Торговые маршруты между соседними фракциями."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.geography import ResourceType
from worldsim.core.resources import TradeRoute
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext

RESOURCE_SHARE = 0.1


class TradeRule:
    """Строит маршруты между соседями разных фракций.

    Маршрут работает, только если фракции не воюют и не находятся под
    перемирием. Ёмкость растёт от инфраструктуры и реки; обе стороны
    получают доход в казну и на склад ресурсов. При войне маршруты рвутся.
    """

    name = "trade"
    priority = 25

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Пересобирает маршруты и начисляет доход."""
        factions = {faction.id: faction for faction in state.factions}
        old_keys = {
            _route_key(route.from_tile, route.to_tile, route.resource)
            for route in state.trade_routes
        }
        routes: list[TradeRoute] = []
        events: list[Event] = []

        for faction in sorted(state.factions, key=lambda item: item.id):
            for tile in state.map.tiles:
                if tile.owner_id != faction.id or not tile.is_land:
                    continue
                for neighbor in state.map.neighbors(tile.x, tile.y):
                    if neighbor.owner_id is None or neighbor.owner_id == tile.owner_id:
                        continue
                    if tile.owner_id > neighbor.owner_id:
                        continue
                    if self._blocked(state, tile.owner_id, neighbor.owner_id):
                        continue
                    resource = tile.resource_type
                    if resource is ResourceType.NONE:
                        resource = neighbor.resource_type
                    if resource is ResourceType.NONE:
                        continue
                    capacity = 1.0 + (tile.infrastructure + neighbor.infrastructure) / 200.0
                    if tile.has_river or neighbor.has_river:
                        capacity += 0.5
                    route = TradeRoute(
                        from_tile=tile.id,
                        to_tile=neighbor.id,
                        resource=resource,
                        capacity=capacity,
                    )
                    routes.append(route)
                    if _route_key(route.from_tile, route.to_tile, route.resource) not in old_keys:
                        events.append(
                            Event(
                                id=0,
                                year=ctx.year,
                                type=EventType.TRADE,
                                summary=(
                                    f"Торговый маршрут {tile.id} ↔ {neighbor.id}: {resource.value}"
                                ),
                                tile_ids=(tile.id, neighbor.id),
                                faction_ids=(tile.owner_id, neighbor.owner_id),
                                severity=0.5,
                            )
                        )

        treasury: dict[int, float] = {}
        resources: dict[int, dict[str, float]] = {}
        for route in routes:
            from_tile = state.map.by_id(route.from_tile)
            to_tile = state.map.by_id(route.to_tile)
            for owner_id in (from_tile.owner_id, to_tile.owner_id):
                if owner_id is None:
                    continue
                treasury[owner_id] = treasury.get(owner_id, 0.0) + route.capacity
                bucket = resources.setdefault(owner_id, {})
                key = route.resource.value
                bucket[key] = bucket.get(key, 0.0) + route.capacity * RESOURCE_SHARE

        faction_updates = self._faction_updates(factions, treasury, resources)
        return RuleOutcome(
            faction_updates=faction_updates,
            events=tuple(events),
            trade_routes=tuple(routes),
        )

    @staticmethod
    def _blocked(state: WorldState, first: int, second: int) -> bool:
        """Война или перемирие запрещают торговлю."""
        for war in state.wars:
            if {war.attacker_id, war.defender_id} != {first, second}:
                continue
            if war.active:
                return True
            if war.truce_until_year is not None and war.truce_until_year >= state.year:
                return True
        return False

    @staticmethod
    def _faction_updates(
        factions: dict[int, Faction],
        treasury: dict[int, float],
        resources: dict[int, dict[str, float]],
    ) -> tuple[FactionUpdate, ...]:
        """Собирает доход фракций от торговли."""
        updates: list[FactionUpdate] = []
        for faction_id, faction in factions.items():
            changes: dict[str, object] = {}
            if treasury.get(faction_id):
                changes["treasury"] = faction.treasury + treasury[faction_id]
            if resources.get(faction_id):
                merged = dict(faction.resources)
                for key, amount in resources[faction_id].items():
                    merged[key] = merged.get(key, 0.0) + amount
                changes["resources"] = merged
            if changes:
                updates.append(FactionUpdate(faction_id=faction_id, changes=changes))
        return tuple(updates)


def _route_key(from_tile: int, to_tile: int, resource: ResourceType) -> tuple[int, int, str]:
    """Ключ маршрута без учёта направления."""
    return min(from_tile, to_tile), max(from_tile, to_tile), resource.value
