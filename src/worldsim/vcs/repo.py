"""Репозиторий версий мира в памяти (git-подобная модель)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from worldsim.core.state import WorldState
from worldsim.vcs.snapshot import Snapshot


class Repository:
    """Хранит снимки мира, ветки и теги в памяти.

    Ветка — указатель на хеш снимка; ``HEAD`` — текущая ветка или
    отсоединённый коммит. Состояние снимка сериализуется через
    ``WorldState.to_json()`` при необходимости, а объекты лежат в
    ``dict[hash, Snapshot]``.
    """

    def __init__(self) -> None:
        self._objects: dict[str, Snapshot] = {}
        self._branches: dict[str, str | None] = {}
        self._head_branch: str | None = None
        self._detached: str | None = None
        self.init()

    def init(self, branch: str = "main") -> None:
        """Создаёт основную ветку, если репозиторий пуст."""
        if self._branches:
            return
        self._branches[branch] = None
        self._head_branch = branch

    def commit(self, state: WorldState, message: str, author: str = "worldsim") -> Snapshot:
        """Создаёт снимок состояния.

        Повторный коммит того же состояния возвращает существующий снимок
        (идемпотентность), не меняя указатели ветки.
        """
        digest = state.snapshot_hash()
        existing = self._objects.get(digest)
        if existing is not None:
            return existing

        snapshot = Snapshot(
            hash=digest,
            parent_hash=self._current_hash(),
            message=message,
            author=author,
            created_at=datetime.now(UTC),
            state=state,
        )
        self._objects[digest] = snapshot
        if self._detached is not None:
            self._detached = digest
        elif self._head_branch is not None:
            self._branches[self._head_branch] = digest
        return snapshot

    @property
    def head(self) -> Snapshot | None:
        """Снимок в текущей позиции ``HEAD``."""
        digest = self._current_hash()
        return self._objects.get(digest) if digest is not None else None

    @property
    def branch(self) -> str | None:
        """Имя текущей ветки или ``None`` при отсоединённом ``HEAD``."""
        return None if self._detached is not None else self._head_branch

    @property
    def objects(self) -> dict[str, Snapshot]:
        """Все снимки репозитория."""
        return dict(self._objects)

    def log(self) -> tuple[Snapshot, ...]:
        """История от ``HEAD`` к корню, от новых к старым."""
        history: list[Snapshot] = []
        digest = self._current_hash()
        while digest is not None:
            snapshot = self._objects.get(digest)
            if snapshot is None:
                break
            history.append(snapshot)
            digest = snapshot.parent_hash
        return tuple(history)

    def checkout(self, hash: str) -> Snapshot:
        """Переключает ``HEAD`` на снимок (отсоединённое состояние)."""
        snapshot = self._objects.get(hash)
        if snapshot is None:
            raise KeyError(f"снимок не найден: {hash}")
        self._detached = hash
        return snapshot

    def branch_create(self, name: str) -> Snapshot | None:
        """Создаёт ветку от текущего ``HEAD`` и переключается на неё."""
        if name in self._branches:
            raise ValueError(f"ветка уже существует: {name}")
        base = self._current_hash()
        self._branches[name] = base
        self._head_branch = name
        self._detached = None
        return self._objects.get(base) if base is not None else None

    def switch_branch(self, name: str) -> Snapshot | None:
        """Переключается на существующую ветку."""
        if name not in self._branches:
            raise KeyError(f"ветка не найдена: {name}")
        self._head_branch = name
        self._detached = None
        digest = self._branches[name]
        return self._objects.get(digest) if digest is not None else None

    def branches(self) -> dict[str, str | None]:
        """Копия указателей веток (имя → хеш)."""
        return dict(self._branches)

    def tag(self, name: str, hash: str | None = None) -> Snapshot:
        """Ставит тег на снимок (по умолчанию на текущий ``HEAD``)."""
        target = hash if hash is not None else self._current_hash()
        if target is None:
            raise KeyError("нечего помечать тегом: репозиторий пуст")
        snapshot = self._objects.get(target)
        if snapshot is None:
            raise KeyError(f"снимок не найден: {target}")
        if not name:
            raise ValueError("имя тега не может быть пустым")
        updated = replace(snapshot, tags=(*snapshot.tags, name))
        self._objects[target] = updated
        return updated

    def _current_hash(self) -> str | None:
        """Хеш текущей позиции ``HEAD``."""
        if self._detached is not None:
            return self._detached
        if self._head_branch is None:
            return None
        return self._branches.get(self._head_branch)
