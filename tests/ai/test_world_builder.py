"""Тесты ИИ-генератора конфигурации мира (без сети)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from worldsim.ai.client import AIUnavailableError, Message
from worldsim.ai.world_builder import (
    SYSTEM_PROMPT,
    apply_config,
    build_blueprint,
    build_config,
)
from worldsim.core.faction import Ideology
from worldsim.core.state import WorldConfig


class FakeClient:
    """Клиент с очередью ответов."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls: list[list[Message]] = []

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Возвращает следующий ответ."""
        self.calls.append(list(messages))
        return self.answers.pop(0)


def valid_payload(
    *,
    seed: int = 7,
    size: int = 8,
    factions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Собирает валидный JSON-объект конфигурации."""
    return {
        "seed": seed,
        "size": size,
        "initial_factions": 2,
        "aggression": 0.3,
        "growth_rate": 0.01,
        "plague_chance": 0.0,
        "magic_level": 0.2,
        "factions": factions
        if factions is not None
        else [
            {"name": "Север", "ideology": "militarist", "color": "#aa0000"},
            {"name": "Юг", "ideology": "mercantile", "color": "#00aa00"},
        ],
    }


def as_json(payload: dict[str, object]) -> str:
    """Сериализует конфигурацию."""
    return json.dumps(payload, ensure_ascii=False)


def test_valid_json_builds_config() -> None:
    """Валидный JSON даёт конфигурацию и фракции."""
    client = FakeClient([as_json(valid_payload())])

    blueprint = build_blueprint("мир с двумя фракциями", client)

    assert blueprint.config.seed == 7
    assert blueprint.config.size == 8
    assert blueprint.config.aggression == 0.3
    assert [spec.name for spec in blueprint.factions] == ["Север", "Юг"]
    assert blueprint.factions[0].ideology is Ideology.MILITARIST
    assert blueprint.factions[0].color == "#AA0000"
    assert isinstance(blueprint.config, WorldConfig)
    assert "JSON" in SYSTEM_PROMPT


def test_build_config_returns_only_config() -> None:
    """build_config возвращает WorldConfig."""
    client = FakeClient([as_json(valid_payload())])

    config = build_config("описание", client)

    assert isinstance(config, WorldConfig)
    assert config.size == 8


def test_truncated_json_is_retried() -> None:
    """Обрезанный JSON уходит на повтор с текстом ошибки."""
    client = FakeClient(['{"seed": 7, "size":', as_json(valid_payload())])

    blueprint = build_blueprint("описание", client)

    assert blueprint.config.seed == 7
    assert len(client.calls) == 2
    assert "невалид" in client.calls[1][-1]["content"].lower()


def test_invalid_json_twice_raises() -> None:
    """Два невалидных ответа дают AIUnavailableError."""
    client = FakeClient(["{", "{"])

    with pytest.raises(AIUnavailableError):
        build_blueprint("описание", client)

    assert len(client.calls) == 2


def test_out_of_range_is_rejected() -> None:
    """Значения вне диапазона не проходят валидацию."""
    payload = valid_payload()
    payload["size"] = 9_999
    client = FakeClient([as_json(payload), as_json(payload)])

    with pytest.raises(AIUnavailableError):
        build_config("описание", client)


def test_invalid_color_is_retried() -> None:
    """Невалидный цвет фракции требует повтора."""
    bad = valid_payload(factions=[{"name": "Север", "ideology": "militarist", "color": "red"}])
    client = FakeClient([as_json(bad), as_json(valid_payload())])

    blueprint = build_blueprint("описание", client)

    assert blueprint.config.size == 8
    assert len(client.calls) == 2


def test_apply_config_creates_world_and_saves(tmp_path: Path) -> None:
    """apply_config создаёт мир, применяет фракции и сохраняет черновик."""
    client = FakeClient([as_json(valid_payload())])

    world, blueprint, path = apply_config("мир", client, root=tmp_path)

    assert world.config.seed == 7
    assert [faction.name for faction in world.factions] == ["Север", "Юг"]
    assert world.factions[0].color == "#AA0000"
    assert blueprint.config.size == 8
    assert path.parent == tmp_path / "worlds"
    assert path.suffix == ".json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["prompt"] == "мир"
    assert saved["config"]["size"] == 8
    assert list((tmp_path / "worlds").glob("*.tmp")) == []


def test_duplicate_colors_fall_back_to_generated(tmp_path: Path) -> None:
    """Повтор цвета заменяется сгенерированным цветом фракции."""
    factions = [
        {"name": "Север", "ideology": "militarist", "color": "#AA0000"},
        {"name": "Юг", "ideology": "militarist", "color": "#AA0000"},
    ]
    client = FakeClient([as_json(valid_payload(factions=factions))])

    world, _, _ = apply_config("мир", client, root=tmp_path)

    colors = [faction.color for faction in world.factions]
    assert len(colors) == 2
    assert colors[0] != colors[1]
    assert world.factions[0].name == "Север"
    assert world.factions[1].name != "Север"


def test_fewer_specs_keep_generated_factions(tmp_path: Path) -> None:
    """Если ИИ описал меньше фракций, остальные остаются сгенерированными."""
    factions = [{"name": "Север", "ideology": "militarist", "color": "#AA0000"}]
    client = FakeClient([as_json(valid_payload(factions=factions))])

    world, _, _ = apply_config("мир", client, root=tmp_path)

    assert len(world.factions) == 2
    assert world.factions[0].name == "Север"
    assert world.factions[1].name != "Север"


def test_saved_blueprint_contains_factions(tmp_path: Path) -> None:
    """Сохранённый JSON содержит фракции из ответа ИИ."""
    client = FakeClient([as_json(valid_payload())])

    _, _, path = apply_config("мир", client, root=tmp_path)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [item["name"] for item in saved["factions"]] == ["Север", "Юг"]
    assert saved["factions"][0]["ideology"] == "militarist"
