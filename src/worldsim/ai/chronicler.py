"""ИИ-хронист: главы летописи по событиям мира."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from worldsim.ai.client import AIUnavailableError, LLMClient, Message
from worldsim.core.chronicle import Chronicle
from worldsim.core.events import Event

SYSTEM_PROMPT = (
    "Ты — хронист мира. Напиши главу летописи на русском языке объёмом "
    "400–800 слов. Используй только факты из переданного JSON событий: "
    "годы, типы событий, фракции и severity. Не выдумывай события, имена, "
    "цифры и причины, которых нет в данных. Не добавляй заглушки и списки."
)

_PLACEHOLDERS = ("lorem ipsum", "todo", "заглушка", "placeholder", "tbd")


def fallback_chapter(
    events: Sequence[Event],
    year_from: int | None = None,
    year_to: int | None = None,
) -> str:
    """Собирает главу из markdown-летописи без обращения к ИИ."""
    chronicle = Chronicle()
    for event in events:
        chronicle.add(event)
    title = "Летопись"
    if year_from is not None and year_to is not None:
        title = f"Летопись, годы {year_from}–{year_to}"
    body = chronicle.to_markdown() if events else "Событий за этот период не было."
    return f"# {title}\n\n{body}"


class ChronicleWriter:
    """Пишет главы летописи через LLM с проверкой и fallback."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def write_chapter(
        self,
        events: Sequence[Event],
        year_from: int,
        year_to: int,
    ) -> str:
        """Возвращает главу по событиям периода.

        Если ИИ недоступен или ответ не проходит проверку, возвращается
        глава из ``fallback_chapter``.
        """
        if not events:
            return fallback_chapter(events, year_from, year_to)

        payload = [
            {
                "year": event.year,
                "type": event.type.value,
                "factions": list(event.faction_ids),
                "severity": event.severity,
            }
            for event in events
        ]
        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    f"Годы {year_from}–{year_to}. События (JSON): "
                    f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}. "
                    "Напиши главу 400–800 слов на русском, только по этим данным."
                ),
            ),
        ]
        try:
            text = self._client.complete(messages)
        except AIUnavailableError:
            return fallback_chapter(events, year_from, year_to)

        if not self._is_valid(text, year_from, year_to):
            return fallback_chapter(events, year_from, year_to)
        return text.strip()

    @staticmethod
    def _is_valid(text: str, year_from: int, year_to: int) -> bool:
        """Проверяет ответ: непустой, все годы, без заглушек."""
        if not text.strip():
            return False
        lowered = text.casefold()
        if any(marker in lowered for marker in _PLACEHOLDERS):
            return False
        return all(str(year) in text for year in range(year_from, year_to + 1))

    @property
    def model(self) -> str | None:
        """Имя модели клиента, если оно есть."""
        model = getattr(self._client, "model", None)
        return model if isinstance(model, str) else None


def save_chapter(
    path: Path,
    text: str,
    *,
    year_from: int = 0,
    year_to: int = 0,
    seed: int | None = None,
    model: str | None = None,
) -> Path:
    """Атомарно сохраняет главу с YAML-front-matter.

    Если ``path`` — каталог, файл называется
    ``chapter_<year_from>_<year_to>.md``.
    """
    target = Path(path)
    if target.suffix == "":
        target = target / f"chapter_{year_from}_{year_to}.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"year_from: {year_from}",
        f"year_to: {year_to}",
    ]
    if seed is not None:
        lines.append(f"seed: {seed}")
    if model is not None:
        lines.append(f"model: {json.dumps(model, ensure_ascii=False)}")
    lines.extend(["---", "", text.strip(), ""])

    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, target)
    return target
