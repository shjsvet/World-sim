"""Модель коммита файлового репозитория версий."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Commit(BaseModel):
    """Неизменяемая запись коммита.

    ``id`` — sha256 от родителя, года, сообщения и хеша снимка; ``created_at``
    передаётся снаружи (UTC), модели не вызывают ``datetime.now()``.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=16)
    parent_id: str | None = None
    branch: str
    year: int = Field(ge=0)
    message: str = Field(min_length=1)
    created_at: datetime
    snapshot_hash: str = Field(min_length=16)

    @field_validator("created_at")
    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        """Приводит время создания к UTC."""
        if value.tzinfo is None:
            raise ValueError("created_at должен быть с часовым поясом")
        return value.astimezone(UTC)
