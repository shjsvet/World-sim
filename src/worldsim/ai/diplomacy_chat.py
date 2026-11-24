"""Переписка ИИ-правителей: предложения мира и торговли."""

from __future__ import annotations

import json

from worldsim.ai.client import AIUnavailableError, LLMClient, Message
from worldsim.core.faction import Faction
from worldsim.core.rulers import DiplomaticMessage, MessageKind
from worldsim.core.state import WorldState

SYSTEM_PROMPT = (
    "Ты — ИИ-правитель фракции. Напиши одно дипломатическое сообщение другому "
    "правителю. Верни строго JSON без markdown: "
    '{"kind": "offer|peace|trade", "text": "сообщение на русском, 1–300 символов"}. '
    "Опирайся только на переданные факты, не выдумывай события."
)

_TOPIC_KINDS: dict[str, MessageKind] = {
    "peace": MessageKind.PEACE,
    "мир": MessageKind.PEACE,
    "trade": MessageKind.TRADE,
    "торговля": MessageKind.TRADE,
    "offer": MessageKind.OFFER,
    "союз": MessageKind.OFFER,
}

_FALLBACK_TEXT: dict[MessageKind, str] = {
    MessageKind.PEACE: "Предлагаю перемирие: война истощает обе стороны.",
    MessageKind.TRADE: "У нас есть избыток еды — предлагаю обмен на золото.",
    MessageKind.OFFER: "Предлагаю обсудить союз и общие границы.",
}


class DiplomacyChat:
    """Генерирует одно предложение от правителя правителю."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client

    def open_channel(
        self,
        sender: Faction,
        recipient: Faction,
        topic: str,
        state: WorldState,
    ) -> tuple[DiplomaticMessage, ...]:
        """Возвращает сообщение-предложение (или fallback без ИИ).

        Raises:
            ValueError: Если фракции совпадают или отсутствуют в снимке.
        """
        faction_ids = {faction.id for faction in state.factions}
        if sender.id == recipient.id:
            raise ValueError("нельзя открыть канал с самим собой")
        if sender.id not in faction_ids or recipient.id not in faction_ids:
            raise ValueError("фракция отсутствует в снимке")

        kind = _TOPIC_KINDS.get(topic.strip().lower(), MessageKind.OFFER)
        text = self._ask(sender, recipient, topic, state, kind)
        message = DiplomaticMessage(
            id=max((item.id for item in state.diplomatic_messages), default=-1) + 1,
            year=state.year,
            sender_id=sender.id,
            recipient_id=recipient.id,
            kind=kind,
            text=text,
            accepted=None,
        )
        return (message,)

    def _ask(
        self,
        sender: Faction,
        recipient: Faction,
        topic: str,
        state: WorldState,
        kind: MessageKind,
    ) -> str:
        """Спрашивает ИИ или возвращает шаблон."""
        if self._client is None:
            return _FALLBACK_TEXT[kind]
        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(
                role="user",
                content=json.dumps(
                    {
                        "topic": topic,
                        "sender": _faction_brief(sender),
                        "recipient": _faction_brief(recipient),
                        "year": state.year,
                        "war": _war_status(state, sender.id, recipient.id),
                        "allowed_kinds": ["offer", "peace", "trade"],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        ]
        try:
            answer = self._client.complete(messages, json_mode=True)
            payload = json.loads(answer)
            if not isinstance(payload, dict):
                raise ValueError("ожидался JSON-объект")
            text = str(payload.get("text", "")).strip()
            if not text:
                raise ValueError("пустой текст")
            payload_kind = str(payload.get("kind", kind.value))
            parsed_kind = MessageKind(payload_kind)
            if parsed_kind not in {MessageKind.OFFER, MessageKind.PEACE, MessageKind.TRADE}:
                raise ValueError("недопустимый тип сообщения")
            return text[:1000]
        except (AIUnavailableError, ValueError, json.JSONDecodeError):
            return _FALLBACK_TEXT[kind]


def _faction_brief(faction: Faction) -> dict[str, object]:
    """Краткая сводка фракции для промпта."""
    return {
        "id": faction.id,
        "name": faction.name,
        "culture": faction.culture,
        "food": faction.food_stockpile,
        "treasury": faction.treasury,
        "army": faction.army_size,
        "morale": faction.morale,
    }


def _war_status(state: WorldState, first_id: int, second_id: int) -> str:
    """Описывает отношения двух фракций."""
    for war in state.wars:
        if {war.attacker_id, war.defender_id} != {first_id, second_id}:
            continue
        if war.active:
            return "война"
        if war.truce_until_year is not None and war.truce_until_year >= state.year:
            return f"перемирие до {war.truce_until_year}"
    return "мир"
