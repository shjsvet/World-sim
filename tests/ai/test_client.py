"""Тесты клиента LLM на фейковом транспорте (без сети)."""

from __future__ import annotations

import json

import httpx
import pytest

from worldsim.ai.client import (
    DEFAULT_TIMEOUT,
    AIUnavailableError,
    GroqClient,
    LLMClient,
    Message,
    OllamaClient,
    OpenAIClient,
    create_client,
)


def make_handler(
    responses: list[httpx.Response],
    captured: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    """Создаёт транспорт, отдающий ответы по очереди."""
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return queue.pop(0) if queue else httpx.Response(200, json={})

    return httpx.MockTransport(handler)


def make_client(
    responses: list[httpx.Response],
    *,
    api_key: str = "test-key",
    captured: list[httpx.Request] | None = None,
    delays: list[float] | None = None,
) -> OpenAIClient:
    """Создаёт OpenAI-клиент с фейковым транспортом."""
    return OpenAIClient(
        api_key,
        transport=make_handler(responses, captured),
        sleeper=(delays.append if delays is not None else lambda _: None),
    )


def test_openai_success_and_request_shape() -> None:
    """Успешный ответ OpenAI и корректный запрос."""
    captured: list[httpx.Request] = []
    client = make_client(
        [httpx.Response(200, json={"choices": [{"message": {"content": "привет"}}]})],
        captured=captured,
    )

    result = client.complete([Message(role="user", content="привет")])

    assert result == "привет"
    request = captured[0]
    assert str(request.url) == "https://api.openai.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["model"] == "gpt-4o-mini"
    assert body["messages"] == [{"role": "user", "content": "привет"}]
    assert body["temperature"] == 0.7
    assert "response_format" not in body


def test_json_mode_adds_response_format() -> None:
    """JSON-режим включает response_format."""
    captured: list[httpx.Request] = []
    client = make_client(
        [httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})],
        captured=captured,
    )

    client.complete([Message(role="user", content="json")], json_mode=True, temperature=0.2)

    body = json.loads(captured[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0.2


def test_retry_on_500() -> None:
    """500 повторяется с экспоненциальной задержкой."""
    delays: list[float] = []
    captured: list[httpx.Request] = []
    client = make_client(
        [
            httpx.Response(500),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ],
        captured=captured,
        delays=delays,
    )

    result = client.complete([Message(role="user", content="hi")])

    assert result == "ok"
    assert len(captured) == 2
    assert delays == [0.5]


def test_retry_on_429() -> None:
    """429 повторяется, затем успех."""
    captured: list[httpx.Request] = []
    client = make_client(
        [
            httpx.Response(429),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ],
        captured=captured,
    )

    assert client.complete([Message(role="user", content="hi")]) == "ok"
    assert len(captured) == 2


def test_retries_are_exhausted() -> None:
    """После двух повторов ошибка провайдера."""
    delays: list[float] = []
    captured: list[httpx.Request] = []
    client = make_client(
        [httpx.Response(500), httpx.Response(500), httpx.Response(500)],
        captured=captured,
        delays=delays,
    )

    with pytest.raises(AIUnavailableError):
        client.complete([Message(role="user", content="hi")])

    assert len(captured) == 3
    assert delays == [0.5, 1.0]


def test_client_error_is_not_retried() -> None:
    """400 не повторяется."""
    captured: list[httpx.Request] = []
    client = make_client(
        [httpx.Response(400)],
        captured=captured,
    )

    with pytest.raises(AIUnavailableError):
        client.complete([Message(role="user", content="hi")])

    assert len(captured) == 1


def test_ollama_success_and_payload() -> None:
    """Ollama использует /api/chat и stream=false."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"message": {"content": "ответ"}})

    client = OllamaClient(transport=httpx.MockTransport(handler))

    result = client.complete([Message(role="user", content="hi")], temperature=0.3)

    assert result == "ответ"
    request = captured[0]
    assert str(request.url) == "http://127.0.0.1:11434/api/chat"
    body = json.loads(request.content)
    assert body["stream"] is False
    assert body["options"] == {"temperature": 0.3}
    assert "format" not in body


def test_ollama_json_mode() -> None:
    """JSON-режим Ollama включает format=json."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"message": {"content": "{}"}})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    client.complete([Message(role="user", content="json")], json_mode=True)

    assert json.loads(captured[0].content)["format"] == "json"


def test_key_is_not_leaked() -> None:
    """Ключ не попадает в repr и текст исключения."""
    client = make_client([httpx.Response(500), httpx.Response(500), httpx.Response(500)])

    with pytest.raises(AIUnavailableError) as error:
        client.complete([Message(role="user", content="hi")])

    assert "test-key" not in repr(client)
    assert "test-key" not in str(error.value)
    assert "Authorization" not in str(error.value)


def test_timeout_default() -> None:
    """Таймаут по умолчанию — 30 секунд."""
    client = make_client([])

    assert client.timeout == DEFAULT_TIMEOUT == 30.0


def test_client_implements_protocol() -> None:
    """Клиенты структурно реализуют LLMClient."""
    client = make_client([])

    assert isinstance(client, LLMClient)
    assert isinstance(OllamaClient(), LLMClient)
    assert isinstance(GroqClient("key"), LLMClient)


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Убирает переменные окружения провайдеров."""
    for name in (
        "WORLDSIM_AI_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "OLLAMA_HOST",
        "OLLAMA_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_create_client_auto_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Автоопределение OpenAI по ключу."""
    clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "key")

    client = create_client()

    assert isinstance(client, OpenAIClient)
    assert client.model == "gpt-4o-mini"


def test_create_client_auto_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    """Автоопределение Groq по ключу."""
    clear_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "key")

    assert isinstance(create_client(), GroqClient)


def test_create_client_auto_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """Автоопределение Ollama по OLLAMA_HOST."""
    clear_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")

    assert isinstance(create_client(), OllamaClient)


def test_create_client_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без конфигурации — AIUnavailableError."""
    clear_env(monkeypatch)

    with pytest.raises(AIUnavailableError):
        create_client()


def test_create_client_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Явный провайдер без ключа — ошибка."""
    clear_env(monkeypatch)

    with pytest.raises(AIUnavailableError):
        create_client("openai")
    with pytest.raises(AIUnavailableError):
        create_client("groq")


def test_create_client_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Неизвестный провайдер отклоняется."""
    clear_env(monkeypatch)

    with pytest.raises(AIUnavailableError):
        create_client("unknown")


def test_create_client_env_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Провайдер берётся из WORLDSIM_AI_PROVIDER."""
    clear_env(monkeypatch)
    monkeypatch.setenv("WORLDSIM_AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_HOST", "http://example:11434")

    client = create_client()

    assert isinstance(client, OllamaClient)
    assert client.base_url == "http://example:11434"
