"""Сравнение двух снимков мира."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.state import WorldState


@dataclass(frozen=True)
class TileOwnershipChange:
    """Смена владельца тайла."""

    tile_id: int
    from_owner: int | None
    to_owner: int | None


@dataclass(frozen=True)
class Diff:
    """Разница между двумя снимками мира."""

    years: tuple[int, int]
    tiles_changed: int = 0
    population_delta: int = 0
    owners_changed: tuple[TileOwnershipChange, ...] = ()
    factions_added: tuple[int, ...] = ()
    factions_removed: tuple[int, ...] = ()
    events_added: int = 0

    @property
    def is_empty(self) -> bool:
        """Нет ли изменений между снимками."""
        return (
            self.tiles_changed == 0
            and self.population_delta == 0
            and not self.owners_changed
            and not self.factions_added
            and not self.factions_removed
            and self.events_added == 0
        )

    def to_markdown(self) -> str:
        """Сводка в виде markdown-таблиц."""
        lines = [
            f"## Изменения: {self.years[0]} → {self.years[1]}",
            "",
            "| Показатель | Значение |",
            "| --- | --- |",
            f"| Годы | {self.years[0]} → {self.years[1]} |",
            f"| Тайлы изменены | {self.tiles_changed} |",
            f"| Прирост населения | {self.population_delta:+d} |",
            f"| Смены владельцев | {len(self.owners_changed)} |",
            f"| Фракции добавлены | {', '.join(map(str, self.factions_added)) or '—'} |",
            f"| Фракции удалены | {', '.join(map(str, self.factions_removed)) or '—'} |",
            f"| События добавлены | {self.events_added} |",
        ]
        if self.is_empty:
            lines.extend(["", "Изменений нет."])
        if self.owners_changed:
            lines.extend(
                [
                    "",
                    "| Тайл | Было | Стало |",
                    "| --- | --- | --- |",
                ]
            )
            lines.extend(
                f"| {change.tile_id} | "
                f"{'—' if change.from_owner is None else change.from_owner} | "
                f"{'—' if change.to_owner is None else change.to_owner} |"
                for change in self.owners_changed
            )
        return "\n".join(lines)


def compute_diff(
    from_state: WorldState,
    from_chronicle: Chronicle,
    to_state: WorldState,
    to_chronicle: Chronicle,
) -> Diff:
    """Сравнивает два снимка по тайлам, фракциям и летописи.

    Карты разного размера сравниваются по общим идентификаторам тайлов;
    остальные тайлы просто не попадают в частичный diff.
    """
    old_tiles = {tile.id: tile for tile in from_state.map.tiles}
    new_tiles = {tile.id: tile for tile in to_state.map.tiles}
    common_ids = sorted(set(old_tiles) & set(new_tiles))

    tiles_changed = 0
    population_delta = 0
    owners_changed: list[TileOwnershipChange] = []
    for tile_id in common_ids:
        old = old_tiles[tile_id]
        new = new_tiles[tile_id]
        changed = False
        if old.owner_id != new.owner_id:
            owners_changed.append(
                TileOwnershipChange(
                    tile_id=tile_id,
                    from_owner=old.owner_id,
                    to_owner=new.owner_id,
                )
            )
            changed = True
        if old.population != new.population:
            population_delta += new.population - old.population
            changed = True
        if changed:
            tiles_changed += 1

    old_factions = {faction.id for faction in from_state.factions}
    new_factions = {faction.id for faction in to_state.factions}
    events_added = _count_new_events(from_chronicle, to_chronicle)

    return Diff(
        years=(from_state.year, to_state.year),
        tiles_changed=tiles_changed,
        population_delta=population_delta,
        owners_changed=tuple(owners_changed),
        factions_added=tuple(sorted(new_factions - old_factions)),
        factions_removed=tuple(sorted(old_factions - new_factions)),
        events_added=events_added,
    )


def _count_new_events(from_chronicle: Chronicle, to_chronicle: Chronicle) -> int:
    """Считает события, которых не было в исходной летописи."""
    old_counts = Counter(_event_key(event) for event in from_chronicle.all_events())
    added = 0
    for event in to_chronicle.all_events():
        key = _event_key(event)
        if old_counts[key] > 0:
            old_counts[key] -= 1
        else:
            added += 1
    return added


def _event_key(event: Event) -> tuple[object, ...]:
    """Ключ события для сравнения летописей."""
    return (
        event.year,
        event.type,
        event.tile_ids,
        event.faction_ids,
        event.severity,
        event.summary,
    )
