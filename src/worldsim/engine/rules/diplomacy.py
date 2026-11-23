"""Дипломатия: запрос мира и перемирие."""

from __future__ import annotations

from worldsim.core.diplomacy import War
from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.state import WorldState
from worldsim.engine.metrics import MORALE_PEACE_THRESHOLD
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext

TRUCE_YEARS = 10
PEACE_MORALE_BONUS = 0.1
PEACE_AGGRESSION_DROP = 0.1
PEACE_OPPONENT_MORALE = 0.5


class DiplomacyRule:
    """Просит мира при низкой морали и заключает перемирие.

    Фракция с моралью ниже порога, ведущая активную войну, с вероятностью
    ``min(1, (порог − мораль) × 2)`` запрашивает мир. Противник соглашается,
    если его мораль ниже 0.5 или его потери выше потерь просящего. После мира
    война закрывается, обе стороны восстанавливают мораль и снижают
    агрессивность, а перемирие длится ``TRUCE_YEARS`` лет.
    """

    name = "diplomacy"
    priority = 30

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Обрабатывает активные войны и запросы мира.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага.

        Returns:
            Изменения фракций, события дипломатии и записи войн.
        """
        factions = {faction.id: faction for faction in state.factions}
        working = dict(factions)
        wars: dict[int, War] = {war.id: war for war in state.wars}
        events: list[Event] = []

        for war_id in sorted(wars):
            war = wars[war_id]
            if not war.active:
                continue
            if war.attacker_id not in working or war.defender_id not in working:
                continue

            for asker_id, opponent_id in (
                (war.attacker_id, war.defender_id),
                (war.defender_id, war.attacker_id),
            ):
                asker = working[asker_id]
                if asker.morale >= MORALE_PEACE_THRESHOLD:
                    continue
                probability = min(1.0, (MORALE_PEACE_THRESHOLD - asker.morale) * 2.0)
                if not ctx.rng.chance(probability):
                    continue

                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.PEACE_OFFER,
                        summary=f"Фракция {asker_id} запросила мир у фракции {opponent_id}",
                        faction_ids=(asker_id, opponent_id),
                        severity=min(1.0, MORALE_PEACE_THRESHOLD - asker.morale),
                    )
                )

                opponent = working[opponent_id]
                if not self._accepts(war, opponent, asker_id, opponent_id):
                    continue

                wars[war_id] = war.model_copy(
                    update={
                        "active": False,
                        "truce_until_year": state.year + TRUCE_YEARS,
                    }
                )
                for faction_id in (asker_id, opponent_id):
                    current = working[faction_id]
                    working[faction_id] = current.evolve(
                        morale=min(1.0, current.morale + PEACE_MORALE_BONUS),
                        aggressiveness=max(0.0, current.aggressiveness - PEACE_AGGRESSION_DROP),
                    )
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.PEACE_TREATY,
                        summary=f"Мир между фракциями {asker_id} и {opponent_id}",
                        faction_ids=(asker_id, opponent_id),
                        severity=1.0,
                    )
                )
                break

        faction_updates = self._faction_updates(factions, working)
        return RuleOutcome(
            faction_updates=faction_updates,
            events=tuple(events),
            wars=tuple(wars.values()),
        )

    @staticmethod
    def _accepts(war: War, opponent: Faction, asker_id: int, opponent_id: int) -> bool:
        """Решает, принимает ли противник мир (детерминированно)."""
        if opponent.morale < PEACE_OPPONENT_MORALE:
            return True
        opponent_losses = (
            war.attacker_losses if war.attacker_id == opponent_id else war.defender_losses
        )
        asker_losses = war.attacker_losses if war.attacker_id == asker_id else war.defender_losses
        return opponent_losses > asker_losses

    @staticmethod
    def _faction_updates(
        original: dict[int, Faction],
        working: dict[int, Faction],
    ) -> tuple[FactionUpdate, ...]:
        """Собирает изменения морали и агрессивности фракций."""
        updates: list[FactionUpdate] = []
        for faction_id, before in original.items():
            after = working[faction_id]
            changes: dict[str, object] = {}
            if after.morale != before.morale:
                changes["morale"] = after.morale
            if after.aggressiveness != before.aggressiveness:
                changes["aggressiveness"] = after.aggressiveness
            if changes:
                updates.append(FactionUpdate(faction_id=faction_id, changes=changes))
        return tuple(updates)
