"""Тесты репозитория версий мира."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.world import create_world
from worldsim.vcs.repo import Repository
from worldsim.vcs.snapshot import Snapshot


def make_state(year: int = 0, seed: int = 1) -> WorldState:
    """Создаёт небольшой мир нужного года."""
    state = create_world(WorldConfig(seed=seed, size=8))
    return state.evolve(year=year)


def test_new_repository_has_main_branch() -> None:
    """Пустой репозиторий стоит на ветке main без коммитов."""
    repo = Repository()

    assert repo.branch == "main"
    assert repo.head is None
    assert repo.log() == ()
    assert repo.branches() == {"main": None}


def test_commit_creates_snapshot() -> None:
    """Коммит сохраняет снимок и становится HEAD."""
    repo = Repository()
    state = make_state()

    snapshot = repo.commit(state, "первый мир", author="тестер")

    assert snapshot.hash == state.snapshot_hash()
    assert snapshot.parent_hash is None
    assert snapshot.message == "первый мир"
    assert snapshot.author == "тестер"
    assert snapshot.created_at_utc.tzinfo is UTC
    assert repo.head is snapshot
    assert repo.branches()["main"] == snapshot.hash


def test_history_links_parents() -> None:
    """История ведёт от нового коммита к старому."""
    repo = Repository()
    first = repo.commit(make_state(year=0), "год 0")
    second = repo.commit(make_state(year=1), "год 1")

    assert second.parent_hash == first.hash
    assert repo.log() == (second, first)


def test_same_state_is_idempotent() -> None:
    """Повторный коммит того же состояния не создаёт новый объект."""
    repo = Repository()
    state = make_state()

    first = repo.commit(state, "мир")
    second = repo.commit(state, "мир снова")

    assert first is second
    assert len(repo.objects) == 1
    assert repo.branches()["main"] == first.hash


def test_branching_and_switching() -> None:
    """Ветка создаётся от HEAD, а переключение возвращает указатели."""
    repo = Repository()
    base = repo.commit(make_state(year=0), "база")

    repo.branch_create("feature")
    feature_commit = repo.commit(make_state(year=1), "фича")

    assert repo.branch == "feature"
    assert repo.branches() == {"main": base.hash, "feature": feature_commit.hash}

    repo.switch_branch("main")
    assert repo.branch == "main"
    assert repo.head is base

    main_commit = repo.commit(make_state(year=2), "основа")
    assert repo.branches()["main"] == main_commit.hash
    assert repo.branches()["feature"] == feature_commit.hash


def test_detached_checkout_and_commit() -> None:
    """Отсоединённый HEAD позволяет коммитить, не двигая ветку."""
    repo = Repository()
    first = repo.commit(make_state(year=0), "первый")
    repo.commit(make_state(year=1), "второй")
    main_tip = repo.branches()["main"]

    checked_out = repo.checkout(first.hash)

    assert checked_out is first
    assert repo.branch is None
    detached = repo.commit(make_state(year=2), "ответвление")
    assert detached.parent_hash == first.hash
    assert repo.branch is None
    assert repo.branches()["main"] == main_tip


def test_tags() -> None:
    """Теги ставятся на текущий снимок и на указанный хеш."""
    repo = Repository()
    first = repo.commit(make_state(year=0), "первый")
    second = repo.commit(make_state(year=1), "второй")

    tagged = repo.tag("v1")
    assert tagged.hash == second.hash
    assert tagged.tags == ("v1",)

    older = repo.tag("v0", first.hash)
    assert older.tags == ("v0",)
    assert repo.objects[second.hash].tags == ("v1",)


def test_unknown_objects_are_rejected() -> None:
    """Неизвестные ветки, снимки и теги отклоняются."""
    repo = Repository()

    with pytest.raises(KeyError):
        repo.checkout("нет-такого")
    with pytest.raises(KeyError):
        repo.tag("v1")
    with pytest.raises(KeyError):
        repo.switch_branch("нет-такой")

    repo.commit(make_state(), "мир")
    with pytest.raises(KeyError):
        repo.tag("v1", "нет-такого")


def test_duplicate_branch_is_rejected() -> None:
    """Повторное создание ветки запрещено."""
    repo = Repository()
    repo.commit(make_state(), "мир")
    repo.branch_create("feature")

    with pytest.raises(ValueError):
        repo.branch_create("feature")


def test_identical_states_share_hash() -> None:
    """Одинаковые снимки дают одинаковый хеш."""
    first = make_state(year=3)
    second = make_state(year=3)

    assert first.snapshot_hash() == second.snapshot_hash()


def test_snapshot_keeps_serialized_state() -> None:
    """Снимок хранит состояние и умеет отдать его JSON."""
    repo = Repository()
    state = make_state(year=4)

    snapshot = repo.commit(state, "мир")

    assert snapshot.state == state
    assert WorldState.from_json(snapshot.state_json) == state


def test_snapshot_rejects_empty_fields() -> None:
    """Пустые хеш, сообщение и автор запрещены."""
    state = make_state()
    base: dict[str, object] = {
        "hash": "a" * 64,
        "parent_hash": None,
        "message": "мир",
        "author": "worldsim",
        "created_at": datetime.now(UTC),
        "state": state,
    }

    for field, value in (("hash", ""), ("message", ""), ("author", "")):
        with pytest.raises(ValueError):
            Snapshot(**{**base, field: value})  # type: ignore[arg-type]


def test_branch_from_empty_repository() -> None:
    """Ветку можно создать и без коммитов."""
    repo = Repository()

    assert repo.branch_create("feature") is None
    assert repo.branch == "feature"
    assert repo.branches()["feature"] is None


def test_empty_tag_name_is_rejected() -> None:
    """Пустое имя тега отклоняется."""
    repo = Repository()
    repo.commit(make_state(), "мир")

    with pytest.raises(ValueError):
        repo.tag("")


def test_init_is_idempotent() -> None:
    """Повторная инициализация не сбрасывает ветки."""
    repo = Repository()
    before = repo.branches()

    repo.init("other")

    assert repo.branches() == before
