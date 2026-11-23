"""Тесты UI-обёрток истории и таймлайна."""

from __future__ import annotations

from pathlib import Path

from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.generator.world import create_world
from worldsim.ui.figures import timeline_figure
from worldsim.ui.history import (
    checkout_snapshot,
    commit_world,
    default_repo_path,
    diff_to_parent,
    open_repo,
    run_alternative,
)
from worldsim.vcs.repo import WorldRepo


def make_state(year: int = 0, seed: int = 1) -> WorldState:
    """Создаёт небольшой мир нужного года."""
    return create_world(WorldConfig(seed=seed, size=8)).evolve(year=year)


def test_timeline_builds_nodes_and_edges(tmp_path: Path) -> None:
    """Таймлайн строит узел на коммит и ребро родитель → ребёнок."""
    repo = WorldRepo(tmp_path)
    repo.commit(make_state(year=0), "год 0")
    repo.commit(make_state(year=1), "год 1")

    figure = timeline_figure(repo.log())

    edge_trace = figure.data[0]
    node_trace = figure.data[1]
    assert list(node_trace.x) == [0.0, 1.0]
    assert len(node_trace.y) == 2
    assert all("год" in text for text in node_trace.text)
    assert list(edge_trace.x) == [0.0, 1.0, None]
    assert list(edge_trace.y) == [0.0, 0.0, None]


def test_timeline_shows_fork(tmp_path: Path) -> None:
    """Развилка отображается двумя ветками на оси Y."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_state(year=0), "база")
    repo.create_branch("feature", from_ref=base.id)
    repo.checkout_branch("feature")
    repo.commit(make_state(year=5, seed=2), "ветка", branch="feature")

    figure = timeline_figure(repo.log("feature"))

    node_trace = figure.data[-1]
    assert len(node_trace.x) == 2
    assert len(set(node_trace.y)) == 2
    assert figure.layout.yaxis.ticktext == ("feature", "main")


def test_empty_timeline_does_not_fail() -> None:
    """Пустая история даёт пустую фигуру."""
    figure = timeline_figure([])

    node_trace = figure.data[0]
    assert list(node_trace.x) == []
    assert list(node_trace.y) == []


def test_checkout_wrapper_returns_snapshot(tmp_path: Path) -> None:
    """UI-обёртка checkout возвращает состояние коммита."""
    repo = WorldRepo(tmp_path)
    commit = repo.commit(make_state(year=3), "мир")

    state, chronicle = checkout_snapshot(repo, commit.id)

    assert state.snapshot_hash() == commit.snapshot_hash
    assert isinstance(chronicle, Chronicle)


def test_diff_to_parent_and_root(tmp_path: Path) -> None:
    """Diff к родителю считается, у корневого коммита он пустой."""
    repo = WorldRepo(tmp_path)
    root = repo.commit(make_state(year=0), "корень")
    repo.commit(make_state(year=1), "второй")

    root_diff = diff_to_parent(repo, root)
    child_diff = diff_to_parent(repo, repo.log()[0])

    assert root_diff.is_empty
    assert child_diff.years == (0, 1)


def test_commit_world_wrapper(tmp_path: Path) -> None:
    """Коммит текущего мира использует переданную летопись."""
    repo = WorldRepo(tmp_path)
    state = make_state(year=7)

    commit = commit_world(repo, state, Chronicle(), "год 7")

    assert commit.year == 7
    assert repo.head() == commit


def test_run_alternative_creates_branch_and_diff(tmp_path: Path) -> None:
    """Альтернатива создаёт ветку, прогоняет годы и считает diff."""
    repo = WorldRepo(tmp_path)
    base = repo.commit(make_state(year=0, seed=5), "база")

    commit, diff = run_alternative(
        repo,
        base.id,
        "alt",
        aggression=0.9,
        years=5,
        rules=[PopulationGrowthRule()],
        message="alt: высокая агрессия",
    )

    assert commit.parent_id == base.id
    assert commit.year == 5
    assert commit.message == "alt: высокая агрессия"
    assert repo.list_branches()["alt"] == commit.id
    assert diff.years == (0, 5)
    assert diff.tiles_changed >= 0


def test_default_repo_path(tmp_path: Path) -> None:
    """Путь по умолчанию — ``<корень>/.worldsim``."""
    assert default_repo_path(tmp_path) == tmp_path / ".worldsim"
    assert open_repo(tmp_path).root == tmp_path / ".worldsim"
