"""Неизменяемый снимок мира для системы версий."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from worldsim.core.state import WorldState


@dataclass(frozen=True)
class Snapshot:
    """Коммит версии мира: хеш, родитель, автор и сообщение."""

    hash: str
    parent_hash: str | None
    message: str
    author: str
    created_at: datetime
    state: WorldState
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.hash:
            raise ValueError("хеш снимка не может быть пустым")
        if not self.message:
            raise ValueError("сообщение коммита не может быть пустым")
        if not self.author:
            raise ValueError("автор коммита не может быть пустым")

    @property
    def state_json(self) -> str:
        """Сериализованное состояние снимка."""
        return self.state.to_json()

    @property
    def created_at_utc(self) -> datetime:
        """Время создания в UTC."""
        return self.created_at.astimezone(UTC)
