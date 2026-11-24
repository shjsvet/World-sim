"""Тесты хелперов переписки правителей."""

from __future__ import annotations

from worldsim.core.faction import Faction, Ideology
from worldsim.core.rulers import DiplomaticMessage, MessageKind
from worldsim.ui.chat import (
    filter_messages,
    format_message,
    kind_label,
    messages_to_markdown,
)


def make_faction(faction_id: int, name: str) -> Faction:
    """Создаёт фракцию для UI-тестов."""
    return Faction(
        id=faction_id,
        name=name,
        color="#112233",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=faction_id,
    )


def make_message(
    message_id: int,
    *,
    sender: int = 0,
    recipient: int = 1,
    year: int = 0,
    kind: MessageKind = MessageKind.OFFER,
    text: str = "Предложение.",
) -> DiplomaticMessage:
    """Создаёт сообщение."""
    return DiplomaticMessage(
        id=message_id,
        year=year,
        sender_id=sender,
        recipient_id=recipient,
        kind=kind,
        text=text,
    )


def test_filter_messages_sorts_and_filters() -> None:
    """Фильтр по отправителю и получателю сохраняет хронологию."""
    messages = (
        make_message(2, year=5),
        make_message(0, year=1),
        make_message(1, sender=1, recipient=0, year=3),
    )

    filtered = filter_messages(messages, sender_id=0)
    all_messages = filter_messages(messages)

    assert [message.id for message in filtered] == [0, 2]
    assert [message.id for message in all_messages] == [0, 1, 2]


def test_filter_by_recipient() -> None:
    """Фильтр по получателю оставляет входящие."""
    messages = (
        make_message(0, sender=0, recipient=1),
        make_message(1, sender=1, recipient=0),
    )

    filtered = filter_messages(messages, recipient_id=0)

    assert [message.id for message in filtered] == [1]


def test_format_message_contains_participants() -> None:
    """Карточка сообщения содержит год, имена и текст."""
    message = make_message(
        0,
        year=7,
        kind=MessageKind.PEACE,
        text="Давайте жить мирно.",
    )

    text = format_message(message, {0: "Альянс", 1: "Орда"})

    assert "Год 7" in text
    assert "Альянс → Орда" in text
    assert "Мир" in text
    assert "Давайте жить мирно." in text


def test_kind_label() -> None:
    """Тип сообщения переводится на русский."""
    assert kind_label(MessageKind.TRADE) == "Торговля"
    assert kind_label(MessageKind.THREAT) == "Угроза"


def test_messages_to_markdown() -> None:
    """Markdown содержит заголовок и сообщения."""
    factions = (make_faction(0, "Альянс"), make_faction(1, "Орда"))
    messages = (
        make_message(0, text="Первое."),
        make_message(1, sender=1, recipient=0, year=1, text="Второе."),
    )

    text = messages_to_markdown(messages, factions)

    assert "# Переписка правителей" in text
    assert "Первое." in text
    assert "Второе." in text


def test_empty_markdown() -> None:
    """Пустая переписка содержит пояснение."""
    text = messages_to_markdown((), (make_faction(0, "Альянс"),))

    assert "Сообщений пока нет" in text
