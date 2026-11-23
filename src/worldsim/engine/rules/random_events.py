"""Случайные события движка: эпидемии и голод."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.state import WorldState
from worldsim.engine.rules import RuleOutcome, StepContext, TileUpdate


class PlagueRule:
    """Эпидемия: вероятность зависит от плотности населения.

    При срабатывании выбирается от одного до трёх населённых тайлов, каждый
    теряет 10–60 % населения. Все случайные величины берутся из ``ctx.rng``.
    """

    name = "plague"
    priority = 20

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Проверяет вероятность эпидемии и формирует изменения.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага.

        Returns:
            Изменения населения и события ``PLAGUE``.
        """
        total_population = sum(tile.population for tile in state.map.tiles if tile.is_land)
        area = state.map.size * state.map.size
        density = total_population / area
        probability = min(1.0, ctx.config.plague_chance * (1.0 + density / 100.0))
        if not ctx.rng.chance(probability):
            return RuleOutcome()

        candidates = [tile.id for tile in state.map.tiles if tile.is_land and tile.population > 0]
        if not candidates:
            return RuleOutcome()

        ctx.rng.shuffle(candidates)
        count = min(len(candidates), ctx.rng.int(1, 3))
        updates: list[TileUpdate] = []
        events: list[Event] = []
        for tile_id in candidates[:count]:
            tile = state.map.by_id(tile_id)
            losses = ctx.rng.uniform(0.1, 0.6)
            new_population = max(0, int(tile.population * (1.0 - losses)))
            updates.append(TileUpdate(tile_id=tile_id, population=new_population))
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.PLAGUE,
                    summary=f"Эпидемия в тайле {tile_id}: потери {losses:.0%}",
                    tile_ids=(tile_id,),
                    severity=losses,
                )
            )
        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))


class FamineRule:
    """Голод: перенаселённый тайл теряет население и плодородие.

    Выполняется до роста населения, поэтому движок видит уже исправленный
    снимок. Истощение плодородия тем сильнее, чем больше превышение ёмкости.
    """

    name = "famine"
    priority = 9

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Формирует изменения по перенаселённым тайлам.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага.

        Returns:
            Изменения населения и плодородия, события ``FAMINE``.
        """
        updates: list[TileUpdate] = []
        events: list[Event] = []

        for tile in state.map.tiles:
            if not tile.is_land or tile.population <= tile.population_capacity:
                continue
            capacity = tile.population_capacity
            excess = tile.population - capacity
            severity = min(1.0, excess / max(1, capacity))
            fertility_loss = 2.0 + severity * 8.0
            updates.append(
                TileUpdate(
                    tile_id=tile.id,
                    population=capacity,
                    fertility=max(0.0, tile.fertility - fertility_loss),
                )
            )
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.FAMINE,
                    summary=f"Голод в тайле {tile.id}: перенаселение",
                    tile_ids=(tile.id,),
                    severity=severity,
                )
            )
        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))
