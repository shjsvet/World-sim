"""Тесты переписки ИИ-правителей."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from worldsim.ai.client import AIUnavailableError, Message
from worldsim.ai.diplomacy_chat import DiplomacyChat
from worldsim.ai.orchestrator import AIRulerOrchestrator
from worldsim.core.chronicle import Chronicle
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rulers import DiplomaticMessage, MessageKind
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.ai_ruler import AIRulerRule


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
        """Запоминает промпт и возвращает ответ."""
        self.calls.append(list(messages))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_faction(faction_id: int, name: str) -> Faction:
    """Создаёт фракцию для переписки."""
    return Faction(
        id=faction_id,
        name=name,
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=faction_id,
        food_stockpile=100.0,
        treasury=100.0,
    )


def make_state(*, messages: tuple[DiplomaticMessage, ...] = ()) -> WorldState:
    """Создаёт мир с двумя фракциями."""
    factions = (make_faction(0, "Альянс"), make_faction(1, "Орда"))
    tiles: list[RegionData] = []
    for index in range(16):
        data: dict[str, object] = {
            "id": index,
            "x": index % 4,
            "y": index // 4,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": 100,
            "population_capacity": 1_000,
        }
        if index < 2:
            data["owner_id"] = index
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=2),
        year=3,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        diplomatic_messages=messages,
    )


def test_llm_message_success() -> None:
    """Валидный JSON превращается в сообщение."""
    state = make_state()
    sender, recipient = state.factions
    client = FakeClient(json.dumps({"kind": "peace", "text": "Предлагаю мир."}, ensure_ascii=False))

    messages = DiplomacyChat(client).open_channel(sender, recipient, "peace", state)

    assert len(messages) == 1
    message = messages[0]
    assert message.kind is MessageKind.PEACE
    assert message.text == "Предлагаю мир."
    assert (message.sender_id, message.recipient_id) == (0, 1)
    assert message.year == 3
    assert message.accepted is None
    assert "Альянс" in client.calls[0][1]["content"]
    assert "Орда" in client.calls[0][1]["content"]


def test_fallback_without_client() -> None:
    """Без клиента возвращается шаблонное предложение."""
    state = make_state()
    sender, recipient = state.factions

    messages = DiplomacyChat().open_channel(sender, recipient, "trade", state)

    assert messages[0].kind is MessageKind.TRADE
    assert "обмен" in messages[0].text.lower()


def test_malformed_answer_falls_back() -> None:
    """Битый JSON уходит в шаблон."""
    state = make_state()
    sender, recipient = state.factions

    messages = DiplomacyChat(FakeClient("{oops")).open_channel(sender, recipient, "peace", state)

    assert messages[0].kind is MessageKind.PEACE
    assert "перемирие" in messages[0].text.lower()


def test_client_error_falls_back() -> None:
    """Ошибка клиента не роняет переписку."""
    state = make_state()
    sender, recipient = state.factions

    messages = DiplomacyChat(FakeClient(AIUnavailableError("нет ключа"))).open_channel(
        sender, recipient, "peace", state
    )

    assert messages[0].kind is MessageKind.PEACE


def test_same_faction_is_rejected() -> None:
    """Нельзя писать самому себе."""
    state = make_state()
    sender = state.factions[0]

    with pytest.raises(ValueError):
        DiplomacyChat().open_channel(sender, sender, "peace", state)


def test_unknown_faction_is_rejected() -> None:
    """Неизвестная фракция отклоняется."""
    state = make_state()
    sender = state.factions[0]
    stranger = make_faction(9, "Призрак")

    with pytest.raises(ValueError):
        DiplomacyChat().open_channel(sender, stranger, "peace", state)


def test_message_id_continues_existing_sequence() -> None:
    """Новое сообщение получает следующий id."""
    existing = DiplomaticMessage(
        id=4,
        year=1,
        sender_id=0,
        recipient_id=1,
        text="Старое сообщение.",
    )
    state = make_state(messages=(existing,))
    sender, recipient = state.factions

    messages = DiplomacyChat().open_channel(sender, recipient, "peace", state)

    assert messages[0].id == 5


def test_orchestrator_records_channel() -> None:
    """Оркестратор сохраняет сообщение в снимок."""
    state = make_state()
    engine = SimulationEngine([AIRulerRule()], Chronicle(), initial_state=state)

    messages = AIRulerOrchestrator().open_channel(engine, 0, 1, "peace")

    assert len(messages) == 1
    assert engine.state.diplomatic_messages == messages
