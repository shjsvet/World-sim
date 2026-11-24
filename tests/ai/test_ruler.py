"""Тесты решений ИИ-правителя."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from worldsim.ai.client import AIUnavailableError, Message
from worldsim.ai.ruler import (
    LLMRuler,
    RulerAction,
    RulerDecision,
    fallback_decision,
)
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.state import WorldConfig, WorldState


class FakeClient:
    """Клиент с фиксированным ответом или ошибкой."""

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


def make_faction(*, food: float = 100.0, morale: float = 0.8, treasury: float = 100.0) -> Faction:
    """Создаёт фракцию для тестов правителя."""
    return Faction(
        id=0,
        name="Альянс",
        color="#112233",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=0,
        food_stockpile=food,
        morale=morale,
        treasury=treasury,
        army_size=10.0,
    )


def make_state(
    faction: Faction,
    *,
    overrides: dict[int, dict[str, object]] | None = None,
) -> WorldState:
    """Создаёт мир с одной фракцией."""
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
        if overrides is not None:
            data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=1),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=(faction,),
    )


def test_successful_llm_decision() -> None:
    """Валидный JSON клиента превращается в решение."""
    faction = make_faction()
    state = make_state(faction, overrides={0: {"owner_id": 0}})
    answer = json.dumps(
        {
            "action": "build_academy",
            "target_tile_id": 1,
            "amount": 100,
            "message": "Строим академию",
            "thought": "Мои маги готовы учить новых чародеев.",
            "confidence": 0.9,
        },
        ensure_ascii=False,
    )
    client = FakeClient(answer)

    decision = LLMRuler(client).decide(state, faction)

    assert decision.action is RulerAction.BUILD_ACADEMY
    assert decision.target_tile_id == 1
    assert decision.amount == 100
    assert "маги" in decision.thought
    assert len(client.calls) == 1
    system_prompt = client.calls[0][0]["content"]
    assert "JSON" in system_prompt
    assert "Альянс" in client.calls[0][1]["content"]


def test_malformed_json_falls_back() -> None:
    """Битый JSON уходит в fallback."""
    faction = make_faction(food=0.0)
    state = make_state(
        faction,
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.FOOD,
                "resource_depletion": 50.0,
                "resource_amount": 10.0,
            }
        },
    )

    decision = LLMRuler(FakeClient("{ это не json")).decide(state, faction)

    assert decision.action is RulerAction.EXTRACT_RESOURCE
    assert decision.target_tile_id == 0
    assert decision.thought


def test_unknown_action_falls_back() -> None:
    """Неизвестное действие отклоняется и уходит в fallback."""
    faction = make_faction()
    state = make_state(faction, overrides={0: {"owner_id": 0}})
    answer = json.dumps(
        {"action": "dance", "thought": "Танцую", "confidence": 0.5},
        ensure_ascii=False,
    )

    decision = LLMRuler(FakeClient(answer)).decide(state, faction)

    assert decision.action is RulerAction.HOLD


def test_empty_thought_is_rejected() -> None:
    """Пустая мысль не проходит валидацию решения."""
    with pytest.raises(ValidationError):
        RulerDecision(action=RulerAction.HOLD, thought="")
    faction = make_faction()
    state = make_state(faction, overrides={0: {"owner_id": 0}})
    answer = json.dumps(
        {"action": "hold", "thought": "", "confidence": 0.5},
        ensure_ascii=False,
    )

    decision = LLMRuler(FakeClient(answer)).decide(state, faction)

    assert decision.action is RulerAction.HOLD
    assert decision.thought


def test_client_error_falls_back() -> None:
    """Ошибка клиента не роняет решение."""
    faction = make_faction(morale=0.2)
    state = make_state(faction, overrides={0: {"owner_id": 0}})

    decision = LLMRuler(FakeClient(AIUnavailableError("нет ключа"))).decide(state, faction)

    assert decision.action is RulerAction.PROPOSE_PEACE


def test_fallback_for_low_morale() -> None:
    """Низкая мораль даёт предложение мира."""
    faction = make_faction(morale=0.2)
    state = make_state(faction, overrides={0: {"owner_id": 0}})

    decision = fallback_decision(state, faction)

    assert decision.action is RulerAction.PROPOSE_PEACE
    assert decision.thought


def test_fallback_without_emergency_is_hold() -> None:
    """Без угроз правитель просто ждёт."""
    faction = make_faction()
    state = make_state(faction, overrides={0: {"owner_id": 0}})

    decision = fallback_decision(state, faction)

    assert decision.action is RulerAction.HOLD


def test_target_outside_map_falls_back() -> None:
    """Цель вне карты отклоняется."""
    faction = make_faction()
    state = make_state(faction, overrides={0: {"owner_id": 0}})
    answer = json.dumps(
        {
            "action": "move_army",
            "target_tile_id": 999,
            "thought": "Иду в поход",
            "confidence": 0.5,
        },
        ensure_ascii=False,
    )

    decision = LLMRuler(FakeClient(answer)).decide(state, faction)

    assert decision.action is RulerAction.HOLD


def test_same_input_gives_same_decision() -> None:
    """Одинаковый вход и ответ дают одинаковое решение."""
    faction = make_faction()
    state = make_state(faction, overrides={0: {"owner_id": 0}})
    answer = json.dumps(
        {
            "action": "recruit",
            "amount": 5,
            "thought": "Наберу солдат.",
            "confidence": 0.5,
        },
        ensure_ascii=False,
    )

    first = LLMRuler(FakeClient(answer)).decide(state, faction)
    second = LLMRuler(FakeClient(answer)).decide(state, faction)

    assert first == second


def test_confidence_is_bounded() -> None:
    """Уверенность ограничена диапазоном 0–1."""
    with pytest.raises(ValidationError):
        RulerDecision(action=RulerAction.HOLD, thought="Мысль", confidence=1.5)
