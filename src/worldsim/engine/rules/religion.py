"""Изобретение религий ИИ-правителями и их распространение."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction
from worldsim.core.culture import Religion
from worldsim.core.diplomacy import War
from worldsim.core.events import Event, EventType
from worldsim.core.faction import Faction
from worldsim.core.geography import RegionData
from worldsim.core.state import WorldState
from worldsim.engine.rules import RuleOutcome, StepContext, TileUpdate

HIGH_ZEAL = 0.8
ADOPTION_ZEAL = 0.5


class ReligionFoundingRule:
    """Создаёт религию по решению ИИ и распространяет её."""

    name = "religion_founding"
    priority = 16

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Обрабатывает ``FOUND_RELIGION``, принятие и священную войну."""
        religions = list(state.religions)
        wars = list(state.wars)
        tile_updates: list[TileUpdate] = []
        events: list[Event] = []
        wars_changed = False
        next_religion_id = max((religion.id for religion in religions), default=-1) + 1
        next_war_id = max((war.id for war in wars), default=-1) + 1

        for command in ctx.ai_decisions:
            if command.decision.action is not RulerAction.FOUND_RELIGION:
                continue
            faction = next(
                (item for item in state.factions if item.id == command.faction_id),
                None,
            )
            if faction is None:
                continue
            culture_id = _culture_id(state, faction)
            if culture_id is None:
                continue
            name = _unique_name(
                command.decision.message.strip() or f"Вера {faction.culture}",
                religions,
            )
            religion = Religion(
                id=next_religion_id,
                name=name,
                culture_id=culture_id,
                zeal=max(0.1, min(1.0, command.decision.confidence)),
            )
            religions.append(religion)
            next_religion_id += 1

            owned = [tile for tile in state.map.tiles if tile.owner_id == faction.id]
            for tile in owned:
                tile_updates.append(TileUpdate(tile_id=tile.id, religion_id=religion.id))
            events.append(
                Event(
                    id=0,
                    year=ctx.year,
                    type=EventType.CUSTOM,
                    summary=(f"Фракция {faction.id} основала религию «{religion.name}»"),
                    faction_ids=(faction.id,),
                    severity=religion.zeal,
                )
            )

            neighbours = _neighbour_owners(state, faction.id)
            for neighbour_id, border_tile in neighbours:
                if religion.zeal >= HIGH_ZEAL:
                    if _has_active_conflict(state, faction.id, neighbour_id):
                        continue
                    wars.append(
                        War(
                            id=next_war_id,
                            attacker_id=faction.id,
                            defender_id=neighbour_id,
                            started_year=ctx.year,
                            active=True,
                        )
                    )
                    next_war_id += 1
                    wars_changed = True
                    events.append(
                        Event(
                            id=0,
                            year=ctx.year,
                            type=EventType.WAR,
                            summary=(
                                f"Священная война: фракция {faction.id} "
                                f"против {neighbour_id} за веру «{religion.name}»"
                            ),
                            tile_ids=(border_tile.id,),
                            faction_ids=(faction.id, neighbour_id),
                            severity=religion.zeal,
                        )
                    )
                elif religion.zeal >= ADOPTION_ZEAL:
                    tile_updates.append(
                        TileUpdate(
                            tile_id=border_tile.id,
                            religion_id=religion.id,
                        )
                    )
                    events.append(
                        Event(
                            id=0,
                            year=ctx.year,
                            type=EventType.CUSTOM,
                            summary=(f"Тайл {border_tile.id} принял веру «{religion.name}»"),
                            tile_ids=(border_tile.id,),
                            faction_ids=(faction.id, neighbour_id),
                            severity=0.4,
                        )
                    )

        return RuleOutcome(
            tile_updates=tuple(tile_updates),
            events=tuple(events),
            wars=tuple(wars) if wars_changed else None,
            religions=tuple(religions),
        )


def _culture_id(state: WorldState, faction: Faction) -> int | None:
    """Находит культуру фракции по имени."""
    for culture in state.cultures:
        if culture.name.casefold() == faction.culture.casefold():
            return culture.id
    return None


def _unique_name(name: str, religions: list[Religion]) -> str:
    """Делает имя религии уникальным и ограничивает длину."""
    base = name[:64]
    used = {religion.name.casefold() for religion in religions}
    if base.casefold() not in used:
        return base
    for index in range(2, 100):
        suffix = f" {index}"
        candidate = f"{base[: 64 - len(suffix)]}{suffix}"
        if candidate.casefold() not in used:
            return candidate
    return base[:60] + " X"


def _neighbour_owners(
    state: WorldState,
    faction_id: int,
) -> list[tuple[int, RegionData]]:
    """Возвращает соседние фракции и первый пограничный тайл."""
    found: dict[int, RegionData] = {}
    for tile in state.map.tiles:
        if tile.owner_id != faction_id:
            continue
        for neighbor in state.map.neighbors(tile.x, tile.y):
            if neighbor.owner_id is None or neighbor.owner_id == faction_id:
                continue
            found.setdefault(neighbor.owner_id, neighbor)
    return sorted(found.items(), key=lambda item: item[0])


def _has_active_conflict(state: WorldState, first_id: int, second_id: int) -> bool:
    """Проверяет активную войну или перемирие."""
    for war in state.wars:
        if {war.attacker_id, war.defender_id} != {first_id, second_id}:
            continue
        if war.active:
            return True
        if war.truce_until_year is not None and war.truce_until_year >= state.year:
            return True
    return False
