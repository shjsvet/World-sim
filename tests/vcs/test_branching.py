"""Тесты ветвления и альтернативных реальностей."""

from __future__ import annotations

from pathlib import Path

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.generator.world import create_world
from worldsim.vcs.repo import RepositoryError, WorldRepo

pytestmark = pytest.mark.integration


def make_world(seed: int = 1, size: int = 16, factions: int = 1) -> WorldState:
    """Создаёт мир для сценариев ветвления."""
    return create_world(WorldConfig(seed=seed, size=size, initial_factions=factions))


def run_years(state: WorldState, years: int) -> WorldState:
    """Прогоняет мир с правилом роста населения."""
    chronicle = Chronicle()
    engine = SimulationEngine([PopulationGrowthRule()], chronicle, initial_state=state)
    return engine.run(years)


def test_branch_from_middle_of_history(tmp_path: Path) -> None:
    """Ветка создаётся от середины истории и восстанавливает тот снимок."""
    repo = WorldRepo(tmp_path)
    first = repo.commit(make_world(seed=1).evolve(year=0), "год 0")
    second = repo.commit(make_world(seed=1).evolve(year=1), "год 1")

    repo.create_branch("feature", from_ref=first.id)
    state, _ = repo.checkout_branch("feature")

    assert state.snapshot_hash() == first.snapshot_hash
    assert repo.current_branch() == "feature"
    assert repo.list_branches() == {"feature": first.id, "main": second.id}


def test_branch_commits_do_not_change_main(tmp_path: Path) -> None:
    """Коммиты в ветке не двигают основную ветку."""
    repo = WorldRepo(tmp_path)
    first = repo.commit(make_world(seed=1).evolve(year=0), "год 0")
    second = repo.commit(make_world(seed=1).evolve(year=1), "год 1")
    repo.create_branch("feature", from_ref=first.id)
    repo.checkout_branch("feature")

    feature_commit = repo.commit(make_world(seed=2), "фича", branch="feature")

    assert repo.list_branches()["main"] == second.id
    assert repo.list_branches()["feature"] == feature_commit.id
    assert repo.log("main") == [second, first]
    assert repo.log("feature") == [feature_commit, first]


def test_checkout_branch_returns_its_head(tmp_path: Path) -> None:
    """Checkout ветки возвращает её HEAD, а не общий."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_world(seed=1), "база")
    repo.create_branch("feature", from_ref=base.id)
    repo.checkout_branch("feature")
    feature_commit = repo.commit(make_world(seed=2), "фича", branch="feature")

    repo.checkout_branch("main")
    assert repo.head() == base

    state, _ = repo.checkout_branch("feature")
    assert state.snapshot_hash() == feature_commit.snapshot_hash


def test_two_branches_with_different_parameters_differ(tmp_path: Path) -> None:
    """Одинаковый сид, разные параметры — разные итоги."""
    repo = WorldRepo(tmp_path)
    base = make_world(seed=7, size=16, factions=1)
    base_commit = repo.commit(base, "база")

    repo.create_branch("slow", from_ref=base_commit.id)
    repo.checkout_branch("slow")
    slow_after = run_years(
        base.evolve(config=base.config.evolve(growth_rate=0.01)),
        10,
    )
    repo.commit(slow_after, "медленный рост", branch="slow")

    repo.create_branch("fast", from_ref=base_commit.id)
    repo.checkout_branch("fast")
    fast_after = run_years(
        base.evolve(config=base.config.evolve(growth_rate=0.1)),
        10,
    )
    repo.commit(fast_after, "быстрый рост", branch="fast")

    assert slow_after.snapshot_hash() != fast_after.snapshot_hash()


def test_branch_names_are_validated(tmp_path: Path) -> None:
    """Недопустимые и занятые имена веток отклоняются."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_world(), "база")

    for name in ("bad name", "bad/name", "", "имя"):
        with pytest.raises(RepositoryError):
            repo.create_branch(name, from_ref=base.id)

    repo.create_branch("feature", from_ref=base.id)
    with pytest.raises(RepositoryError):
        repo.create_branch("feature", from_ref=base.id)


def test_unknown_branch_checkout_is_rejected(tmp_path: Path) -> None:
    """Checkout несуществующей ветки даёт ошибку."""
    repo = WorldRepo(tmp_path)
    repo.commit(make_world(), "база")

    with pytest.raises(RepositoryError):
        repo.checkout_branch("missing")


def test_alternate_reality_scenario(tmp_path: Path) -> None:
    """Сценарий: тег на историю → другая агрессия → ветка alt."""
    repo = WorldRepo(tmp_path)
    base = make_world(seed=11, size=16, factions=2)
    chronicle = Chronicle()
    engine = SimulationEngine([PopulationGrowthRule()], chronicle, initial_state=base)
    state100 = engine.run(10)
    base_commit = repo.commit(state100, "год 10", chronicle=chronicle)
    repo.tag("year_10", base_commit.id)

    restored, restored_chronicle = repo.checkout("year_10")
    assert restored.snapshot_hash() == state100.snapshot_hash()
    assert restored_chronicle.to_json() == chronicle.to_json()

    alt_state = restored.evolve(config=restored.config.evolve(aggression=0.9))
    alt_after = run_years(alt_state, 10)
    alt_commit = repo.commit(alt_after, "alt: высокая агрессия", branch="alt")

    assert alt_commit.parent_id == base_commit.id
    assert repo.list_branches()["main"] == base_commit.id
    assert repo.list_branches()["alt"] == alt_commit.id
    assert repo.current_branch() == "alt"
    assert repo.log("alt") == [alt_commit, base_commit]


def test_tags_are_validated(tmp_path: Path) -> None:
    """Теги не допускают пустых имён и повторов."""
    repo = WorldRepo(tmp_path)
    commit = repo.commit(make_world(), "база")

    repo.tag("v1", commit.id)
    with pytest.raises(RepositoryError):
        repo.tag("v1", commit.id)
    with pytest.raises(RepositoryError):
        repo.tag("плохое имя", commit.id)


def test_tag_on_empty_repository_is_rejected(tmp_path: Path) -> None:
    """Без коммитов ставить тег не на что."""
    repo = WorldRepo(tmp_path)

    with pytest.raises(RepositoryError):
        repo.tag("v1")


def test_merge_is_not_implemented(tmp_path: Path) -> None:
    """Слияние веток не поддерживается и это задокументировано."""
    repo = WorldRepo(tmp_path)

    assert not hasattr(repo, "merge")
    assert WorldRepo.__doc__ is not None
    assert "Слияние" in WorldRepo.__doc__


def test_log_shows_fork(tmp_path: Path) -> None:
    """История показывает развилку веток."""
    repo = WorldRepo(tmp_path)
    first = repo.commit(make_world(seed=1).evolve(year=0), "год 0")
    repo.commit(make_world(seed=1).evolve(year=1), "год 1")
    repo.create_branch("feature", from_ref=first.id)
    repo.checkout_branch("feature")
    feature_commit = repo.commit(make_world(seed=2), "фича", branch="feature")

    main_log = repo.log("main")
    feature_log = repo.log("feature")

    assert main_log[-1] == first
    assert feature_log == [feature_commit, first]
    assert main_log[0].id != feature_log[0].id


def test_three_branches_and_two_forks(tmp_path: Path) -> None:
    """Полный сценарий: три ветки и две развилки."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_world(seed=1).evolve(year=0), "основа")

    repo.create_branch("feature", from_ref=base.id)
    repo.checkout_branch("feature")
    feature = repo.commit(make_world(seed=2).evolve(year=1), "фича", branch="feature")

    repo.checkout_branch("main")
    main = repo.commit(make_world(seed=3).evolve(year=2), "основа+", branch="main")

    repo.create_branch("alt", from_ref=feature.id)
    repo.checkout_branch("alt")
    alt = repo.commit(make_world(seed=4).evolve(year=3), "альтернатива", branch="alt")

    assert set(repo.list_branches()) == {"main", "feature", "alt"}
    assert repo.list_branches()["main"] == main.id
    assert repo.log("main") == [main, base]
    assert repo.log("feature") == [feature, base]
    assert repo.log("alt") == [alt, feature, base]
    assert alt.parent_id == feature.id


def test_commit_after_checkout_of_old_commit(tmp_path: Path) -> None:
    """После checkout старого коммита можно ветвиться от него."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_world(seed=1).evolve(year=0), "основа")
    main = repo.commit(make_world(seed=2).evolve(year=1), "основная", branch="main")

    repo.checkout(base.id)
    repo.create_branch("hotfix")
    repo.checkout_branch("hotfix")
    fix = repo.commit(make_world(seed=3).evolve(year=2), "hotfix", branch="hotfix")

    assert fix.parent_id == base.id
    assert repo.list_branches()["main"] == main.id
    assert repo.log("hotfix") == [fix, base]


def test_main_branch_stays_unchanged(tmp_path: Path) -> None:
    """Коммиты в других ветках не двигают основную."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_world(seed=1).evolve(year=0), "основа")
    repo.create_branch("feature", from_ref=base.id)
    repo.checkout_branch("feature")
    repo.commit(make_world(seed=2), "фича", branch="feature")
    repo.create_branch("alt", from_ref=base.id)
    repo.checkout_branch("alt")
    repo.commit(make_world(seed=3), "альтернатива", branch="alt")

    assert repo.list_branches()["main"] == base.id
    assert repo.log("main") == [base]
    repo.checkout_branch("main")
    restored, _ = repo.checkout("main")
    assert restored.snapshot_hash() == base.snapshot_hash


def test_checkout_restores_state_and_chronicle_exactly(tmp_path: Path) -> None:
    """Свойство: checkout возвращает тот же снимок и ту же летопись."""
    repo = WorldRepo(tmp_path)
    chronicles: dict[str, Chronicle] = {}
    commits = []
    for year in range(3):
        chronicle = Chronicle()
        chronicle.add(Event.expansion(year=year, faction_id=0, tile_id=year))
        commit = repo.commit(
            make_world(seed=1).evolve(year=year),
            f"год {year}",
            chronicle=chronicle,
        )
        commits.append(commit)
        chronicles[commit.id] = chronicle

    for commit in commits:
        state, chronicle = repo.checkout(commit.id)
        assert state.snapshot_hash() == commit.snapshot_hash
        assert chronicle.to_json() == chronicles[commit.id].to_json()


def test_damaged_object_can_be_restored(tmp_path: Path) -> None:
    """Повреждённый объект даёт ошибку, после восстановления файла — работает."""
    repo = WorldRepo(tmp_path)
    commit = repo.commit(make_world(seed=1), "мир")
    object_path = repo.objects_dir / f"{commit.id}.json"
    original = object_path.read_text(encoding="utf-8")

    object_path.write_text("{ это не json", encoding="utf-8")
    with pytest.raises(RepositoryError):
        repo.checkout(commit.id)

    object_path.write_text(original, encoding="utf-8")
    restored, _ = repo.checkout(commit.id)
    assert restored.snapshot_hash() == commit.snapshot_hash
