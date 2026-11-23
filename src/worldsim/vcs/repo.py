"""Репозитории версий мира: in-memory и файловый ``.worldsim/``."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldState
from worldsim.vcs.commit import Commit
from worldsim.vcs.diff import Diff, compute_diff
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


class RepositoryError(Exception):
    """Ошибка чтения или адресации файлового репозитория."""


def compute_commit_id(
    parent_id: str | None,
    year: int,
    message: str,
    snapshot_hash: str,
) -> str:
    """Считает идентификатор коммита по родителю, году, сообщению и снимку."""
    payload = f"{parent_id or ''}|{year}|{message}|{snapshot_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class WorldRepo:
    """Файловый репозиторий версий в каталоге ``.worldsim/``.

    Раскладка:
    ``objects/<commit_id>.json`` — метаданные коммита, снимок и летопись;
    ``refs/branches/<name>`` — идентификатор коммита ветки;
    ``refs/tags/<name>`` — именованная ссылка на коммит;
    ``HEAD`` — текущая ветка или идентификатор коммита.

    Запись выполняется атомарно: временный файл рядом с целевым и
    ``os.replace``. Повреждённые объекты дают ``RepositoryError``.

    Слияние веток (``merge``) сознательно не реализуется: альтернативные
    реальности развиваются независимо, а выбор между ними остаётся за
    пользователем через ``checkout``.
    """

    def __init__(self, root: Path, chronicle: Chronicle | None = None) -> None:
        self.root = Path(root)
        self.meta_dir = self.root / ".worldsim"
        self.objects_dir = self.meta_dir / "objects"
        self.refs_dir = self.meta_dir / "refs" / "branches"
        self.tags_dir = self.meta_dir / "refs" / "tags"
        self.head_path = self.meta_dir / "HEAD"
        self._chronicle = chronicle

    def init(self) -> None:
        """Создаёт структуру каталогов и ``HEAD`` (идемпотентно)."""
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.refs_dir.mkdir(parents=True, exist_ok=True)
        self.tags_dir.mkdir(parents=True, exist_ok=True)
        if not self.head_path.exists():
            self._write_atomic(self.head_path, "main")

    def _write_atomic(self, path: Path, data: str) -> None:
        """Пишет файл через временный и ``os.replace``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        text = data if data.endswith("\n") else data + "\n"
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)

    def _read_text(self, path: Path) -> str:
        """Читает текстовый файл репозитория."""
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RepositoryError(f"не удалось прочитать {path}") from exc

    def _read_json(self, path: Path) -> dict[str, object]:
        """Читает JSON-объект, превращая повреждения в ``RepositoryError``."""
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RepositoryError(f"объект не найден: {path.stem}") from exc
        except OSError as exc:
            raise RepositoryError(f"не удалось прочитать {path}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RepositoryError(f"повреждённый JSON: {path.name}") from exc
        if not isinstance(data, dict):
            raise RepositoryError(f"ожидался JSON-объект: {path.name}")
        return data

    def _read_commit(self, commit_id: str) -> Commit:
        """Загружает метаданные коммита по идентификатору."""
        data = self._read_json(self.objects_dir / f"{commit_id}.json")
        payload = data.get("commit")
        if not isinstance(payload, dict):
            raise RepositoryError(f"в объекте {commit_id} нет коммита")
        try:
            commit = Commit.model_validate(payload)
        except ValidationError as exc:
            raise RepositoryError(f"некорректный коммит {commit_id}") from exc
        if commit.id != commit_id:
            raise RepositoryError(f"идентификатор объекта не совпадает: {commit_id}")
        return commit

    def _read_payload(self, commit_id: str) -> tuple[Commit, WorldState, Chronicle]:
        """Загружает коммит, снимок мира и летопись."""
        data = self._read_json(self.objects_dir / f"{commit_id}.json")
        commit = self._read_commit(commit_id)
        snapshot = data.get("snapshot")
        chronicle = data.get("chronicle")
        if not isinstance(snapshot, dict) or not isinstance(chronicle, dict):
            raise RepositoryError(f"объект {commit_id} не содержит снимок и летопись")
        try:
            state = WorldState.model_validate(snapshot)
            history = Chronicle.from_json(json.dumps(chronicle, ensure_ascii=False))
        except (ValidationError, ValueError) as exc:
            raise RepositoryError(f"повреждённый объект {commit_id}") from exc
        if state.snapshot_hash() != commit.snapshot_hash:
            raise RepositoryError(f"хеш снимка не совпадает с коммитом {commit_id}")
        return commit, state, history

    def _resolve(self, ref: str) -> str:
        """Превращает ``HEAD``, имя ветки, тег или id в идентификатор коммита."""
        value = self._read_text(self.head_path) if ref == "HEAD" else ref
        for directory in (self.refs_dir, self.tags_dir):
            ref_path = directory / value
            if ref_path.exists():
                value = self._read_text(ref_path)
                break
        if (self.objects_dir / f"{value}.json").exists():
            return value
        raise RepositoryError(f"неизвестная ссылка: {ref}")

    def _parent_for(self, branch: str) -> str | None:
        """Определяет родителя нового коммита в ветке."""
        ref_path = self.refs_dir / branch
        if ref_path.exists():
            return self._read_text(ref_path)
        if not self.head_path.exists():
            return None
        head = self._read_text(self.head_path)
        if (self.refs_dir / head).exists():
            return self._read_text(self.refs_dir / head)
        if (self.objects_dir / f"{head}.json").exists():
            return head
        return None

    def commit(
        self,
        state: WorldState,
        message: str,
        branch: str = "main",
        created_at: datetime | None = None,
        chronicle: Chronicle | None = None,
    ) -> Commit:
        """Создаёт коммит и обновляет ветку и ``HEAD``."""
        self.init()
        parent_id = self._parent_for(branch)
        snapshot_hash = state.snapshot_hash()
        commit_id = compute_commit_id(parent_id, state.year, message, snapshot_hash)
        if (self.objects_dir / f"{commit_id}.json").exists():
            return self._read_commit(commit_id)

        created = created_at if created_at is not None else datetime.now(UTC)
        commit = Commit(
            id=commit_id,
            parent_id=parent_id,
            branch=branch,
            year=state.year,
            message=message,
            created_at=created,
            snapshot_hash=snapshot_hash,
        )
        history = chronicle
        if history is None:
            history = self._chronicle if self._chronicle is not None else Chronicle()
        payload = {
            "commit": json.loads(commit.model_dump_json()),
            "snapshot": json.loads(state.to_json()),
            "chronicle": json.loads(history.to_json()),
        }
        self._write_atomic(
            self.objects_dir / f"{commit_id}.json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
        self._write_atomic(self.refs_dir / branch, commit_id)
        self._write_atomic(self.head_path, branch)
        return commit

    def checkout(self, ref: str = "HEAD") -> tuple[WorldState, Chronicle]:
        """Восстанавливает состояние и летопись по ссылке."""
        self.init()
        commit_id = self._resolve(ref)
        _, state, history = self._read_payload(commit_id)
        if ref == "HEAD":
            target = self._read_text(self.head_path)
        elif (self.refs_dir / ref).exists():
            target = ref
        else:
            target = commit_id
        self._write_atomic(self.head_path, target)
        return state, history

    def log(self, branch: str | None = None) -> list[Commit]:
        """История коммитов от ``HEAD`` (или ветки) к корню."""
        self.init()
        ref = branch if branch is not None else self._read_text(self.head_path)
        try:
            cursor: str | None = self._resolve(ref)
        except RepositoryError:
            return []
        history: list[Commit] = []
        while cursor is not None:
            commit = self._read_commit(cursor)
            history.append(commit)
            cursor = commit.parent_id
        return history

    def current_branch(self) -> str:
        """Имя текущей ветки или ``detached`` для отсоединённого ``HEAD``."""
        self.init()
        head = self._read_text(self.head_path)
        return head if (self.refs_dir / head).exists() else "detached"

    def head(self) -> Commit | None:
        """Текущий коммит или ``None`` для пустого репозитория."""
        self.init()
        try:
            return self._read_commit(self._resolve("HEAD"))
        except RepositoryError:
            return None

    def diff(self, from_ref: str, to_ref: str) -> Diff:
        """Сравнивает два снимка репозитория по тайлам, фракциям и летописи."""
        self.init()
        _, from_state, from_chronicle = self._read_payload(self._resolve(from_ref))
        _, to_state, to_chronicle = self._read_payload(self._resolve(to_ref))
        return compute_diff(from_state, from_chronicle, to_state, to_chronicle)

    def create_branch(self, name: str, from_ref: str = "HEAD") -> str:
        """Создаёт ветку от ссылки и возвращает идентификатор коммита.

        Слияние веток не поддерживается: альтернативные реальности
        развиваются независимо.
        """
        self.init()
        self._validate_branch_name(name)
        if (self.refs_dir / name).exists():
            raise RepositoryError(f"ветка уже существует: {name}")
        commit_id = self._resolve(from_ref)
        self._write_atomic(self.refs_dir / name, commit_id)
        return commit_id

    def checkout_branch(self, name: str) -> tuple[WorldState, Chronicle]:
        """Переключает ``HEAD`` на ветку и восстанавливает её состояние."""
        self.init()
        if not (self.refs_dir / name).exists():
            raise RepositoryError(f"ветка не найдена: {name}")
        return self.checkout(name)

    def list_branches(self) -> dict[str, str]:
        """Возвращает существующие ветки: имя → идентификатор коммита."""
        self.init()
        return {
            path.name: self._read_text(path)
            for path in sorted(self.refs_dir.iterdir())
            if path.is_file()
        }

    def tag(self, name: str, ref: str = "HEAD") -> str:
        """Ставит именованную ссылку на коммит и возвращает его id."""
        self.init()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise RepositoryError(f"недопустимое имя тега: {name}")
        if (self.tags_dir / name).exists():
            raise RepositoryError(f"тег уже существует: {name}")
        commit_id = self._resolve(ref)
        self._write_atomic(self.tags_dir / name, commit_id)
        return commit_id

    @staticmethod
    def _validate_branch_name(name: str) -> None:
        """Проверяет имя ветки по шаблону ``[A-Za-z0-9_-]+``."""
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise RepositoryError(f"недопустимое имя ветки: {name}")
