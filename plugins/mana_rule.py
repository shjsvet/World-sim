"""Пример плагина: мана ускоряет рост населения.

Подключается через ``load_rules(["plugins/mana_rule.py"])`` или
``scripts/run_sim.py --plugin plugins/mana_rule.py``.
"""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.state import WorldState
from worldsim.engine.rules import RuleOutcome, StepContext, TileUpdate


class ManaRegenerationRule:
    """При ``magic_level > 0`` население растёт быстрее."""

    name = "mana_regeneration"
    priority = 11

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Добавляет прирост населения от маны и изредка событие ``CUSTOM``."""
        level = state.config.magic_level
        if level <= 0.0:
            return RuleOutcome()

        updates: list[TileUpdate] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            bonus = max(1, int(tile.population * 0.02 * level))
            updates.append(TileUpdate(tile_id=tile.id, population=tile.population + bonus))

        events: list[Event] = []
        if level >= 0.7 and ctx.rng.chance(0.1):
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.CUSTOM,
                    summary="Мана ускорила рост населения",
                    severity=0.5,
                )
            )
        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))


RULES = [ManaRegenerationRule()]
