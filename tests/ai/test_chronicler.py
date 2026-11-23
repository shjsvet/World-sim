"""Тесты ИИ-хрониста на mock-клиенте."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import httpx

from worldsim.ai.chronicler import (
    SYSTEM_PROMPT,
    ChronicleWriter,
    fallback_chapter,
    save_chapter,
)
from worldsim.ai.client import AIUnavailableError, Message, OpenAIClient
from worldsim.core.events import Event


class FakeClient:
    """Клиент, возвращающий заранее заданный ответ или ошибку."""

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


def make_events() -> list[Event]:
    """Создаёт два события разных лет."""
    return [
        Event.expansion(year=10, faction_id=0, tile_id=0),
        Event.war(year=11, attacker_id=0, defender_id=1, tile_id=1),
    ]


def test_successful_chapter() -> None:
    """Валидный ответ клиента возвращается как глава."""
    client = FakeClient("В год 10 фракция расширилась. В год 11 началась война.")
    writer = ChronicleWriter(client)

    text = writer.write_chapter(make_events(), 10, 11)

    assert text == "В год 10 фракция расширилась. В год 11 началась война."
    assert len(client.calls) == 1
    messages = client.calls[0]
    assert messages[0]["role"] == "system"
    assert "не выдумывай" in messages[0]["content"].lower()
    assert '"year":10' in messages[1]["content"].replace(" ", "")
    assert "JSON" in messages[1]["content"]


def test_fallback_when_client_unavailable() -> None:
    """При недоступности ИИ возвращается markdown-летопись."""
    client = FakeClient(AIUnavailableError("нет ключа"))
    writer = ChronicleWriter(client)

    text = writer.write_chapter(make_events(), 10, 11)

    assert "# Летопись" in text
    assert "10" in text
    assert "11" in text


def test_fallback_when_year_is_missing() -> None:
    """Ответ без упоминания всех лет периода отбрасывается."""
    client = FakeClient("В год 10 всё было спокойно.")
    writer = ChronicleWriter(client)

    text = writer.write_chapter(make_events(), 10, 11)

    assert text.startswith("# Летопись")


def test_fallback_on_placeholder() -> None:
    """Заглушки в ответе приводят к fallback."""
    client = FakeClient("TODO: год 10, год 11")
    writer = ChronicleWriter(client)

    assert writer.write_chapter(make_events(), 10, 11).startswith("# Летопись")


def test_empty_events_do_not_call_client() -> None:
    """Пустой период обрабатывается без обращения к ИИ."""
    client = FakeClient("не должно вызываться")
    writer = ChronicleWriter(client)

    text = writer.write_chapter([], 5, 6)

    assert "Летопись, годы 5–6" in text
    assert "Событий за этот период не было" in text
    assert client.calls == []


def test_fallback_chapter_contains_events() -> None:
    """Fallback собирает markdown из переданных событий."""
    text = fallback_chapter(make_events(), 10, 11)

    assert "# Летопись, годы 10–11" in text
    assert "10" in text
    assert "11" in text


def test_save_chapter_with_front_matter(tmp_path: Path) -> None:
    """Глава сохраняется в каталог с корректным front-matter."""
    target = save_chapter(
        tmp_path,
        "# Глава\n\nТекст главы.",
        year_from=5,
        year_to=6,
        seed=42,
        model="gpt-4o-mini",
    )

    content = target.read_text(encoding="utf-8")
    assert target == tmp_path / "chapter_5_6.md"
    assert content.startswith("---\n")
    assert "year_from: 5" in content
    assert "year_to: 6" in content
    assert "seed: 42" in content
    assert 'model: "gpt-4o-mini"' in content
    assert "# Глава" in content
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_chapter_to_explicit_file(tmp_path: Path) -> None:
    """Можно указать конкретный файл."""
    target = save_chapter(
        tmp_path / "custom.md",
        "Текст",
        year_from=1,
        year_to=2,
    )

    assert target.name == "custom.md"
    assert target.is_file()


def test_key_does_not_leak_into_chapter(tmp_path: Path) -> None:
    """Ключ провайдера не попадает в сохранённую главу."""
    content = "В год 10 и год 11 всё спокойно."

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer super-secret-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = OpenAIClient(
        "super-secret-key",
        transport=httpx.MockTransport(handler),
    )
    writer = ChronicleWriter(client)

    text = writer.write_chapter(make_events(), 10, 11)
    target = save_chapter(tmp_path / "chapter.md", text, model=writer.model)

    saved = target.read_text(encoding="utf-8")
    assert "super-secret-key" not in saved
    assert content in saved


def test_model_property() -> None:
    """Модель берётся у клиента, если она есть."""
    assert ChronicleWriter(FakeClient("")).model is None
    assert ChronicleWriter(OpenAIClient("key", model="test-model")).model == "test-model"


def test_system_prompt_forbids_inventions() -> None:
    """Системный промпт запрещает выдумывать факты."""
    lowered = SYSTEM_PROMPT.casefold()
    assert "не выдумывай" in lowered
    assert "только" in lowered
