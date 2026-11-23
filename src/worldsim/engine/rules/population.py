"""Правило роста населения тайлов."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.state import WorldState
from worldsim.engine.rules import RuleOutcome, StepContext, TileUpdate


class PopulationGrowthRule:
    """Население растёт от плодородия, пока не достигнет ёмкости тайла.

    Перенаселение (население выше ёмкости) разрешается голодом: население
    возвращается к ёмкости, а в летопись попадает ``FAMINE``.
    """

    name = "population"
    priority = 10

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Рассчитывает прирост населения и события голода.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага (год, конфиг, генератор).

        Returns:
            Изменения населения тайлов и события голода.
        """
        updates: list[TileUpdate] = []
        events: list[Event] = []

        for tile in state.map.tiles:
            if not tile.is_land:
                continue

            capacity = tile.population_capacity
            if tile.population > capacity:
                severity = min(1.0, (tile.population - capacity) / max(1, capacity))
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.FAMINE,
                        summary=f"Голод в тайле {tile.id}: население выше ёмкости",
                        tile_ids=(tile.id,),
                        severity=severity,
                    )
                )
                updates.append(TileUpdate(tile_id=tile.id, population=capacity))
                continue

            if tile.population >= capacity or ctx.config.growth_rate <= 0:
                continue

            growth = int(tile.population * ctx.config.growth_rate * tile.fertility / 100.0)
            if growth <= 0:
                growth = 1
            new_population = min(capacity, tile.population + growth)
            if new_population != tile.population:
                updates.append(TileUpdate(tile_id=tile.id, population=new_population))

        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))
