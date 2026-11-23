"""Армии на карте: распределение, фронты и гарнизоны."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.state import WorldState
from worldsim.engine.rules import RuleOutcome, StepContext, TileUpdate

FRONTIER_BONUS = 1.2
RIVER_DISCOUNT = 0.8


class ArmyMovementRule:
    """Распределяет армию фракции по её тайлам.

    Приоритет получают тайлы на границе с врагом и тайлы с высоким
    недовольством. Логистика учитывает стоимость перемещения биома, высоту,
    реку и инфраструктуру. Суммарный гарнизон не превышает ``army_size``.
    """

    name = "army"
    priority = 7

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Расставляет гарнизоны по владениям фракций."""
        updates: list[TileUpdate] = []

        for faction in sorted(state.factions, key=lambda item: item.id):
            owned = [
                tile for tile in state.map.tiles if tile.owner_id == faction.id and tile.is_land
            ]
            if not owned:
                continue
            stats = ctx.stats.get(faction.id)
            enemies = set(stats.enemies) if stats is not None else set()
            budget = max(0, int(faction.army_size))

            weights = {tile.id: self._tile_weight(state, tile, enemies) for tile in owned}
            total_weight = sum(weights.values())
            if total_weight <= 0.0:
                total_weight = float(len(owned))
                weights = {tile.id: 1.0 for tile in owned}

            presence: dict[int, int] = {}
            remaining = budget
            for tile_id in sorted(weights, key=lambda item: (-weights[item], item)):
                share = int(budget * weights[tile_id] / total_weight)
                allocated = min(share, remaining)
                presence[tile_id] = allocated
                remaining -= allocated
            for tile_id in sorted(weights, key=lambda item: (-weights[item], item)):
                if remaining <= 0:
                    break
                presence[tile_id] += 1
                remaining -= 1

            for tile in owned:
                new_presence = presence[tile.id]
                if new_presence != tile.army_presence:
                    updates.append(TileUpdate(tile_id=tile.id, army_presence=new_presence))

        return RuleOutcome(tile_updates=tuple(updates))

    @staticmethod
    def _tile_weight(
        state: WorldState,
        tile: object,
        enemies: set[int],
    ) -> float:
        """Считает привлекательность тайла для размещения гарнизона."""
        from worldsim.core.geography import RegionData

        if not isinstance(tile, RegionData):
            return 1.0
        weight = 1.0 + tile.unrest / 50.0
        frontier = any(
            neighbor.owner_id in enemies for neighbor in state.map.neighbors(tile.x, tile.y)
        )
        if frontier:
            weight *= 3.0 * FRONTIER_BONUS
        cost = tile.biome.movement_cost * (1.0 + tile.elevation / 1000.0)
        if tile.has_river:
            cost *= RIVER_DISCOUNT
        cost *= max(0.5, 1.0 - tile.infrastructure / 200.0)
        return weight / max(0.1, cost)


class FrontlineRule:
    """Укрепляет приграничные тайлы: гарнизон роет окопы.

    Каждый год тайл на границе с враждебной фракцией получает +1 к
    фортификации (до 100), что усиливает защиту в бою (T21).
    """

    name = "frontline"
    priority = 8

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Поднимает фортификацию приграничных тайлов."""
        updates: list[TileUpdate] = []
        for faction in state.factions:
            stats = ctx.stats.get(faction.id)
            enemies = set(stats.enemies) if stats is not None else set()
            if not enemies:
                continue
            for tile in state.map.tiles:
                if tile.owner_id != faction.id or not tile.is_land:
                    continue
                frontier = any(
                    neighbor.owner_id in enemies for neighbor in state.map.neighbors(tile.x, tile.y)
                )
                if not frontier:
                    continue
                new_value = min(100.0, tile.fortification + 1.0)
                if new_value != tile.fortification:
                    updates.append(TileUpdate(tile_id=tile.id, fortification=new_value))
        return RuleOutcome(tile_updates=tuple(updates))


class OccupationRule:
    """Следит за гарнизонами: чужой тайл меняет владельца только в бою.

    Правило не захватывает тайлы самостоятельно. Оно снимает гарнизоны с
    нейтральных тайлов и не позволяет держать больше солдат, чем есть у
    фракции; событие ``OCCUPATION`` фиксирует потерю гарнизона.
    """

    name = "occupation"
    priority = 21

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Приводит гарнизоны в соответствие с владением и армией."""
        factions = {faction.id: faction for faction in state.factions}
        updates: list[TileUpdate] = []
        events: list[Event] = []

        for tile in state.map.tiles:
            if tile.army_presence <= 0 or tile.owner_id is None:
                continue
            faction = factions.get(tile.owner_id)
            if faction is None:
                continue
            limit = max(0, int(faction.army_size))
            if tile.army_presence > limit:
                updates.append(TileUpdate(tile_id=tile.id, army_presence=limit))
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.OCCUPATION,
                        summary=f"Гарнизон тайла {tile.id} сокращён до армии фракции",
                        tile_ids=(tile.id,),
                        faction_ids=(faction.id,),
                        severity=1.0,
                    )
                )

        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))
