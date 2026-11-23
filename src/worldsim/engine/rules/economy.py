"""Экономика фракции: снабжение, казна, армия, технологии и мана."""

from __future__ import annotations

from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext, TileUpdate

UPKEEP_PER_SOLDIER = 0.5
RECRUITMENT_MIN_TREASURY = 50.0
RECRUITMENT_COST_PER_SOLDIER = 2.0
MAX_RECRUIT_SHARE = 0.10
TECH_COST = 10.0
TECH_GROWTH = 0.02
TECH_MAX = 10.0


class EconomyRule:
    """Ведёт хозяйство фракций: еду, казну, армию, технологии и ману.

    Правило выполняется до экспансии и войны. Строительство пока не
    моделируется: расходы казны зарезервированы под будущую задачу (T44+),
    а сейчас золото уходит на содержание и набор армии и на технологии.

    Все изменения проходят через ``Faction.evolve`` и ``faction_updates``;
    порядок обхода фракций и все случайные числа детерминированы.
    """

    name = "economy"
    priority = 5

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Считает баланс фракций за год.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага с метриками и генератором.

        Returns:
            Изменения фракций и населения тайлов, события экономики.
        """
        tile_updates: list[TileUpdate] = []
        faction_updates: list[FactionUpdate] = []
        events: list[Event] = []

        for faction in sorted(state.factions, key=lambda item: item.id):
            stats = ctx.stats.get(faction.id)
            if stats is None:
                continue
            current = faction
            food = current.food_stockpile + stats.food_production - stats.food_consumption

            if food < 0.0:
                losses = ctx.rng.uniform(0.05, 0.15)
                for tile in state.map.tiles:
                    if tile.owner_id != faction.id or tile.population <= 0:
                        continue
                    tile_updates.append(
                        TileUpdate(
                            tile_id=tile.id,
                            population=max(0, int(tile.population * (1.0 - losses))),
                        )
                    )
                food = 0.0
                current = current.evolve(
                    morale=max(0.0, current.morale - 0.05),
                    aggressiveness=min(1.0, current.aggressiveness + 0.05),
                )
                events.append(
                    Event.starvation(
                        year=ctx.year,
                        faction_id=faction.id,
                        severity=losses,
                    )
                )

            current = current.evolve(food_stockpile=food)

            upkeep = current.army_size * UPKEEP_PER_SOLDIER
            if upkeep > 0.0:
                if current.treasury >= upkeep:
                    current = current.evolve(treasury=current.treasury - upkeep)
                else:
                    deficit = upkeep - current.treasury
                    ratio = min(0.5, deficit / max(upkeep, 1e-9))
                    current = current.evolve(
                        treasury=0.0,
                        army_size=max(0.0, current.army_size * (1.0 - ratio)),
                        morale=max(0.0, current.morale - 0.02),
                    )
                    events.append(
                        Event(
                            id=0,
                            year=ctx.year,
                            type=EventType.DESERTION,
                            summary=(
                                f"Дезертирство во фракции {faction.id}: нет денег на содержание"
                            ),
                            faction_ids=(faction.id,),
                            severity=ratio,
                        )
                    )

            before_recruitment = current
            current = self._recruit(current, stats.population, ctx)
            recruited = current.army_size - before_recruitment.army_size
            if recruited > 0.0:
                limit = max(1.0, stats.population * MAX_RECRUIT_SHARE)
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.RECRUITMENT,
                        summary=f"Фракция {faction.id} набрала рекрутов",
                        faction_ids=(faction.id,),
                        severity=min(1.0, recruited / limit),
                    )
                )

            if current.treasury > TECH_COST and current.tech_level < TECH_MAX:
                gain = TECH_GROWTH * (1.0 + current.ideology.tech_bonus)
                current = current.evolve(
                    treasury=current.treasury - TECH_COST,
                    tech_level=min(TECH_MAX, current.tech_level + gain),
                )
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.TECH_ADVANCE,
                        summary=f"Фракция {faction.id} улучшила технологии",
                        faction_ids=(faction.id,),
                        severity=0.1,
                    )
                )

            if stats.mana_income > 0:
                current = current.evolve(mana_pool=current.mana_pool + stats.mana_income)

            changes = self._changes(faction, current)
            if changes:
                faction_updates.append(FactionUpdate(faction_id=faction.id, changes=changes))

        return RuleOutcome(
            tile_updates=tuple(tile_updates),
            faction_updates=tuple(faction_updates),
            events=tuple(events),
        )

    def _recruit(self, faction: Faction, population: int, ctx: StepContext) -> Faction:
        """Набирает рекрутов в пределах 10 % населения, если хватает золота."""
        target = population * faction.ideology.army_share
        if faction.army_size >= target:
            return faction
        if faction.treasury < RECRUITMENT_MIN_TREASURY:
            return faction

        limit = population * MAX_RECRUIT_SHARE
        desired = min(target - faction.army_size, limit)
        if desired <= 0:
            return faction

        cost = desired * RECRUITMENT_COST_PER_SOLDIER
        if faction.treasury >= cost:
            return faction.evolve(
                treasury=faction.treasury - cost,
                army_size=faction.army_size + desired,
            )

        affordable = faction.treasury / RECRUITMENT_COST_PER_SOLDIER
        return faction.evolve(treasury=0.0, army_size=faction.army_size + affordable)

    @staticmethod
    def _changes(before: Faction, after: Faction) -> dict[str, object]:
        """Собирает изменившиеся поля фракции."""
        fields = (
            "army_size",
            "treasury",
            "morale",
            "aggressiveness",
            "tech_level",
            "mana_pool",
            "food_stockpile",
        )
        changes: dict[str, object] = {}
        for name in fields:
            new_value = getattr(after, name)
            if new_value != getattr(before, name):
                changes[name] = new_value
        return changes
