"""Социальная динамика тайлов: счастье, недовольство, бунты и города."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext, TileUpdate

RIOT_HAPPINESS = 20.0
RIOT_UNREST = 60.0
SECESSION_UNREST = 80.0
CITY_POPULATION = 1_000
CITY_URBANIZATION = 50.0


def _clamp(value: float, low: float, high: float) -> float:
    """Ограничивает значение диапазоном."""
    return max(low, min(high, value))


class HappinessRule:
    """Счастье жителей тайла.

    Растёт при запасах еды, родной культуре, низком недовольстве и гарнизоне;
    падает при голоде, войне, чужой культуре и высоком недовольстве.
    """

    name = "happiness"
    priority = 12

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Изменяет счастье принадлежащих фракциям тайлов."""
        factions = {faction.id: faction for faction in state.factions}
        updates: list[TileUpdate] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            faction = factions.get(tile.owner_id)
            if faction is None:
                continue
            stats = ctx.stats.get(tile.owner_id)
            delta = 0
            if stats is not None:
                delta += 1 if stats.food_stockpile > 0 else -1
                delta -= 1 if stats.is_starving else 0
                delta -= 1 if stats.enemies else 0
            delta += 1 if tile.culture == faction.culture else -1
            if tile.unrest < 30.0:
                delta += 1
            elif tile.unrest > 60.0:
                delta -= 1
            if tile.army_presence > 0:
                delta += 1
            delta = max(-3, min(3, delta))
            if delta == 0:
                continue
            new_value = _clamp(tile.happiness + delta, 0.0, 100.0)
            if new_value != tile.happiness:
                updates.append(TileUpdate(tile_id=tile.id, happiness=new_value))
        return RuleOutcome(tile_updates=tuple(updates))


class UnrestRule:
    """Недовольство властью: растёт от бед и падает от порядка."""

    name = "unrest"
    priority = 13

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Изменяет недовольство тайлов."""
        factions = {faction.id: faction for faction in state.factions}
        updates: list[TileUpdate] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            faction = factions.get(tile.owner_id)
            if faction is None:
                continue
            stats = ctx.stats.get(tile.owner_id)
            delta = 0
            if tile.happiness < 40.0:
                delta += 1
            if stats is not None and stats.is_starving:
                delta += 1
            if tile.culture != faction.culture:
                delta += 1
            if tile.army_presence > 0:
                delta -= 1
            if tile.infrastructure > 20.0:
                delta -= 1
            delta = max(-2, min(2, delta))
            if delta == 0:
                continue
            new_value = _clamp(tile.unrest + delta, 0.0, 100.0)
            if new_value != tile.unrest:
                updates.append(TileUpdate(tile_id=tile.id, unrest=new_value))
        return RuleOutcome(tile_updates=tuple(updates))


class RiotRule:
    """Бунт: при низком счастье и высоком недовольстве гибнет население."""

    name = "riot"
    priority = 14

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Формирует последствия бунтов."""
        updates: list[TileUpdate] = []
        events: list[Event] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            if tile.happiness >= RIOT_HAPPINESS or tile.unrest <= RIOT_UNREST:
                continue
            losses = ctx.rng.uniform(0.05, 0.15)
            updates.append(
                TileUpdate(
                    tile_id=tile.id,
                    population=max(0, int(tile.population * (1.0 - losses))),
                    unrest=min(100.0, tile.unrest + 10.0),
                )
            )
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.RIOT,
                    summary=f"Бунт в тайле {tile.id}: потери {losses:.0%}",
                    tile_ids=(tile.id,),
                    severity=losses,
                )
            )
        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))


class SecessionRule:
    """Отделение тайла или переход к соседу той же культуры."""

    name = "secession"
    priority = 15

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Обрабатывает тайлы с недовольством выше порога."""
        factions = {faction.id: faction for faction in state.factions}
        updates: list[TileUpdate] = []
        events: list[Event] = []
        lost: dict[int, set[int]] = {}

        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            if tile.unrest <= SECESSION_UNREST:
                continue
            owner_id = tile.owner_id
            target = self._defection_target(state, factions, tile)
            if target is not None:
                updates.append(
                    TileUpdate(
                        tile_id=tile.id,
                        owner_id=target.id,
                        set_owner=True,
                        army_presence=0,
                    )
                )
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.DEFECTION,
                        summary=f"Тайл {tile.id} перешёл к фракции {target.id}",
                        tile_ids=(tile.id,),
                        faction_ids=(owner_id, target.id),
                        severity=min(1.0, tile.unrest / 100.0),
                    )
                )
            else:
                updates.append(
                    TileUpdate(
                        tile_id=tile.id,
                        owner_id=None,
                        set_owner=True,
                        army_presence=0,
                    )
                )
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.SECESSION,
                        summary=f"Тайл {tile.id} отделился от фракции {owner_id}",
                        tile_ids=(tile.id,),
                        faction_ids=(owner_id,),
                        severity=min(1.0, tile.unrest / 100.0),
                    )
                )
            lost.setdefault(owner_id, set()).add(tile.id)

        faction_updates = self._capital_updates(state, factions, lost)
        return RuleOutcome(
            tile_updates=tuple(updates),
            faction_updates=faction_updates,
            events=tuple(events),
        )

    @staticmethod
    def _defection_target(
        state: WorldState,
        factions: dict[int, Faction],
        tile: object,
    ) -> Faction | None:
        """Ищет соседа с той же культурой для перехода тайла."""
        from worldsim.core.geography import RegionData

        if not isinstance(tile, RegionData):
            return None
        for neighbor in state.map.neighbors(tile.x, tile.y):
            if neighbor.owner_id is None or neighbor.owner_id == tile.owner_id:
                continue
            candidate = factions.get(neighbor.owner_id)
            if candidate is not None and candidate.culture == tile.culture:
                return candidate
        return None

    @staticmethod
    def _capital_updates(
        state: WorldState,
        factions: dict[int, Faction],
        lost: dict[int, set[int]],
    ) -> tuple[FactionUpdate, ...]:
        """Переносит столицы фракций, потерявших свои столичные тайлы."""
        updates: list[FactionUpdate] = []
        for faction_id, lost_tiles in lost.items():
            faction = factions[faction_id]
            if faction.capital_tile_id not in lost_tiles:
                continue
            remaining = [
                tile
                for tile in state.map.tiles
                if tile.owner_id == faction_id and tile.id not in lost_tiles and tile.is_land
            ]
            new_capital = (
                min(remaining, key=lambda tile: (-tile.population, tile.id)).id
                if remaining
                else None
            )
            updates.append(
                FactionUpdate(
                    faction_id=faction_id,
                    changes={"capital_tile_id": new_capital},
                )
            )
        return tuple(updates)


class UrbanizationRule:
    """Рост и падение урбанизации, появление городов."""

    name = "urbanization"
    priority = 16

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Меняет урбанизацию и объявляет новые города."""
        updates: list[TileUpdate] = []
        events: list[Event] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land:
                continue
            stats = ctx.stats.get(tile.owner_id)
            starving = stats.is_starving if stats is not None else False
            delta = 0
            if tile.population > 500 and tile.infrastructure > 20.0 and not starving:
                delta += 2
            if starving or tile.happiness < RIOT_HAPPINESS:
                delta -= 2
            if delta == 0:
                continue
            new_urbanization = _clamp(tile.urbanization + delta, 0.0, 100.0)
            new_capacity = tile.population_capacity
            became_city = (
                not tile.is_city
                and tile.population > CITY_POPULATION
                and new_urbanization >= CITY_URBANIZATION
            )
            if became_city:
                new_capacity += 10
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.CITY_RISE,
                        summary=f"Тайл {tile.id} стал городом",
                        tile_ids=(tile.id,),
                        severity=1.0,
                    )
                )
            if new_urbanization != tile.urbanization or new_capacity != tile.population_capacity:
                updates.append(
                    TileUpdate(
                        tile_id=tile.id,
                        urbanization=new_urbanization,
                        population_capacity=new_capacity,
                    )
                )
        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))
