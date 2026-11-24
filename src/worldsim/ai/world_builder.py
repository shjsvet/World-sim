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
from worldsim.core.geography import WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.generator.factions import CULTURES
from worldsim.generator.world import create_world

_IDEOLOGIES = ", ".join(ideology.value for ideology in Ideology)
_CULTURES = ", ".join(CULTURES)
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

_CULTURE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("люд", "Люди"),
    ("эльф", "Эльфы"),
    ("орк", "Орки"),
    ("гном", "Гномы"),
    ("нежит", "Нежить"),
    ("human", "Люди"),
    ("elf", "Эльфы"),
    ("orc", "Орки"),
    ("dwarf", "Гномы"),
    ("undead", "Нежить"),
)

_COUNT_WORDS: dict[str, int] = {
    "1": 1,
    "один": 1,
    "одна": 1,
    "одной": 1,
    "one": 1,
    "2": 2,
    "два": 2,
    "две": 2,
    "двух": 2,
    "two": 2,
    "3": 3,
    "три": 3,
    "трех": 3,
    "трёх": 3,
    "three": 3,
    "4": 4,
    "четыре": 4,
    "four": 4,
}

SYSTEM_PROMPT = (
    "Ты — генератор конфигурации мира. Верни строго один JSON-объект без "
    "пояснений и markdown. Поля: seed (целое), size (4..512), "
    "initial_factions (0..4), aggression (0..1), growth_rate (>=0), "
    "plague_chance (0..1), magic_level (0..1), factions — массив объектов "
    '{"name": строка, "ideology": одно из [' + _IDEOLOGIES + "], "
    '"culture": одно из [' + _CULTURES + '], "color": "#RRGGBB"}. '
    "Число фракций должно совпадать с initial_factions; культуры и названия "
    "должны соответствовать описанию пользователя."
)


class FactionSpec(BaseModel):
    """Описание фракции из ответа ИИ."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=40)
    ideology: Ideology
    color: str
    culture: str | None = None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, value: str) -> str:
        """Проверяет цвет в формате ``#RRGGBB``."""
        if not _COLOR_RE.fullmatch(value):
            raise ValueError("цвет должен быть в формате #RRGGBB")
        return value.upper()

    @field_validator("culture")
    @classmethod
    def _validate_culture(cls, value: str | None) -> str | None:
        """Проверяет культуру из известного набора."""
        if value is None or not value.strip():
            return None
        for culture in CULTURES:
            if culture.casefold() == value.strip().casefold():
                return culture
        raise ValueError(f"неизвестная культура: {value}")


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
    """Создаёт мир по описанию, применяет фракции ИИ и сохраняет черновик."""
    blueprint = build_blueprint(user_prompt, client)
    updated = _apply_blueprint(create_world(blueprint.config), blueprint)
    path = save_blueprint(user_prompt, blueprint, root=root)
    return updated, blueprint, path


def apply_offline_config(
    user_prompt: str,
    base_config: WorldConfig | None = None,
    *,
    root: Path | None = None,
) -> tuple[WorldState, WorldBlueprint, Path]:
    """Создаёт мир по описанию без ИИ: культуры и число фракций из текста."""
    config = base_config if base_config is not None else WorldConfig(seed=42, size=64)
    blueprint = blueprint_from_description(user_prompt, config)
    updated = _apply_blueprint(create_world(blueprint.config), blueprint)
    path = save_blueprint(user_prompt, blueprint, root=root)
    return updated, blueprint, path


def blueprint_from_description(
    user_prompt: str,
    base_config: WorldConfig | None = None,
) -> WorldBlueprint:
    """Собирает blueprint эвристически, когда LLM недоступен."""
    base = base_config if base_config is not None else WorldConfig(seed=42, size=64)
    specs = _description_factions(user_prompt)
    count = _description_count(user_prompt)
    if count is None:
        count = len(specs) or base.initial_factions
    count = max(0, min(4, count))

    colors = ("#AA0000", "#00AA00", "#0000AA", "#AA00AA")
    factions: list[FactionSpec] = []
    used_names: set[str] = set()
    for index in range(count):
        if index < len(specs):
            name, culture = specs[index]
        else:
            culture = CULTURES[index % len(CULTURES)]
            name = culture
        name = name[:40]
        if name.casefold() in used_names:
            suffix = f" {index + 1}"
            name = f"{name[: 40 - len(suffix)]}{suffix}"
        used_names.add(name.casefold())
        factions.append(
            FactionSpec(
                name=name,
                ideology=Ideology.MILITARIST,
                color=colors[index % len(colors)],
                culture=culture,
            )
        )
    config = base.model_copy(update={"initial_factions": count})
    return WorldBlueprint(
        config=config,
        factions=tuple(factions),
        raw={"offline": True, "description": user_prompt},
    )


def _apply_blueprint(world: WorldState, blueprint: WorldBlueprint) -> WorldState:
    """Применяет имена, цвета и культуры blueprint к сгенерированному миру."""
    factions: list[Faction] = []
    used_names: set[str] = set()
    used_colors: set[str] = set()
    culture_changes: dict[int, str] = {}
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
                        culture=spec.culture or faction.culture,
                    )
                except ValidationError:
                    candidate = None
        chosen = candidate if candidate is not None else faction
        used_names.add(chosen.name)
        used_colors.add(chosen.color)
        if chosen.culture != faction.culture:
            culture_changes[chosen.id] = chosen.culture
        factions.append(chosen)

    updated = world.evolve(factions=tuple(factions))
    if culture_changes:
        tiles = tuple(
            tile.model_copy(update={"culture": culture_changes[tile.owner_id]})
            if tile.owner_id is not None and tile.owner_id in culture_changes
            else tile
            for tile in updated.map.tiles
        )
        updated = updated.evolve(map=WorldMap(size=updated.map.size, tiles=tiles))
    return updated


def _description_factions(description: str) -> list[tuple[str, str]]:
    """Ищет культуры и названия фракций в свободном тексте."""
    segments = [
        part.strip(" .")
        for part in re.split(r"[,.:;()]|\s+и\s+|\s+and\s+", description)
        if part.strip(" .")
    ]
    found: list[tuple[str, str]] = []
    for segment in segments:
        lower = segment.casefold()
        for keyword, culture in _CULTURE_KEYWORDS:
            if keyword in lower:
                found.append((segment[:40], culture))
                break
    if found:
        return found
    return [(culture, culture) for culture in CULTURES]


def _description_count(description: str) -> int | None:
    """Определяет число фракций по словам и цифрам."""
    tokens = re.findall(r"[a-zа-я0-9-]+", description.casefold())
    for token in tokens:
        if token in _COUNT_WORDS:
            return _COUNT_WORDS[token]
    return None


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
