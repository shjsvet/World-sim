"""Тесты маршей армий."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction, RulerDecision
from worldsim.core.army import ArmyMarch, march_duration
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules import AICommand, StepContext
from worldsim.engine.rules.ai_ruler import AIRulerRule
from worldsim.engine.rules.march import MarchRule


def make_faction(*, army: float = 50.0, capital: int = 0) -> Faction:
    """Создаёт фракцию для марша."""
    return Faction(
        id=0,
        name="Альянс",
        color="#112233",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        army_size=army,
    )


def make_state(
    *,
    faction: Faction | None = None,
    presence: int = 20,
    marches: tuple[ArmyMarch, ...] = (),
    target_owner: int | None = 0,
) -> WorldState:
    """Создаёт карту с исходным гарнизоном и целью."""
    if faction is None:
        faction = make_faction()
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
        if index == 0:
            data["owner_id"] = 0
            data["army_presence"] = presence
        elif index == 3 and target_owner is not None:
            data["owner_id"] = target_owner
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=1),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=(faction,),
        army_marches=marches,
    )


def test_march_model_validation() -> None:
    """Марш требует разные тайлы и корректный срок."""
    march = ArmyMarch(
        id=0,
        faction_id=0,
        from_tile=0,
        to_tile=3,
        amount=5,
        departure_year=0,
        arrival_year=2,
    )

    assert march.arrival_year == 2


def test_march_duration_is_positive_and_grows() -> None:
    """Дальний марш идёт не меньше ближнего."""
    state = make_state()

    near = march_duration(state, 0, 1)
    far = march_duration(state, 0, 3)

    assert near >= 1
    assert far >= near


def test_ai_issues_march() -> None:
    """MOVE_ARMY снимает гарнизон и создаёт марш."""
    state = make_state()
    decision = RulerDecision(
        action=RulerAction.MOVE_ARMY,
        target_tile_id=3,
        amount=10,
        thought="Иду на восток.",
        confidence=0.5,
    )
    context = StepContext(
        year=0,
        config=state.config,
        rng=Rng(1),
        ai_decisions=[AICommand(0, decision)],
    )

    outcome = AIRulerRule().apply(state, context)

    assert outcome.army_marches is not None
    march = outcome.army_marches[0]
    assert march.amount == 10
    assert march.from_tile == 0
    assert march.to_tile == 3
    assert march.arrival_year > 0
    assert outcome.tile_updates[0].army_presence == 10
    assert outcome.faction_updates[0].changes["army_size"] == 40.0


def test_march_waits_before_arrival() -> None:
    """До срока прибытия марш остаётся в пути."""
    march = ArmyMarch(
        id=0,
        faction_id=0,
        from_tile=0,
        to_tile=3,
        amount=10,
        departure_year=0,
        arrival_year=3,
    )
    state = make_state(marches=(march,), presence=10)
    context = StepContext(year=1, config=state.config, rng=Rng(1))

    outcome = MarchRule().apply(state, context)

    assert outcome.army_marches == (march,)
    assert outcome.tile_updates == ()


def test_march_arrives() -> None:
    """В срок армия прибывает и гарнизон растёт."""
    march = ArmyMarch(
        id=0,
        faction_id=0,
        from_tile=0,
        to_tile=3,
        amount=10,
        departure_year=0,
        arrival_year=2,
    )
    state = make_state(
        faction=make_faction(army=40.0),
        marches=(march,),
        presence=5,
    )
    context = StepContext(year=2, config=state.config, rng=Rng(1))

    outcome = MarchRule().apply(state, context)

    assert outcome.army_marches == ()
    assert outcome.faction_updates[0].changes["army_size"] == 50.0
    assert any(
        update.tile_id == 3 and update.army_presence == 10 for update in outcome.tile_updates
    )
    assert any(event.type is EventType.MIGRATION for event in outcome.events)


def test_march_cancelled_when_target_lost() -> None:
    """Потеря нейтрального тайла отменяет прибытие."""
    march = ArmyMarch(
        id=0,
        faction_id=0,
        from_tile=0,
        to_tile=3,
        amount=10,
        departure_year=0,
        arrival_year=2,
    )
    state = make_state(
        faction=make_faction(army=40.0),
        marches=(march,),
        presence=5,
        target_owner=None,
    )
    context = StepContext(year=2, config=state.config, rng=Rng(1))

    outcome = MarchRule().apply(state, context)

    assert outcome.army_marches == ()
    assert outcome.tile_updates == ()
    assert outcome.faction_updates[0].changes["army_size"] == 50.0


def test_march_deterministic() -> None:
    """Марш детерминирован."""
    march = ArmyMarch(
        id=0,
        faction_id=0,
        from_tile=0,
        to_tile=3,
        amount=10,
        departure_year=0,
        arrival_year=2,
    )
    state = make_state(
        faction=make_faction(army=40.0),
        marches=(march,),
        presence=5,
    )
    context = StepContext(year=2, config=state.config, rng=Rng(1))

    first = MarchRule().apply(state, context)
    second = MarchRule().apply(state, context)

    assert first == second
