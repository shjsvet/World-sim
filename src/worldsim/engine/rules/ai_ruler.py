"""Исполнение решений ИИ-правителей в движке."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction
from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction, MagicSchool
from worldsim.core.geography import ResourceType
from worldsim.core.magic import (
    ACADEMY_COST_GOLD,
    ACADEMY_COST_MANA,
    ACADEMY_MIN_DENSITY,
    MagicAcademy,
)
from worldsim.core.state import WorldState
from worldsim.engine.rules import (
    AICommand,
    FactionUpdate,
    RuleOutcome,
    StepContext,
    TileUpdate,
)

RECRUITMENT_COST = 2.0
DEFAULT_EXTRACTION = 20
DEFAULT_REDISTRIBUTION = 10


class AIRulerRule:
    """Превращает решения правителей в изменения мира."""

    name = "ai_ruler"
    priority = 4

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Выполняет команды ИИ из ``StepContext.ai_decisions``."""
        original = {faction.id: faction for faction in state.factions}
        working = dict(original)
        academies = list(state.academies)
        next_academy_id = max((item.id for item in academies), default=-1) + 1
        tile_updates: list[TileUpdate] = []
        events: list[Event] = []

        for command in ctx.ai_decisions:
            faction = working.get(command.faction_id)
            if faction is None:
                continue
            action = command.decision.action
            if action is RulerAction.BUILD_ACADEMY:
                next_academy_id = self._build_academy(
                    state,
                    faction,
                    command,
                    academies,
                    events,
                    next_academy_id,
                    working,
                    ctx.year,
                )
            elif action is RulerAction.RECRUIT:
                self._recruit(faction, command, events, working, ctx.year)
            elif action is RulerAction.EXTRACT_RESOURCE:
                self._extract(
                    state,
                    faction,
                    command,
                    tile_updates,
                    events,
                    working,
                    ctx.year,
                )
            elif action is RulerAction.REDISTRIBUTE_POPULATION:
                self._redistribute(
                    state,
                    faction,
                    command,
                    tile_updates,
                    events,
                    ctx.year,
                )

        return RuleOutcome(
            tile_updates=tuple(tile_updates),
            faction_updates=_faction_updates(original, working),
            events=tuple(events),
            academies=tuple(academies),
        )

    @staticmethod
    def _build_academy(
        state: WorldState,
        faction: Faction,
        command: AICommand,
        academies: list[MagicAcademy],
        events: list[Event],
        next_id: int,
        working: dict[int, Faction],
        year: int,
    ) -> int:
        target_id = command.decision.target_tile_id
        if target_id is None or target_id >= len(state.map.tiles):
            return next_id
        tile = state.map.by_id(target_id)
        if tile.owner_id != faction.id or not tile.is_land:
            return next_id
        if tile.mana_density < ACADEMY_MIN_DENSITY:
            return next_id
        if any(item.tile_id == target_id for item in academies):
            return next_id
        if faction.treasury < ACADEMY_COST_GOLD or faction.mana_pool < ACADEMY_COST_MANA:
            return next_id
        school = faction.magic_schools[0] if faction.magic_schools else MagicSchool.FIRE
        academies.append(
            MagicAcademy(
                id=next_id,
                tile_id=target_id,
                faction_id=faction.id,
                school=school,
                level=1,
                founded_year=year,
            )
        )
        schools = tuple(dict.fromkeys((*faction.magic_schools, school)))
        working[faction.id] = faction.evolve(
            treasury=faction.treasury - ACADEMY_COST_GOLD,
            mana_pool=faction.mana_pool - ACADEMY_COST_MANA,
            magic_schools=schools,
        )
        events.append(
            Event(
                id=0,
                year=year,
                type=EventType.ACADEMY_FOUNDED,
                summary=f"Академия {school.value} основана в тайле {target_id}",
                tile_ids=(target_id,),
                faction_ids=(faction.id,),
                severity=1.0,
            )
        )
        return next_id + 1

    @staticmethod
    def _recruit(
        faction: Faction,
        command: AICommand,
        events: list[Event],
        working: dict[int, Faction],
        year: int,
    ) -> None:
        amount = command.decision.amount
        if amount <= 0:
            return
        cost = amount * RECRUITMENT_COST
        if faction.treasury < cost:
            return
        working[faction.id] = faction.evolve(
            treasury=faction.treasury - cost,
            army_size=faction.army_size + amount,
        )
        events.append(
            Event(
                id=0,
                year=year,
                type=EventType.RECRUITMENT,
                summary=f"Фракция {faction.id} набрала {amount} солдат по решению ИИ",
                faction_ids=(faction.id,),
                severity=min(1.0, amount / max(1.0, faction.army_size + amount)),
            )
        )

    @staticmethod
    def _extract(
        state: WorldState,
        faction: Faction,
        command: AICommand,
        tile_updates: list[TileUpdate],
        events: list[Event],
        working: dict[int, Faction],
        year: int,
    ) -> None:
        target_id = command.decision.target_tile_id
        if target_id is None or target_id >= len(state.map.tiles):
            return
        tile = state.map.by_id(target_id)
        if tile.owner_id != faction.id:
            return
        if tile.resource_type is ResourceType.NONE or tile.resource_depletion <= 0:
            return
        requested = (
            command.decision.amount
            if command.decision.amount > 0
            else int(min(tile.resource_amount, tile.resource_depletion))
        )
        extracted = min(requested, int(tile.resource_depletion))
        if extracted <= 0:
            return
        remaining = max(0.0, tile.resource_depletion - extracted)
        tile_updates.append(TileUpdate(tile_id=tile.id, resource_depletion=remaining))

        if tile.resource_type is ResourceType.FOOD:
            working[faction.id] = faction.evolve(food_stockpile=faction.food_stockpile + extracted)
        elif tile.resource_type is ResourceType.GOLD:
            working[faction.id] = faction.evolve(treasury=faction.treasury + extracted)
        else:
            resources = dict(faction.resources)
            key = tile.resource_type.value
            resources[key] = resources.get(key, 0.0) + extracted
            working[faction.id] = faction.evolve(resources=resources)

        events.append(
            Event(
                id=0,
                year=year,
                type=EventType.CUSTOM,
                summary=f"ИИ добыл {extracted} {tile.resource_type.value} в тайле {tile.id}",
                tile_ids=(tile.id,),
                faction_ids=(faction.id,),
                severity=0.3,
            )
        )
        if remaining <= 0.0:
            events.append(
                Event(
                    id=0,
                    year=year,
                    type=EventType.RESOURCE_DEPLETED,
                    summary=f"Месторождение тайла {tile.id} истощено",
                    tile_ids=(tile.id,),
                    faction_ids=(faction.id,),
                    severity=1.0,
                )
            )

    @staticmethod
    def _redistribute(
        state: WorldState,
        faction: Faction,
        command: AICommand,
        tile_updates: list[TileUpdate],
        events: list[Event],
        year: int,
    ) -> None:
        target_id = command.decision.target_tile_id
        if target_id is None or target_id >= len(state.map.tiles):
            return
        target = state.map.by_id(target_id)
        if target.owner_id != faction.id:
            return
        owned = [
            tile
            for tile in state.map.tiles
            if tile.owner_id == faction.id and tile.id != target_id and tile.population > 0
        ]
        if not owned:
            return
        source = max(owned, key=lambda tile: (tile.population, -tile.id))
        room = max(0, target.population_capacity - target.population)
        wanted = command.decision.amount if command.decision.amount > 0 else DEFAULT_REDISTRIBUTION
        moved = min(wanted, source.population, room)
        if moved <= 0:
            return
        tile_updates.append(TileUpdate(tile_id=source.id, population=source.population - moved))
        tile_updates.append(TileUpdate(tile_id=target.id, population=target.population + moved))
        events.append(
            Event(
                id=0,
                year=year,
                type=EventType.CUSTOM,
                summary=(f"ИИ переселил {moved} человек из тайла {source.id} в тайл {target.id}"),
                tile_ids=(source.id, target.id),
                faction_ids=(faction.id,),
                severity=0.3,
            )
        )


def _faction_updates(
    before: dict[int, Faction],
    after: dict[int, Faction],
) -> tuple[FactionUpdate, ...]:
    """Собирает изменения фракций после действий ИИ."""
    fields = (
        "treasury",
        "mana_pool",
        "army_size",
        "magic_schools",
        "food_stockpile",
        "resources",
    )
    updates: list[FactionUpdate] = []
    for faction_id, original in before.items():
        current = after[faction_id]
        changes: dict[str, object] = {}
        for name in fields:
            new_value = getattr(current, name)
            if new_value != getattr(original, name):
                changes[name] = new_value
        if changes:
            updates.append(FactionUpdate(faction_id=faction_id, changes=changes))
    return tuple(updates)
