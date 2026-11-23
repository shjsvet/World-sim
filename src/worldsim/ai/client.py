"""Клиенты LLM для ИИ-функций WorldSim.

Ключи читаются только из переменных окружения и никогда не попадают в
``repr``, сообщения исключений или журналы. Сетевые вызовы выполняются через
``httpx``; в тестах подменяется транспорт.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from typing import Protocol, TypedDict, runtime_checkable

import httpx

DEFAULT_TIMEOUT = 30.0
RETRY_ATTEMPTS = 2
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GROQ_MODEL = "llama-3.1-70b-versatile"
DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"


class Message(TypedDict):
    """Сообщение чата."""

    role: str
    content: str


class AIUnavailableError(RuntimeError):
    """Провайдер ИИ не настроен или недоступен."""


@runtime_checkable
class LLMClient(Protocol):
    """Интерфейс клиента LLM."""

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Возвращает текст ответа модели."""
        ...


class _HttpLLMClient:
    """Общая часть HTTP-клиентов: повторы, таймаут и защита ключа."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleeper

    def __repr__(self) -> str:
        """Представление без ключа."""
        return f"{type(self).__name__}(model={self.model!r}, base_url={self.base_url!r})"

    def _headers(self) -> dict[str, str]:
        """Заголовки запроса; ключ не выводится в сообщениях."""
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        """Выполняет POST с двумя повторами на 429 и 5xx."""
        url = f"{self.base_url}{path}"
        for attempt in range(RETRY_ATTEMPTS + 1):
            try:
                with httpx.Client(transport=self._transport, timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=self._headers())
            except httpx.HTTPError as exc:
                if attempt < RETRY_ATTEMPTS:
                    self._sleep(0.5 * (2**attempt))
                    continue
                raise AIUnavailableError(
                    f"Сетевая ошибка провайдера: {type(exc).__name__}"
                ) from None

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < RETRY_ATTEMPTS:
                    self._sleep(0.5 * (2**attempt))
                    continue
                raise AIUnavailableError(
                    f"Провайдер вернул статус {response.status_code}"
                ) from None
            if response.status_code >= 400:
                raise AIUnavailableError(
                    f"Провайдер вернул статус {response.status_code}"
                ) from None

            try:
                data = response.json()
            except ValueError:
                raise AIUnavailableError("Провайдер вернул некорректный JSON") from None
            if not isinstance(data, dict):
                raise AIUnavailableError("Провайдер вернул некорректный ответ")
            return data
        raise AIUnavailableError("Провайдер недоступен")


class OpenAIClient(_HttpLLMClient):
    """OpenAI-совместимый клиент (``/chat/completions``)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = "https://api.openai.com/v1",
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            base_url=base_url,
            model=model,
            api_key=api_key,
            transport=transport,
            timeout=timeout,
            sleeper=sleeper,
        )

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Запрашивает ответ у OpenAI-совместимого провайдера."""
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post("/chat/completions", payload)
        return self._extract_content(data)

    @staticmethod
    def _extract_content(data: dict[str, object]) -> str:
        """Достаёт текст из ответа провайдера."""
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIUnavailableError("Провайдер вернул пустой ответ")
        first = choices[0]
        if not isinstance(first, dict):
            raise AIUnavailableError("Провайдер вернул некорректный ответ")
        message = first.get("message")
        if not isinstance(message, dict):
            raise AIUnavailableError("Провайдер вернул некорректный ответ")
        content = message.get("content")
        if not isinstance(content, str):
            raise AIUnavailableError("Провайдер вернул некорректный ответ")
        return content


class GroqClient(OpenAIClient):
    """Клиент Groq (OpenAI-совместимый API)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GROQ_MODEL,
        base_url: str = "https://api.groq.com/openai/v1",
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            api_key,
            model=model,
            base_url=base_url,
            transport=transport,
            timeout=timeout,
            sleeper=sleeper,
        )


class OllamaClient(_HttpLLMClient):
    """Клиент локального Ollama (``POST /api/chat``)."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_HOST,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            base_url=base_url,
            model=model,
            transport=transport,
            timeout=timeout,
            sleeper=sleeper,
        )

    def complete(
        self,
        messages: Sequence[Message],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Запрашивает ответ у локального Ollama."""
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload)
        message = data.get("message")
        if not isinstance(message, dict):
            raise AIUnavailableError("Ollama вернул некорректный ответ")
        content = message.get("content")
        if not isinstance(content, str):
            raise AIUnavailableError("Ollama вернул некорректный ответ")
        return content


def create_client(provider: str | None = None) -> LLMClient:
    """Создаёт клиент по провайдеру или автоопределению из окружения.

    Raises:
        AIUnavailableError: Если провайдер неизвестен или не настроен.
    """
    chosen = (provider or os.environ.get("WORLDSIM_AI_PROVIDER") or "").strip().lower()
    if chosen == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise AIUnavailableError("не задан OPENAI_API_KEY")
        return OpenAIClient(
            key,
            model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        )
    if chosen == "groq":
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise AIUnavailableError("не задан GROQ_API_KEY")
        return GroqClient(
            key,
            model=os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        )
    if chosen == "ollama":
        return OllamaClient(
            model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            base_url=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
        )
    if chosen:
        raise AIUnavailableError(f"неизвестный провайдер ИИ: {chosen}")

    if os.environ.get("OPENAI_API_KEY"):
        return create_client("openai")
    if os.environ.get("GROQ_API_KEY"):
        return create_client("groq")
    if os.environ.get("OLLAMA_HOST"):
        return create_client("ollama")
    raise AIUnavailableError("провайдер ИИ не настроен")
