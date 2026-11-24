"""Магическая экономика: доход маны, академии и исследования."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction, MagicSchool
from worldsim.core.magic import (
    ACADEMY_COST_GOLD,
    ACADEMY_COST_MANA,
    ACADEMY_MAX_LEVEL,
    ACADEMY_MIN_DENSITY,
    LEY_LINE_MANA_BONUS,
    RESEARCH_AFFINITY_STEP,
    RESEARCH_COST_MANA,
    MagicAcademy,
)
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext


class ManaRule:
    """Накапливает ману с контролируемых тайлов."""

    name = "mana"
    priority = 6

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Пополняет ``mana_pool`` доходом тайлов и лей-линий."""
        updates: list[FactionUpdate] = []
        for faction in sorted(state.factions, key=lambda item: item.id):
            stats = ctx.stats.get(faction.id)
            if stats is None:
                continue
            income = stats.mana_income + LEY_LINE_MANA_BONUS * stats.ley_lines
            if income <= 0:
                continue
            mana_pool = max(0, faction.mana_pool + income)
            updates.append(
                FactionUpdate(
                    faction_id=faction.id,
                    changes={"mana_pool": mana_pool},
                )
            )
        return RuleOutcome(faction_updates=tuple(updates))


class AcademyRule:
    """Строит магические академии на богатых маной тайлах."""

    name = "academy"
    priority = 14

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Строит не больше одной академии на фракцию за год."""
        academies = list(state.academies)
        occupied = {academy.tile_id for academy in academies}
        next_id = max((academy.id for academy in academies), default=-1) + 1
        working = {faction.id: faction for faction in state.factions}
        events: list[Event] = []

        for faction in sorted(state.factions, key=lambda item: item.id):
            current = working[faction.id]
            if current.treasury < ACADEMY_COST_GOLD:
                continue
            if current.mana_pool < ACADEMY_COST_MANA:
                continue
            candidates = [
                tile
                for tile in state.map.tiles
                if tile.owner_id == faction.id
                and tile.is_land
                and tile.mana_density >= ACADEMY_MIN_DENSITY
                and tile.id not in occupied
            ]
            if not candidates:
                continue
            tile = min(candidates, key=lambda item: (-item.mana_density, item.id))
            school = current.magic_schools[0] if current.magic_schools else MagicSchool.FIRE
            academy = MagicAcademy(
                id=next_id,
                tile_id=tile.id,
                faction_id=faction.id,
                school=school,
                level=1,
                founded_year=ctx.year,
            )
            next_id += 1
            academies.append(academy)
            occupied.add(tile.id)
            schools = tuple(dict.fromkeys((*current.magic_schools, school)))
            working[faction.id] = current.evolve(
                treasury=current.treasury - ACADEMY_COST_GOLD,
                mana_pool=current.mana_pool - ACADEMY_COST_MANA,
                magic_schools=schools,
            )
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.ACADEMY_FOUNDED,
                    summary=f"Академия {school.value} основана в тайле {tile.id}",
                    tile_ids=(tile.id,),
                    faction_ids=(faction.id,),
                    severity=1.0,
                )
            )

        return RuleOutcome(
            faction_updates=_faction_updates(state.factions, working),
            events=tuple(events),
            academies=tuple(academies),
        )


class MagicResearchRule:
    """Тратит ману на рост склонности и уровня академий."""

    name = "magic_research"
    priority = 15

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Проводит исследования при наличии академий и маны."""
        if not state.academies:
            return RuleOutcome()
        academies = list(state.academies)
        working = {faction.id: faction for faction in state.factions}
        events: list[Event] = []

        for faction in sorted(state.factions, key=lambda item: item.id):
            current = working[faction.id]
            owned = [academy for academy in academies if academy.faction_id == faction.id]
            if not owned or current.mana_pool < RESEARCH_COST_MANA:
                continue
            schools = tuple(
                dict.fromkeys(
                    (
                        *current.magic_schools,
                        *(academy.school for academy in owned),
                    )
                )
            )
            working[faction.id] = current.evolve(
                mana_pool=current.mana_pool - RESEARCH_COST_MANA,
                magic_affinity=min(
                    100,
                    current.magic_affinity + RESEARCH_AFFINITY_STEP,
                ),
                magic_schools=schools,
            )
            target = max(owned, key=lambda academy: (academy.level, -academy.id))
            index = academies.index(target)
            academies[index] = target.model_copy(
                update={"level": min(ACADEMY_MAX_LEVEL, target.level + 1)}
            )
            if ctx.year % 5 == 0:
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.MAGIC_BREAKTHROUGH,
                        summary=f"Магический прорыв фракции {faction.id}",
                        tile_ids=(target.tile_id,),
                        faction_ids=(faction.id,),
                        severity=0.5,
                    )
                )

        return RuleOutcome(
            faction_updates=_faction_updates(state.factions, working),
            events=tuple(events),
            academies=tuple(academies),
        )


def _faction_updates(
    before: tuple[Faction, ...],
    after: dict[int, Faction],
) -> tuple[FactionUpdate, ...]:
    """Собирает изменения фракций по магическим полям."""
    fields = ("treasury", "mana_pool", "magic_affinity", "magic_schools")
    updates: list[FactionUpdate] = []
    for faction in before:
        current = after[faction.id]
        changes: dict[str, object] = {}
        for name in fields:
            new_value = getattr(current, name)
            if new_value != getattr(faction, name):
                changes[name] = new_value
        if changes:
            updates.append(FactionUpdate(faction_id=faction.id, changes=changes))
    return tuple(updates)
