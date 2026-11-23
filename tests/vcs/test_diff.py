"""Тесты сравнения снимков VCS."""

from __future__ import annotations

from pathlib import Path

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.vcs.diff import Diff, TileOwnershipChange
from worldsim.vcs.repo import RepositoryError, WorldRepo


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int = 0,
) -> Faction:
    """Создаёт фракцию для тестов diff."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
    )


def make_state(
    *,
    size: int = 4,
    year: int = 0,
    factions: tuple[Faction, ...] = (),
    owners: dict[int, int] | None = None,
    populations: dict[int, int] | None = None,
) -> WorldState:
    """Создаёт карту с заданными владельцами и населением."""
    tiles: list[RegionData] = []
    for index in range(size * size):
        data: dict[str, object] = {
            "id": index,
            "x": index % size,
            "y": index // size,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": (populations or {}).get(index, 10),
            "population_capacity": 1_000,
        }
        if owners is not None and index in owners:
            data["owner_id"] = owners[index]
        tiles.append(RegionData.model_validate(data))
    config = WorldConfig(seed=1, size=size, initial_factions=len(factions))
    return WorldState(
        config=config,
        year=year,
        map=WorldMap(size=size, tiles=tuple(tiles)),
        factions=factions,
    )


def test_identical_snapshots_have_empty_diff(tmp_path: Path) -> None:
    """Без изменений diff пустой."""
    repo = WorldRepo(tmp_path)
    state = make_state(factions=(make_faction(),), owners={0: 0})
    commit = repo.commit(state, "мир")

    diff = repo.diff(commit.id, "main")

    assert diff.is_empty
    assert diff.tiles_changed == 0
    assert diff.population_delta == 0
    assert diff.owners_changed == ()
    assert diff.events_added == 0


def test_owner_and_population_changes_are_visible(tmp_path: Path) -> None:
    """Смена владельца и рост населения попадают в diff."""
    repo = WorldRepo(tmp_path)
    first = make_faction(0)
    second = make_faction(1, name="Орда", color="#445566", capital=2)
    from_state = make_state(year=0, factions=(first, second), owners={0: 0, 1: 1, 2: 1})
    to_state = make_state(
        year=1,
        factions=(first, second),
        owners={0: 0, 1: 0, 2: 1},
        populations={0: 30},
    )
    to_chronicle = Chronicle()
    to_chronicle.add(Event.expansion(year=1, faction_id=0, tile_id=1))

    first_commit = repo.commit(from_state, "было")
    second_commit = repo.commit(to_state, "стало", chronicle=to_chronicle)
    diff = repo.diff(first_commit.id, second_commit.id)

    assert diff.tiles_changed == 2
    assert diff.population_delta == 20
    assert diff.owners_changed == (TileOwnershipChange(1, 1, 0),)
    assert diff.events_added == 1


def test_markdown_contains_tables(tmp_path: Path) -> None:
    """Markdown-сводка содержит таблицу показателей и смен владельцев."""
    repo = WorldRepo(tmp_path)
    first = make_faction(0)
    second = make_faction(1, name="Орда", color="#445566", capital=2)
    repo.commit(
        make_state(year=0, factions=(first, second), owners={0: 0, 1: 1, 2: 1}),
        "было",
    )
    repo.commit(
        make_state(year=1, factions=(first, second), owners={0: 0, 1: 0, 2: 1}),
        "стало",
    )

    markdown = repo.diff(repo.log()[1].id, "main").to_markdown()

    assert "| Показатель | Значение |" in markdown
    assert "| Тайл | Было | Стало |" in markdown
    assert "| 1 | 1 | 0 |" in markdown
    assert "Изменений нет" not in markdown


def test_different_map_sizes_do_not_fail(tmp_path: Path) -> None:
    """Карты разного размера дают частичный diff без падения."""
    repo = WorldRepo(tmp_path)
    faction = make_faction()
    small = repo.commit(make_state(size=4, factions=(faction,), owners={0: 0}), "малая")
    large = repo.commit(make_state(size=6, factions=(faction,), owners={0: 0}), "большая")

    diff = repo.diff(small.id, large.id)

    assert isinstance(diff, Diff)
    assert diff.tiles_changed >= 0
    assert diff.years == (0, 0)


def test_factions_added_and_removed(tmp_path: Path) -> None:
    """Добавленные и удалённые фракции видны в diff."""
    repo = WorldRepo(tmp_path)
    first = make_faction(0)
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    base = repo.commit(make_state(factions=(first,), owners={0: 0}), "одна")
    extended = repo.commit(
        make_state(factions=(first, second), owners={0: 0, 1: 1}),
        "две",
    )

    added = repo.diff(base.id, extended.id)
    removed = repo.diff(extended.id, base.id)

    assert added.factions_added == (1,)
    assert added.factions_removed == ()
    assert removed.factions_removed == (1,)


def test_events_added_count(tmp_path: Path) -> None:
    """Новые события летописи считаются отдельно от изменений тайлов."""
    repo = WorldRepo(tmp_path)
    state = make_state(factions=(make_faction(),), owners={0: 0})
    first = repo.commit(state, "без событий")
    chronicle = Chronicle()
    chronicle.add(Event.expansion(year=1, faction_id=0, tile_id=0))
    chronicle.add(Event.expansion(year=2, faction_id=0, tile_id=1))
    second = repo.commit(state, "с событиями", chronicle=chronicle)

    diff = repo.diff(first.id, second.id)

    assert diff.tiles_changed == 0
    assert diff.events_added == 2
    assert diff.is_empty is False


def test_unknown_ref_is_rejected(tmp_path: Path) -> None:
    """Неизвестная ссылка в diff даёт ошибку."""
    repo = WorldRepo(tmp_path)
    commit = repo.commit(make_state(factions=(make_faction(),), owners={0: 0}), "мир")

    with pytest.raises(RepositoryError):
        repo.diff(commit.id, "нет-такого")
