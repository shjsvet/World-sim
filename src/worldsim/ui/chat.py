"""Подготовка переписки правителей для интерфейса."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from worldsim.core.faction import Faction
from worldsim.core.rulers import DiplomaticMessage, MessageKind

_KIND_LABELS: dict[MessageKind, str] = {
    MessageKind.OFFER: "Предложение",
    MessageKind.ACCEPT: "Согласие",
    MessageKind.REJECT: "Отказ",
    MessageKind.THREAT: "Угроза",
    MessageKind.PEACE: "Мир",
    MessageKind.TRADE: "Торговля",
}


def kind_label(kind: MessageKind) -> str:
    """Человекочитаемый тип сообщения."""
    return _KIND_LABELS.get(kind, kind.value)


def filter_messages(
    messages: Iterable[DiplomaticMessage],
    *,
    sender_id: int | None = None,
    recipient_id: int | None = None,
) -> list[DiplomaticMessage]:
    """Фильтрует переписку по отправителю и получателю, сортируя по времени."""
    return sorted(
        (
            message
            for message in messages
            if (sender_id is None or message.sender_id == sender_id)
            and (recipient_id is None or message.recipient_id == recipient_id)
        ),
        key=lambda message: (message.year, message.id),
    )


def format_message(
    message: DiplomaticMessage,
    faction_names: Mapping[int, str],
) -> str:
    """Форматирует сообщение для карточки."""
    sender = faction_names.get(message.sender_id, f"Фракция {message.sender_id}")
    recipient = faction_names.get(message.recipient_id, f"Фракция {message.recipient_id}")
    return (
        f"**Год {message.year} · {sender} → {recipient}**\n\n"
        f"**{kind_label(message.kind)}:** {message.text}"
    )


def messages_to_markdown(
    messages: Iterable[DiplomaticMessage],
    factions: Iterable[Faction],
) -> str:
    """Собирает переписку в markdown-файл."""
    names = {faction.id: faction.name for faction in factions}
    ordered = filter_messages(messages)
    lines = ["# Переписка правителей", ""]
    for message in ordered:
        lines.append(format_message(message, names))
        lines.append("")
    if len(lines) == 2:
        lines.append("_Сообщений пока нет._")
        lines.append("")
    return "\n".join(lines)
