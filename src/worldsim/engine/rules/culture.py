"""Правила культуры и религии."""

from __future__ import annotations

from worldsim.core.culture import Culture, Religion
from worldsim.core.events import Event, EventType
from worldsim.core.faction import culture_conflict_factor
from worldsim.core.state import WorldState
from worldsim.engine.rules import RuleOutcome, StepContext, TileUpdate

ASSIMILATION_MIN = 0.05
ASSIMILATION_MAX = 0.10
ASSIMILATION_DECAY = 0.05
CLASH_THRESHOLD = 50.0
RIOT_UNREST = 60.0


class AssimilationRule:
    """Ассимиляция населения на захваченных тайлах.

    Если культура населения отличается от культуры владельца, ассимиляция
    растёт при счастье выше 50 и падает при войне или беспорядках. На
    отметке 1.0 культура тайла меняется на культуру владельца.
    """

    name = "assimilation"
    priority = 17

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Обновляет ассимиляцию и при необходимости меняет культуру тайла."""
        factions = {faction.id: faction for faction in state.factions}
        culture_ids = {culture.name.casefold(): culture.id for culture in state.cultures}
        updates: list[TileUpdate] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land or tile.culture is None:
                continue
            owner = factions.get(tile.owner_id)
            if owner is None:
                continue
            if tile.culture.casefold() == owner.culture.casefold():
                if tile.assimilation > 0.0:
                    updates.append(TileUpdate(tile_id=tile.id, assimilation=0.0))
                continue

            stats = ctx.stats.get(owner.id)
            at_war = stats is not None and bool(stats.enemies)
            if at_war or tile.unrest > RIOT_UNREST:
                delta = -ASSIMILATION_DECAY
            elif tile.happiness > 50.0:
                delta = ctx.rng.uniform(ASSIMILATION_MIN, ASSIMILATION_MAX)
            else:
                delta = 0.0
            if delta == 0.0:
                continue

            value = max(0.0, min(1.0, tile.assimilation + delta))
            if value >= 1.0:
                updates.append(
                    TileUpdate(
                        tile_id=tile.id,
                        culture=owner.culture,
                        culture_id=culture_ids.get(owner.culture.casefold()),
                        assimilation=0.0,
                    )
                )
            elif value != tile.assimilation:
                updates.append(TileUpdate(tile_id=tile.id, assimilation=value))
        return RuleOutcome(tile_updates=tuple(updates))


class CultureClashRule:
    """Культурные столкновения на границе разных культур.

    Напряжение растёт при соседстве тайлов с разными культурами; чем меньше
    общих признаков у культур и чем выше ``culture_conflict_factor``, тем
    вероятнее конфликт с потерями населения.
    """

    name = "culture_clash"
    priority = 18

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Накапливает напряжение и порождает ``CULTURE_CLASH``."""
        factions = {faction.id: faction for faction in state.factions}
        cultures = {culture.name.casefold(): culture for culture in state.cultures}
        updates: list[TileUpdate] = []
        events: list[Event] = []

        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land or tile.culture is None:
                continue
            owner = factions.get(tile.owner_id)
            if owner is None:
                continue

            frontier: list[tuple[int, str]] = []
            for neighbor in state.map.neighbors(tile.x, tile.y):
                if neighbor.owner_id is None or neighbor.owner_id == tile.owner_id:
                    continue
                if neighbor.culture is None:
                    continue
                if neighbor.culture.casefold() != tile.culture.casefold():
                    frontier.append((neighbor.owner_id, neighbor.culture))

            if not frontier:
                if tile.cultural_tension > 0.0:
                    updates.append(
                        TileUpdate(
                            tile_id=tile.id,
                            cultural_tension=max(0.0, tile.cultural_tension - 5.0),
                        )
                    )
                continue

            other_owner_id, other_culture = frontier[0]
            other_owner = factions.get(other_owner_id)
            if other_owner is None:
                continue

            penalty = 1.0 - _trait_similarity(cultures, tile.culture, other_culture)
            tension = min(100.0, tile.cultural_tension + 5.0 + 10.0 * penalty)
            if tension >= CLASH_THRESHOLD:
                conflict = culture_conflict_factor(owner, other_owner)
                probability = min(0.5, 0.1 + 0.3 * conflict * tension / 100.0)
                if ctx.rng.chance(probability):
                    losses = ctx.rng.uniform(0.05, 0.15)
                    updates.append(
                        TileUpdate(
                            tile_id=tile.id,
                            population=max(0, int(tile.population * (1.0 - losses))),
                            fertility=max(0.0, tile.fertility - 2.0),
                            cultural_tension=max(0.0, tension - 30.0),
                        )
                    )
                    events.append(
                        Event(
                            id=0,
                            year=ctx.year,
                            type=EventType.CULTURE_CLASH,
                            summary=(
                                f"Культурный конфликт в тайле {tile.id}: "
                                f"{tile.culture} против {other_culture}"
                            ),
                            tile_ids=(tile.id,),
                            faction_ids=(tile.owner_id, other_owner_id),
                            severity=losses,
                        )
                    )
                    continue

            updates.append(TileUpdate(tile_id=tile.id, cultural_tension=tension))
        return RuleOutcome(tile_updates=tuple(updates), events=tuple(events))


class ConversionRule:
    """Распространение религии с высоким рвением на соседние тайлы."""

    name = "conversion"
    priority = 19

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Меняет религию тайла под влиянием соседа с большим ``zeal``."""
        religions: dict[int, Religion] = {religion.id: religion for religion in state.religions}
        updates: list[TileUpdate] = []
        for tile in state.map.tiles:
            if tile.owner_id is None or not tile.is_land or tile.religion_id is None:
                continue
            own = religions.get(tile.religion_id)
            if own is None:
                continue
            best: Religion | None = None
            for neighbor in state.map.neighbors(tile.x, tile.y):
                if neighbor.religion_id is None or neighbor.religion_id == own.id:
                    continue
                candidate = religions.get(neighbor.religion_id)
                if candidate is None:
                    continue
                if best is None or candidate.zeal > best.zeal:
                    best = candidate
            if best is None or best.zeal <= own.zeal + 0.05:
                continue
            if ctx.rng.chance(min(1.0, (best.zeal - own.zeal) * 0.8)):
                updates.append(TileUpdate(tile_id=tile.id, religion_id=best.id))
        return RuleOutcome(tile_updates=tuple(updates))


def _trait_similarity(
    cultures: dict[str, Culture],
    left: str,
    right: str,
) -> float:
    """Доля общих признаков культур (0 — разные, 1 — совпадают)."""
    left_culture = cultures.get(left.casefold())
    right_culture = cultures.get(right.casefold())
    if left_culture is None or right_culture is None:
        return 0.0
    left_traits = set(left_culture.traits)
    right_traits = set(right_culture.traits)
    union = left_traits | right_traits
    if not union:
        return 1.0
    return len(left_traits & right_traits) / len(union)
