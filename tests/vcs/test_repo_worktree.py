"""Тесты файлового репозитория ``.worldsim/``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.world import create_world
from worldsim.vcs.repo import RepositoryError, WorldRepo, compute_commit_id


def make_state(year: int = 0, seed: int = 1) -> WorldState:
    """Создаёт небольшой мир нужного года."""
    return create_world(WorldConfig(seed=seed, size=8)).evolve(year=year)


def make_chronicle() -> Chronicle:
    """Создаёт летопись с одним событием."""
    chronicle = Chronicle()
    chronicle.add(Event.expansion(year=5, faction_id=0, tile_id=0))
    return chronicle


def test_init_is_idempotent_and_creates_layout(tmp_path: Path) -> None:
    """Инициализация создаёт каталоги и HEAD, повторный вызов безопасен."""
    repo = WorldRepo(tmp_path)
    repo.init()

    objects = repo.objects_dir
    refs = repo.refs_dir
    head_value = repo.head_path.read_text(encoding="utf-8").strip()

    repo.init()

    assert objects.is_dir()
    assert refs.is_dir()
    assert head_value == "main"
    assert repo.head_path.read_text(encoding="utf-8").strip() == "main"


def test_commit_writes_object_and_refs(tmp_path: Path) -> None:
    """Коммит пишет объект, ссылку ветки и HEAD."""
    repo = WorldRepo(tmp_path)
    state = make_state(year=3)

    commit = repo.commit(state, "третий год")

    assert (repo.objects_dir / f"{commit.id}.json").is_file()
    assert (repo.refs_dir / "main").read_text(encoding="utf-8").strip() == commit.id
    assert repo.head_path.read_text(encoding="utf-8").strip() == "main"
    assert repo.current_branch() == "main"
    assert repo.head() == commit
    assert repo.log() == [commit]


def test_history_links_parents(tmp_path: object) -> None:
    """Два коммита подряд связаны ``parent_id`` и упорядочены в ``log``."""
    repo = WorldRepo(tmp_path)  # type: ignore[arg-type]
    first = repo.commit(make_state(year=0), "год 0")
    second = repo.commit(make_state(year=1), "год 1")

    assert second.parent_id == first.id
    assert repo.log() == [second, first]
    assert repo.log("main") == [second, first]


def test_checkout_restores_snapshot_and_chronicle(tmp_path: object) -> None:
    """Checkout восстанавливает тот же снимок и летопись."""
    chronicle = make_chronicle()
    repo = WorldRepo(tmp_path, chronicle=chronicle)  # type: ignore[arg-type]
    state = make_state(year=10)
    commit = repo.commit(state, "мир")

    for ref in (commit.id, "main", "HEAD"):
        restored_state, restored_chronicle = repo.checkout(ref)
        assert restored_state.snapshot_hash() == commit.snapshot_hash
        assert restored_state == state
        assert restored_chronicle.to_json() == chronicle.to_json()


def test_checkout_unknown_ref_is_rejected(tmp_path: object) -> None:
    """Неизвестная ссылка даёт ``RepositoryError``."""
    repo = WorldRepo(tmp_path)  # type: ignore[arg-type]
    repo.commit(make_state(), "мир")

    with pytest.raises(RepositoryError):
        repo.checkout("нет-такого")


def test_missing_object_is_rejected(tmp_path: object) -> None:
    """Отсутствующий объект коммита даёт ``RepositoryError``."""
    repo = WorldRepo(tmp_path)  # type: ignore[arg-type]
    commit = repo.commit(make_state(), "мир")
    (repo.objects_dir / f"{commit.id}.json").unlink()

    with pytest.raises(RepositoryError):
        repo.checkout(commit.id)


def test_corrupted_object_is_rejected(tmp_path: object) -> None:
    """Повреждённый JSON объекта даёт ``RepositoryError``."""
    repo = WorldRepo(tmp_path)  # type: ignore[arg-type]
    commit = repo.commit(make_state(), "мир")
    object_path = repo.objects_dir / f"{commit.id}.json"
    object_path.write_text("{ это не json", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo.checkout(commit.id)


def test_atomic_write_leaves_no_temp_files(tmp_path: object) -> None:
    """Атомарная запись не оставляет временных файлов."""
    repo = WorldRepo(tmp_path)  # type: ignore[arg-type]
    repo.commit(make_state(year=0), "первый")
    repo.commit(make_state(year=1), "второй")

    leftovers = list(repo.meta_dir.rglob("*.tmp"))
    assert leftovers == []


def test_commit_id_is_deterministic() -> None:
    """Идентификатор зависит только от родителя, года, сообщения и снимка."""
    state = make_state(year=2)
    digest = state.snapshot_hash()

    first = compute_commit_id(None, 2, "мир", digest)
    second = compute_commit_id(None, 2, "мир", digest)

    assert first == second
    assert first != compute_commit_id(None, 2, "другое", digest)
    assert first != compute_commit_id("родитель", 2, "мир", digest)


def test_commit_id_matches_compute(tmp_path: object) -> None:
    """Коммит использует тот же расчёт идентификатора."""
    state = make_state(year=4)
    repo = WorldRepo(tmp_path)  # type: ignore[arg-type]

    commit = repo.commit(state, "мир")

    assert commit.id == compute_commit_id(None, 4, "мир", state.snapshot_hash())


def test_commit_created_at_is_respected(tmp_path: Path) -> None:
    """Переданное время создания сохраняется в UTC."""
    created = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    repo = WorldRepo(tmp_path)

    commit = repo.commit(make_state(), "мир", created_at=created)

    assert commit.created_at == created
    assert commit.created_at.tzinfo is UTC


def test_default_created_at_is_timezone_aware(tmp_path: Path) -> None:
    """Время по умолчанию имеет часовой пояс UTC."""
    repo = WorldRepo(tmp_path)

    commit = repo.commit(make_state(), "мир")

    assert commit.created_at.tzinfo is UTC


def test_detached_checkout(tmp_path: Path) -> None:
    """Checkout по идентификатору отсоединяет HEAD."""
    repo = WorldRepo(tmp_path)
    first = repo.commit(make_state(year=0), "первый")
    repo.commit(make_state(year=1), "второй")

    repo.checkout(first.id)

    assert repo.current_branch() == "detached"
    assert repo.head() == first


def test_log_of_empty_repository_is_empty(tmp_path: Path) -> None:
    """Пустой репозиторий отдаёт пустую историю."""
    repo = WorldRepo(tmp_path)

    assert repo.log() == []
    assert repo.head() is None
