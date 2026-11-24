"""Боевая магия: расход маны и контршколы."""

from __future__ import annotations

from worldsim.core.faction import Faction, MagicSchool
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, MagicBoost, RuleOutcome, StepContext

MANA_SPEND_SHARE = 0.1
MAGIC_BONUS_FACTOR = 0.2
SCHOOL_ADVANTAGE = 0.15
SCHOOL_PENALTY = -0.10

# Побеждающая школа: FIRE > ICE > NATURE > NECROMANCY > FIRE.
_BEATS: dict[MagicSchool, MagicSchool] = {
    MagicSchool.FIRE: MagicSchool.ICE,
    MagicSchool.ICE: MagicSchool.NATURE,
    MagicSchool.NATURE: MagicSchool.NECROMANCY,
    MagicSchool.NECROMANCY: MagicSchool.FIRE,
}


class MagicCombatRule:
    """Перед боем тратит до 10 % маны и учитывает контршколы.

    Результат складывается в ``StepContext.magic_boosts`` и используется
    ``WarResolutionRule`` при расчёте атаки.
    """

    name = "magic_combat"
    priority = 18

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Готовит магические бонусы для очереди боёв."""
        working = {faction.id: faction for faction in state.factions}
        spent: dict[int, int] = {}

        for request in ctx.pending_battles:
            attacker = working.get(request.attacker_id)
            defender = working.get(request.defender_id)
            if attacker is None or defender is None:
                continue
            before = max(0, attacker.mana_pool)
            amount = min(before, int(before * MANA_SPEND_SHARE))
            bonus = MAGIC_BONUS_FACTOR * (amount / max(1, before)) * attacker.magic_power()
            modifier = _school_modifier(attacker, defender)
            if amount > 0:
                working[attacker.id] = attacker.evolve(mana_pool=before - amount)
                spent[attacker.id] = spent.get(attacker.id, 0) + amount
            ctx.magic_boosts.append(
                MagicBoost(
                    attacker_id=attacker.id,
                    defender_id=defender.id,
                    tile_id=request.tile_id,
                    mana_spent=amount,
                    magic_bonus=bonus,
                    school_modifier=modifier,
                )
            )

        updates = tuple(
            FactionUpdate(
                faction_id=faction_id,
                changes={"mana_pool": working[faction_id].mana_pool},
            )
            for faction_id in sorted(spent)
        )
        return RuleOutcome(faction_updates=updates)


def _school_modifier(attacker: Faction, defender: Faction) -> float:
    """Считает преимущество контршколы для атакующего."""
    if not attacker.magic_schools:
        return 0.0
    defender_schools = set(defender.magic_schools)
    if any(_BEATS[school] in defender_schools for school in attacker.magic_schools):
        return SCHOOL_ADVANTAGE
    return SCHOOL_PENALTY
