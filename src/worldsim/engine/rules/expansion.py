"""Правило экспансии: голод и агрессивность толкают фракции на соседей."""

from __future__ import annotations

from worldsim.core.events import Event
from worldsim.core.faction import Faction, culture_conflict_factor
from worldsim.core.geography import RegionData
from worldsim.core.state import WorldState
from worldsim.engine.rules import BattleRequest, RuleOutcome, StepContext, TileUpdate


class ExpansionRule:
    """Фракция занимает нейтральные тайлы и атакует чужие.

    Нейтральный тайл переходит сразу, чужой порождает ``BattleRequest`` в
    ``StepContext.pending_battles`` для ``WarResolutionRule`` (T21). Голодная
    фракция атакует всегда, сытая — с вероятностью, зависящей от её
    агрессивности, параметра мира и культурной близости.
    """

    name = "expansion"
    priority = 10

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Формирует захваты нейтральных тайлов и заявки на бой.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага с метриками и очередью боёв.

        Returns:
            Изменения владения и события ``EXPANSION`` / ``WAR``.
        """
        updates: list[TileUpdate] = []
        events: list[Event] = []
        factions_by_id = {faction.id: faction for faction in state.factions}

        for faction in sorted(state.factions, key=lambda item: item.id):
            stats = ctx.stats.get(faction.id)
            starving = stats.is_starving if stats is not None else False

            targets = self._candidates(state, faction)
            weights: dict[int, float] = {}
            for tile in targets:
                if tile.owner_id is not None:
                    defender = factions_by_id.get(tile.owner_id)
                    if defender is None:
                        continue
                    if self._at_truce(state, faction.id, defender.id):
                        continue
                weight = self._target_weight(tile)
                if weight > 0:
                    weights[tile.id] = weight
            if not weights:
                continue

            target_id = ctx.rng.weighted_choice(weights)
            target = state.map.by_id(target_id)
            defender_id = target.owner_id

            if not starving:
                factor = (
                    1.0
                    if defender_id is None
                    else culture_conflict_factor(faction, factions_by_id[defender_id])
                )
                probability = min(
                    1.0,
                    faction.aggressiveness * ctx.config.aggression * factor,
                )
                if not ctx.rng.chance(probability):
                    continue

            if defender_id is None:
                updates.append(TileUpdate(tile_id=target.id, owner_id=faction.id, set_owner=True))
                events.append(
                    Event.expansion(
                        year=ctx.year,
                        faction_id=faction.id,
                        tile_id=target.id,
                    )
                )
            else:
                ctx.pending_battles.append(
                    BattleRequest(
                        attacker_id=faction.id,
                        defender_id=defender_id,
                        tile_id=target.id,
                    )
                )
                events.append(
                    Event.war(
                        year=ctx.year,
                        attacker_id=faction.id,
                        defender_id=defender_id,
                        tile_id=target.id,
                    )
                )

        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))

    @staticmethod
    def _candidates(state: WorldState, faction: Faction) -> list[RegionData]:
        """Возвращает соседние тайлы фракции, не принадлежащие ей."""
        owned = {tile.id for tile in state.map.tiles if tile.owner_id == faction.id}
        candidates: dict[int, RegionData] = {}
        for tile_id in owned:
            tile = state.map.by_id(tile_id)
            for neighbor in state.map.neighbors(tile.x, tile.y):
                if neighbor.id in owned or not neighbor.is_land:
                    continue
                candidates[neighbor.id] = neighbor
        return list(candidates.values())

    @staticmethod
    def _target_weight(tile: RegionData) -> float:
        """Вес привлекательности тайла для атаки."""
        fortification_factor = max(0.0, 1.0 - tile.fortification / 150.0)
        return (
            tile.fertility
            * fortification_factor
            * (1.0 + tile.unrest / 100.0)
            / (tile.army_presence + 1)
            / (1.0 + tile.elevation / 1000.0)
        )

    @staticmethod
    def _at_truce(state: WorldState, attacker_id: int, defender_id: int) -> bool:
        """Проверяет перемирие между фракциями (появится в T41)."""
        wars: object = getattr(state, "wars", ())
        if not isinstance(wars, tuple):
            return False
        for war in wars:
            if getattr(war, "active", True):
                continue
            truce_until = getattr(war, "truce_until_year", None)
            if not isinstance(truce_until, int) or truce_until < state.year:
                continue
            attacker = getattr(war, "attacker_id", None)
            defender = getattr(war, "defender_id", None)
            if {attacker, defender} == {attacker_id, defender_id}:
                return True
        return False
