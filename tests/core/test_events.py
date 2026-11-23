"""Тесты модели события."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from worldsim.core.events import Event, EventType


def make_event(**overrides: object) -> Event:
    """Создаёт событие с минимально допустимыми полями."""
    payload: dict[str, object] = {
        "id": 0,
        "year": 0,
        "type": EventType.CUSTOM,
        "summary": "сухое событие",
        "severity": 0.0,
    }
    payload.update(overrides)
    return Event.model_validate(payload)


def test_event_type_values() -> None:
    """Типы событий покрывают все механики и сериализуются в snake_case."""
    assert len(EventType) == 26
    for event_type in EventType:
        assert event_type.value == event_type.value.lower()
    assert EventType.WAR.value == "war"
    assert EventType.PEACE_TREATY.value == "peace_treaty"
    assert EventType.LEY_LINE_CLAIMED.value == "ley_line_claimed"


def test_event_defaults() -> None:
    """Необязательные поля пусты по умолчанию."""
    event = make_event()

    assert event.id == 0
    assert event.year == 0
    assert event.type is EventType.CUSTOM
    assert event.summary == "сухое событие"
    assert event.tile_ids == ()
    assert event.faction_ids == ()
    assert event.severity == 0.0
    assert event.payload == {}


@pytest.mark.parametrize("severity", [1.1, -0.1])
def test_severity_bounds(severity: float) -> None:
    """Severity ограничен диапазоном [0, 1]."""
    with pytest.raises(ValidationError):
        make_event(severity=severity)


@pytest.mark.parametrize("field,value", [("id", -1), ("year", -1)])
def test_non_negative_ids(field: str, value: int) -> None:
    """Идентификатор и год не могут быть отрицательными."""
    with pytest.raises(ValidationError):
        make_event(**{field: value})


@pytest.mark.parametrize("summary", ["", "   "])
def test_empty_summary_is_rejected(summary: str) -> None:
    """Пустой или пробельный summary отклоняется."""
    with pytest.raises(ValidationError):
        make_event(summary=summary)


def test_summary_length_and_trimming() -> None:
    """Summary обрезается по краям и не превышает 300 символов."""
    assert make_event(summary="  текст  ").summary == "текст"
    assert len(make_event(summary="x" * 300).summary) == 300
    with pytest.raises(ValidationError):
        make_event(summary="x" * 301)


def test_negative_ids_in_tuples_are_rejected() -> None:
    """Отрицательные идентификаторы тайлов и фракций отклоняются."""
    with pytest.raises(ValidationError):
        make_event(tile_ids=(-1,))
    with pytest.raises(ValidationError):
        make_event(faction_ids=(-2,))


def test_payload_validation() -> None:
    """Пустые ключи и несериализуемые значения отклоняются."""
    with pytest.raises(ValidationError):
        make_event(payload={"": 1})
    with pytest.raises(ValidationError):
        make_event(payload={"x": [1, 2]})


def test_event_is_frozen() -> None:
    """Событие неизменяемо."""
    event = make_event()

    with pytest.raises(ValidationError):
        event.severity = 0.5  # type: ignore[misc]


def test_json_round_trip() -> None:
    """Событие полностью сериализуется и восстанавливается."""
    event = make_event(tile_ids=(1, 2), faction_ids=(3,), severity=0.25, payload={"x": 1})
    payload = event.model_dump_json()
    restored = Event.model_validate_json(payload)

    assert restored == event
    assert restored.type is EventType.CUSTOM


def test_as_dict_is_json_compatible() -> None:
    """``as_dict`` отдаёт словарь, который сразу сериализуется в JSON."""
    event = Event.war(year=5, attacker_id=1, defender_id=2, tile_id=10)
    data = event.as_dict()

    assert data["type"] == "war"
    assert data["payload"] == {"attacker_id": 1, "defender_id": 2}
    assert json.loads(json.dumps(data)) == data


def test_plague_factory() -> None:
    """Фабрика эпидемии заполняет тип, тайлы и severity."""
    event = Event.plague(year=7, tile_ids=[1, 2], severity=0.4, event_id=3)

    assert event.id == 3
    assert event.type is EventType.PLAGUE
    assert event.tile_ids == (1, 2)
    assert event.severity == pytest.approx(0.4)
    assert "Эпидемия" in event.summary


def test_expansion_factory() -> None:
    """Фабрика экспансии заполняет фракцию и тайл."""
    event = Event.expansion(year=2, faction_id=1, tile_id=5)

    assert event.type is EventType.EXPANSION
    assert event.faction_ids == (1,)
    assert event.tile_ids == (5,)
    assert "Фракция 1" in event.summary


def test_war_factory() -> None:
    """Фабрика войны кладёт участников в поля и payload."""
    event = Event.war(year=4, attacker_id=1, defender_id=2, tile_id=9, severity=0.8)

    assert event.type is EventType.WAR
    assert event.faction_ids == (1, 2)
    assert event.tile_ids == (9,)
    assert event.payload == {"attacker_id": 1, "defender_id": 2}
    assert "Война" in event.summary


def test_starvation_factory() -> None:
    """Фабрика голода фиксирует фракцию и потери."""
    event = Event.starvation(year=3, faction_id=2, severity=0.2)

    assert event.type is EventType.STARVATION
    assert event.faction_ids == (2,)
    assert "Голод" in event.summary


def test_peace_factory() -> None:
    """Фабрика мира фиксирует участников."""
    event = Event.peace(year=8, faction_ids=[1, 2])

    assert event.type is EventType.PEACE_TREATY
    assert event.faction_ids == (1, 2)
    assert "Мир" in event.summary
