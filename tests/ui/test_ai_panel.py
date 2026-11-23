"""Тесты UI-обёрток ИИ (без Streamlit)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from worldsim.ai.client import AIUnavailableError, Message
from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event
from worldsim.core.state import WorldConfig
from worldsim.engine.engine import SimulationEngine
from worldsim.generator.world import create_world
from worldsim.ui.ai_panel import (
    create_ai_world,
    manual_config,
    manual_world,
    safe_client,
    write_chapter_for_engine,
)


class FakeClient:
    """Клиент с фиксированным ответом."""

    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[list[Message]] = []

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Запоминает вызов и отдаёт ответ."""
        self.calls.append(list(messages))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Убирает переменные окружения провайдеров."""
    for name in (
        "WORLDSIM_AI_PROVIDER",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "OLLAMA_HOST",
    ):
        monkeypatch.delenv(name, raising=False)


def test_manual_config_fields() -> None:
    """Ручная конфигурация собирается из полей формы."""
    config = manual_config(seed=3, size=16, aggression=0.7, magic_level=0.4)

    assert config.seed == 3
    assert config.size == 16
    assert config.aggression == 0.7
    assert config.magic_level == 0.4


def test_manual_config_validation() -> None:
    """Невалидные значения отклоняются."""
    with pytest.raises(ValidationError):
        manual_config(size=2)


def test_manual_world_builds_without_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без ключей мир создаётся вручную."""
    clear_env(monkeypatch)

    world = manual_world(seed=5, size=8, initial_factions=2)

    assert world.config.size == 8
    assert len(world.factions) == 2


def test_safe_client_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без ключей возвращается понятная ошибка, а не исключение."""
    clear_env(monkeypatch)

    client, error = safe_client()

    assert client is None
    assert error is not None and error


def test_safe_client_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Неизвестный провайдер не ломает страницу."""
    clear_env(monkeypatch)

    client, error = safe_client("unknown")

    assert client is None
    assert error is not None


def valid_world_json() -> str:
    """Валидный JSON конфигурации мира."""
    return json.dumps(
        {
            "seed": 9,
            "size": 8,
            "initial_factions": 2,
            "aggression": 0.4,
            "growth_rate": 0.02,
            "plague_chance": 0.0,
            "magic_level": 0.1,
            "factions": [
                {"name": "Север", "ideology": "militarist", "color": "#AA0000"},
                {"name": "Юг", "ideology": "mercantile", "color": "#00AA00"},
            ],
        },
        ensure_ascii=False,
    )


def test_create_ai_world(tmp_path: Path) -> None:
    """Мир по описанию создаётся и сохраняется."""
    client = FakeClient(valid_world_json())

    world, blueprint, path = create_ai_world("описание", client, root=tmp_path)

    assert world.config.seed == 9
    assert [faction.name for faction in world.factions] == ["Север", "Юг"]
    assert blueprint.config.size == 8
    assert path.parent == tmp_path / "worlds"


def test_write_chapter_for_engine(tmp_path: Path) -> None:
    """Глава пишется и сохраняется с front-matter."""
    engine = SimulationEngine(
        [],
        Chronicle(),
        initial_state=create_world(WorldConfig(seed=1, size=8)),
    )
    engine.chronicle.add(Event.expansion(year=0, faction_id=0, tile_id=0))
    client = FakeClient("В год 0 фракция расширилась.")

    path = write_chapter_for_engine(
        engine,
        client,
        0,
        0,
        directory=tmp_path / "chronicle",
        seed=1,
    )

    content = path.read_text(encoding="utf-8")
    assert path.name == "chapter_0_0.md"
    assert "year_from: 0" in content
    assert "seed: 1" in content
    assert "В год 0 фракция расширилась." in content


def test_write_chapter_falls_back_without_ai(tmp_path: Path) -> None:
    """При недоступности ИИ сохраняется fallback-глава."""
    engine = SimulationEngine(
        [],
        Chronicle(),
        initial_state=create_world(WorldConfig(seed=1, size=8)),
    )
    engine.chronicle.add(Event.expansion(year=0, faction_id=0, tile_id=0))
    client = FakeClient(AIUnavailableError("нет ключа"))

    path = write_chapter_for_engine(engine, client, 0, 0, directory=tmp_path)

    content = path.read_text(encoding="utf-8")
    assert "# Летопись" in content
    assert "0" in content


def test_chapter_uses_only_period_events(tmp_path: Path) -> None:
    """В запрос попадают только события выбранного периода."""
    engine = SimulationEngine(
        [],
        Chronicle(),
        initial_state=create_world(WorldConfig(seed=1, size=8)),
    )
    engine.chronicle.add(Event.expansion(year=0, faction_id=0, tile_id=0))
    engine.chronicle.add(Event.expansion(year=1, faction_id=0, tile_id=1))
    client = FakeClient("В год 1 фракция расширилась.")

    write_chapter_for_engine(engine, client, 1, 1, directory=tmp_path)

    payload = client.calls[0][-1]["content"]
    assert '"year":1' in payload.replace(" ", "")
    assert '"year":0' not in payload.replace(" ", "")
