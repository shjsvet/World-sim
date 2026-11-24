"""Правило войны: разрешение боёв, потери, мораль и оккупация."""

from __future__ import annotations

from worldsim.core.diplomacy import War
from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction, culture_conflict_factor
from worldsim.core.geography import RegionData
from worldsim.core.state import WorldState
from worldsim.engine.rules import FactionUpdate, RuleOutcome, StepContext, TileUpdate


class WarResolutionRule:
    """Разрешает заявки на бой, накопленные экспансией.

    Атака сравнивается с защитой тайла (гарнизон, доля армии, магия,
    фортификация и биом). Победитель оккупирует тайл, обе стороны несут
    потери, проигравший теряет мораль, победитель получает трофеи. Война
    заводится или обновляется в ``WorldState.wars``.
    """

    name = "war"
    priority = 20
    max_attacks_per_side = 3

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Разрешает очередь боёв шага.

        Args:
            state: Текущий снимок мира.
            ctx: Контекст шага с очередью боёв.

        Returns:
            Изменения тайлов и фракций, события и записи войн.
        """
        factions = {faction.id: faction for faction in state.factions}
        working = dict(factions)
        boosts = {
            (boost.attacker_id, boost.defender_id, boost.tile_id): boost
            for boost in ctx.magic_boosts
        }
        wars: dict[int, War] = {war.id: war for war in state.wars}
        next_war_id = max(wars, default=-1) + 1
        attacks: dict[int, int] = {}
        captured_tiles: set[int] = set()
        tile_updates: dict[int, TileUpdate] = {}
        events: list[Event] = []

        for request in ctx.pending_battles:
            attacker = working.get(request.attacker_id)
            defender = working.get(request.defender_id)
            if attacker is None or defender is None:
                continue
            if attacks.get(attacker.id, 0) >= self.max_attacks_per_side:
                continue
            if not 0 <= request.tile_id < len(state.map.tiles):
                continue
            tile = state.map.by_id(request.tile_id)
            if tile.owner_id != defender.id or tile.id in captured_tiles:
                continue
            attacks[attacker.id] = attacks.get(attacker.id, 0) + 1

            boost = boosts.get((attacker.id, defender.id, tile.id))
            magic_factor = 1.0 + 0.2 * attacker.magic_power()
            if boost is not None:
                magic_factor += boost.magic_bonus + boost.school_modifier
            attack_roll = (
                attacker.military_power
                * magic_factor
                * ctx.rng.uniform(0.8, 1.2)
                * culture_conflict_factor(attacker, defender)
            )
            garrison = tile.army_presence + 0.25 * defender.army_size
            defense_roll = (
                garrison
                * (1.0 + 0.2 * defender.magic_power())
                * tile.defense_multiplier()
                * ctx.rng.uniform(0.8, 1.2)
            )
            captured = attack_roll > defense_roll
            gap = abs(attack_roll - defense_roll) / max(attack_roll, defense_roll, 1e-9)
            winner_ratio = 0.05 + 0.10 * gap
            loser_ratio = 0.05 + 0.25 * gap

            attacker_loss = attacker.army_size * (winner_ratio if captured else loser_ratio)
            defender_loss = defender.army_size * (loser_ratio if captured else winner_ratio)
            working[attacker.id] = attacker.evolve(
                army_size=max(0.0, attacker.army_size - attacker_loss)
            )
            working[defender.id] = defender.evolve(
                army_size=max(0.0, defender.army_size - defender_loss)
            )

            winner = attacker.id if captured else defender.id
            loser = defender.id if captured else attacker.id
            working[winner] = working[winner].evolve(morale=min(1.0, working[winner].morale + 0.05))
            working[loser] = working[loser].evolve(morale=max(0.0, working[loser].morale - 0.1))

            if captured:
                loot = min(working[defender.id].treasury, ctx.rng.uniform(10.0, 50.0))
                working[attacker.id] = working[attacker.id].evolve(
                    treasury=working[attacker.id].treasury + loot
                )
                working[defender.id] = working[defender.id].evolve(
                    treasury=max(0.0, working[defender.id].treasury - loot)
                )
                tile_updates[tile.id] = self._occupy(tile, working[attacker.id], ctx)
                captured_tiles.add(tile.id)
                events.append(
                    Event(
                        id=0,
                        year=ctx.year,
                        type=EventType.OCCUPATION,
                        summary=f"Фракция {attacker.id} заняла тайл {tile.id}",
                        tile_ids=(tile.id,),
                        faction_ids=(attacker.id, defender.id),
                        severity=min(1.0, gap),
                    )
                )
                if defender.capital_tile_id == tile.id:
                    events.append(
                        Event(
                            id=0,
                            year=ctx.year,
                            type=EventType.CAPITAL_FALL,
                            summary=f"Пала столица фракции {defender.id}",
                            tile_ids=(tile.id,),
                            faction_ids=(defender.id,),
                            severity=1.0,
                        )
                    )
                    working[defender.id] = working[defender.id].evolve(
                        capital_tile_id=self._new_capital(
                            state,
                            defender.id,
                            captured_tiles | {tile.id},
                        )
                    )

            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.BATTLE_WON if captured else EventType.BATTLE_LOST,
                    summary=(
                        f"Битва за тайл {tile.id}: "
                        f"фракция {attacker.id} {'победила' if captured else 'проиграла'}"
                    ),
                    tile_ids=(tile.id,),
                    faction_ids=(attacker.id, defender.id),
                    severity=min(1.0, gap),
                )
            )

            war = self._find_war(wars, attacker.id, defender.id)
            if war is None:
                war = War(
                    id=next_war_id,
                    attacker_id=attacker.id,
                    defender_id=defender.id,
                    started_year=ctx.year,
                )
                next_war_id += 1
                war_event = Event.war(
                    year=ctx.year,
                    attacker_id=attacker.id,
                    defender_id=defender.id,
                    tile_id=tile.id,
                )
                if boost is not None and boost.mana_spent > 0:
                    war_event = war_event.model_copy(
                        update={
                            "payload": {
                                **war_event.payload,
                                "mana_spent": boost.mana_spent,
                            }
                        }
                    )
                events.append(war_event)
            attacker_losses = attacker_loss if war.attacker_id == attacker.id else defender_loss
            defender_losses = defender_loss if war.attacker_id == attacker.id else attacker_loss
            wars[war.id] = war.model_copy(
                update={
                    "battles": war.battles + 1,
                    "attacker_losses": war.attacker_losses + attacker_losses,
                    "defender_losses": war.defender_losses + defender_losses,
                    "active": True,
                }
            )

        faction_updates = self._faction_updates(factions, working)
        return RuleOutcome(
            tile_updates=tuple(tile_updates.values()),
            faction_updates=faction_updates,
            events=tuple(events),
            wars=tuple(wars.values()),
        )

    @staticmethod
    def _occupy(tile: RegionData, attacker: Faction, ctx: StepContext) -> TileUpdate:
        """Формирует изменения захваченного тайла."""
        return TileUpdate(
            tile_id=tile.id,
            population=max(0, int(tile.population * (1.0 - ctx.rng.uniform(0.05, 0.1)))),
            happiness=max(0.0, tile.happiness - 10.0),
            unrest=min(100.0, tile.unrest + 20.0),
            fortification=tile.fortification * (1.0 - ctx.rng.uniform(0.25, 0.5)),
            army_presence=max(1, int(attacker.army_size * 0.05)),
            owner_id=attacker.id,
            set_owner=True,
        )

    @staticmethod
    def _new_capital(
        state: WorldState,
        defender_id: int,
        excluded: set[int],
    ) -> int | None:
        """Выбирает новую столицу из уцелевших тайлов фракции."""
        remaining = [
            tile
            for tile in state.map.tiles
            if tile.owner_id == defender_id and tile.id not in excluded and tile.is_land
        ]
        if not remaining:
            return None
        return min(remaining, key=lambda tile: (-tile.population, tile.id)).id

    @staticmethod
    def _faction_updates(
        original: dict[int, Faction],
        working: dict[int, Faction],
    ) -> tuple[FactionUpdate, ...]:
        """Собирает изменения фракций относительно исходного снимка."""
        updates: list[FactionUpdate] = []
        for faction_id, before in original.items():
            after = working[faction_id]
            changes: dict[str, object] = {}
            if after.army_size != before.army_size:
                changes["army_size"] = after.army_size
            if after.morale != before.morale:
                changes["morale"] = after.morale
            if after.treasury != before.treasury:
                changes["treasury"] = after.treasury
            if after.capital_tile_id != before.capital_tile_id:
                changes["capital_tile_id"] = after.capital_tile_id
            if changes:
                updates.append(FactionUpdate(faction_id=faction_id, changes=changes))
        return tuple(updates)

    @staticmethod
    def _find_war(wars: dict[int, War], first: int, second: int) -> War | None:
        """Ищет активную войну между двумя фракциями."""
        for war in wars.values():
            if not war.active:
                continue
            if {war.attacker_id, war.defender_id} == {first, second}:
                return war
        return None
