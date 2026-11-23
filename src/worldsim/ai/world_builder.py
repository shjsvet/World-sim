"""Генерация конфигурации мира по текстовому описанию через LLM."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from worldsim.ai.client import AIUnavailableError, LLMClient, Message
from worldsim.core.faction import Faction, Ideology
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.world import create_world

_IDEOLOGIES = ", ".join(ideology.value for ideology in Ideology)
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

SYSTEM_PROMPT = (
    "Ты — генератор конфигурации мира. Верни строго один JSON-объект без "
    "пояснений и markdown. Поля: seed (целое), size (4..512), "
    "initial_factions (0..4), aggression (0..1), growth_rate (>=0), "
    "plague_chance (0..1), magic_level (0..1), factions — массив объектов "
    '{"name": строка, "ideology": одно из [' + _IDEOLOGIES + "], "
    '"color": "#RRGGBB"}.'
)


class FactionSpec(BaseModel):
    """Описание фракции из ответа ИИ."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=40)
    ideology: Ideology
    color: str

    @field_validator("color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        """Проверяет цвет в формате ``#RRGGBB``."""
        if not _COLOR_RE.fullmatch(value):
            raise ValueError("цвет должен быть в формате #RRGGBB")
        return value.upper()


class _ConfigDraft(BaseModel):
    """Промежуточная модель JSON-ответа."""

    model_config = ConfigDict(extra="ignore")

    seed: int = 42
    size: int = Field(default=32, ge=4, le=512)
    initial_factions: int = Field(default=2, ge=0, le=4)
    aggression: float = Field(default=0.5, ge=0, le=1)
    growth_rate: float = Field(default=0.02, ge=0)
    plague_chance: float = Field(default=0.01, ge=0, le=1)
    magic_level: float = Field(default=0.0, ge=0, le=1)
    factions: list[FactionSpec] = Field(default_factory=list)


@dataclass(frozen=True)
class WorldBlueprint:
    """Конфигурация мира и описания фракций из ответа ИИ."""

    config: WorldConfig
    factions: tuple[FactionSpec, ...]
    raw: dict[str, object]


def build_blueprint(user_prompt: str, client: LLMClient) -> WorldBlueprint:
    """Просит у ИИ конфигурацию и описания фракций.

    При невалидном ответе делается одна повторная попытка с текстом ошибки,
    затем поднимается ``AIUnavailableError``.
    """
    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=user_prompt),
    ]
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            answer = client.complete(messages, json_mode=True)
        except AIUnavailableError:
            raise
        try:
            data = json.loads(answer)
            if not isinstance(data, dict):
                raise ValueError("ожидался JSON-объект")
            draft = _ConfigDraft.model_validate(data)
            config = WorldConfig.model_validate(draft.model_dump(exclude={"factions"}))
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            messages.append(
                Message(
                    role="user",
                    content=(
                        f"Ответ невалиден: {exc}. Верни только корректный JSON "
                        "с нужными полями и диапазонами."
                    ),
                )
            )
            continue
        return WorldBlueprint(
            config=config,
            factions=tuple(draft.factions),
            raw=data,
        )

    raise AIUnavailableError(f"ИИ не вернул корректную конфигурацию: {last_error}")


def build_config(user_prompt: str, client: LLMClient) -> WorldConfig:
    """Возвращает только конфигурацию мира из ответа ИИ."""
    return build_blueprint(user_prompt, client).config


def apply_config(
    user_prompt: str,
    client: LLMClient,
    *,
    root: Path | None = None,
) -> tuple[WorldState, WorldBlueprint, Path]:
    """Создаёт мир по описанию, применяет фракции ИИ и сохраняет черновик.

    Имена и цвета фракций проверяются; при конфликте (повтор имени или цвета,
    невалидное значение) остаётся сгенерированная фракция.
    """
    blueprint = build_blueprint(user_prompt, client)
    world = create_world(blueprint.config)

    factions: list[Faction] = []
    used_names: set[str] = set()
    used_colors: set[str] = set()
    for index, faction in enumerate(world.factions):
        candidate: Faction | None = None
        if index < len(blueprint.factions):
            spec = blueprint.factions[index]
            if spec.name not in used_names and spec.color not in used_colors:
                try:
                    candidate = faction.evolve(
                        name=spec.name,
                        color=spec.color,
                        ideology=spec.ideology,
                    )
                except ValidationError:
                    candidate = None
        chosen = candidate if candidate is not None else faction
        used_names.add(chosen.name)
        used_colors.add(chosen.color)
        factions.append(chosen)

    updated = world.evolve(factions=tuple(factions))
    path = save_blueprint(user_prompt, blueprint, root=root)
    return updated, blueprint, path


def save_blueprint(
    user_prompt: str,
    blueprint: WorldBlueprint,
    *,
    root: Path | None = None,
) -> Path:
    """Сохраняет промпт и итоговый JSON в ``worlds/<hash>.json``."""
    payload: dict[str, object] = {
        "prompt": user_prompt,
        "config": blueprint.config.model_dump(),
        "factions": [spec.model_dump() for spec in blueprint.factions],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    base = Path(root) if root is not None else Path.cwd()
    target = base / "worlds" / f"{digest}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target
