"""Тесты моделей ИИ-правителей."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rulers import (
    DiplomaticMessage,
    MessageKind,
    RulerProfile,
    RulerStyle,
    RulerThought,
    StandingOrder,
)
from worldsim.core.state import WorldConfig, WorldState


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int = 0,
) -> Faction:
    """Создаёт фракцию для тестов правителей."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
    )


def make_state(
    *,
    factions: tuple[Faction, ...] | None = None,
    rulers: tuple[RulerProfile, ...] = (),
    thoughts: tuple[RulerThought, ...] = (),
    orders: tuple[StandingOrder, ...] = (),
    messages: tuple[DiplomaticMessage, ...] = (),
) -> WorldState:
    """Создаёт мир с моделями правителей."""
    if factions is None:
        factions = (make_faction(),)
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
        for faction in factions:
            if faction.capital_tile_id == index:
                data["owner_id"] = faction.id
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        rulers=rulers,
        thoughts=thoughts,
        standing_orders=orders,
        diplomatic_messages=messages,
    )


def test_profile_and_enums() -> None:
    """Профиль правителя и стили валидируются."""
    profile = RulerProfile(
        faction_id=0,
        name="Король",
        style=RulerStyle.WARLORD,
        traits=("гордость",),
        decision_interval=2,
    )

    assert profile.style is RulerStyle.WARLORD
    assert profile.decision_interval == 2
    with pytest.raises(ValidationError):
        RulerProfile(faction_id=0, name="Король", decision_interval=0)


def test_thought_validation() -> None:
    """Текст мысли не может быть пустым."""
    with pytest.raises(ValidationError):
        RulerThought(id=0, faction_id=0, year=0, text="")
    thought = RulerThought(
        id=0,
        faction_id=0,
        year=3,
        text="Пора строить академию.",
        action="BUILD_ACADEMY",
        target_tile_id=1,
    )
    assert thought.action == "BUILD_ACADEMY"


def test_message_to_self_is_rejected() -> None:
    """Правитель не может писать сам себе."""
    with pytest.raises(ValidationError):
        DiplomaticMessage(
            id=0,
            year=0,
            sender_id=0,
            recipient_id=0,
            text="Привет",
        )


def test_state_accepts_ruler_models() -> None:
    """Снимок принимает правителя, мысль, приказ и сообщение."""
    first = make_faction()
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    profile = RulerProfile(faction_id=0, name="Король")
    thought = RulerThought(id=0, faction_id=0, year=0, text="Думаю.")
    order = StandingOrder(
        id=0,
        faction_id=0,
        kind="accumulate_gold",
        years_left=5,
        created_year=0,
    )
    message = DiplomaticMessage(
        id=0,
        year=0,
        sender_id=0,
        recipient_id=1,
        kind=MessageKind.PEACE,
        text="Предлагаю мир.",
        accepted=None,
    )

    state = make_state(
        factions=(first, second),
        rulers=(profile,),
        thoughts=(thought,),
        orders=(order,),
        messages=(message,),
    )

    assert state.rulers == (profile,)
    assert state.diplomatic_messages == (message,)


def test_unknown_faction_is_rejected() -> None:
    """Все ссылки на фракции проверяются."""
    with pytest.raises(ValidationError):
        make_state(rulers=(RulerProfile(faction_id=5, name="Призрак"),))
    with pytest.raises(ValidationError):
        make_state(thoughts=(RulerThought(id=0, faction_id=5, year=0, text="Текст"),))
    with pytest.raises(ValidationError):
        make_state(
            orders=(
                StandingOrder(
                    id=0,
                    faction_id=5,
                    kind="recruit",
                    years_left=1,
                    created_year=0,
                ),
            )
        )


def test_duplicate_ids_are_rejected() -> None:
    """Идентификаторы мыслей, приказов и сообщений уникальны."""
    with pytest.raises(ValidationError):
        make_state(
            thoughts=(
                RulerThought(id=0, faction_id=0, year=0, text="A"),
                RulerThought(id=0, faction_id=0, year=1, text="B"),
            )
        )
    with pytest.raises(ValidationError):
        make_state(
            orders=(
                StandingOrder(
                    id=0,
                    faction_id=0,
                    kind="recruit",
                    years_left=1,
                    created_year=0,
                ),
                StandingOrder(
                    id=0,
                    faction_id=0,
                    kind="defend",
                    years_left=1,
                    created_year=0,
                ),
            )
        )


def test_unknown_tile_is_rejected() -> None:
    """Ссылка на тайл вне карты отклоняется."""
    with pytest.raises(ValidationError):
        make_state(
            thoughts=(RulerThought(id=0, faction_id=0, year=0, text="Текст", target_tile_id=99),)
        )
    with pytest.raises(ValidationError):
        make_state(
            orders=(
                StandingOrder(
                    id=0,
                    faction_id=0,
                    kind="defend",
                    target_tile_id=99,
                    years_left=1,
                    created_year=0,
                ),
            )
        )


def test_old_json_without_ruler_fields_is_valid() -> None:
    """Старый JSON без полей правителей читается."""
    state = make_state()
    payload = state.model_dump()
    for key in ("rulers", "thoughts", "standing_orders", "diplomatic_messages"):
        payload.pop(key)

    restored = WorldState.model_validate(payload)

    assert restored.rulers == ()
    assert restored.thoughts == ()


def test_json_round_trip() -> None:
    """Модели правителей переживают JSON round-trip."""
    first = make_faction()
    second = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        factions=(first, second),
        rulers=(RulerProfile(faction_id=0, name="Король"),),
        thoughts=(RulerThought(id=0, faction_id=0, year=0, text="Мысль."),),
        messages=(
            DiplomaticMessage(
                id=0,
                year=0,
                sender_id=0,
                recipient_id=1,
                text="Мир?",
            ),
        ),
    )

    assert WorldState.from_json(state.to_json()) == state
