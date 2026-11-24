"""Тесты исполнения решений ИИ-правителей."""

from __future__ import annotations

from worldsim.ai.ruler import RulerAction, RulerDecision
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology, MagicSchool
from worldsim.core.geography import Biome, RegionData, ResourceType, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.rules import AICommand, StepContext
from worldsim.engine.rules.ai_ruler import AIRulerRule


def make_faction(
    faction_id: int = 0,
    *,
    capital: int = 0,
    treasury: float = 200.0,
    mana_pool: int = 100,
    army: float = 10.0,
    food: float = 100.0,
) -> Faction:
    """Создаёт фракцию для действий ИИ."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        treasury=treasury,
        mana_pool=mana_pool,
        army_size=army,
        food_stockpile=food,
    )


def make_state(
    *,
    factions: tuple[Faction, ...] | None = None,
    overrides: dict[int, dict[str, object]] | None = None,
) -> WorldState:
    """Создаёт карту с переопределениями тайлов."""
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
            "mana_density": 60,
        }
        if overrides is not None:
            data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=1, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
    )


def decision(
    action: RulerAction,
    *,
    target: int | None = None,
    amount: int = 0,
) -> RulerDecision:
    """Создаёт решение правителя."""
    return RulerDecision(
        action=action,
        target_tile_id=target,
        amount=amount,
        thought="Решение для теста.",
        confidence=0.5,
    )


def run_rule(state: WorldState, *commands: AICommand) -> object:
    """Выполняет правило ИИ с командами."""
    context = StepContext(
        year=0,
        config=state.config,
        rng=Rng(1),
        ai_decisions=list(commands),
    )
    return AIRulerRule().apply(state, context)


def test_build_academy() -> None:
    """ИИ строит академию на подходящем тайле."""
    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.BUILD_ACADEMY, target=0)),
    )

    assert len(outcome.academies) == 1  # type: ignore[attr-defined]
    changes = outcome.faction_updates[0].changes  # type: ignore[attr-defined]
    assert changes["treasury"] == 100.0
    assert changes["mana_pool"] == 50
    assert MagicSchool.FIRE in changes["magic_schools"]
    assert any(
        event.type is EventType.ACADEMY_FOUNDED
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_build_academy_without_resources() -> None:
    """Без денег и маны академия не строится."""
    faction = make_faction(treasury=10.0, mana_pool=10)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.BUILD_ACADEMY, target=0)),
    )

    assert outcome.academies == ()  # type: ignore[attr-defined]
    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_build_academy_on_foreign_tile() -> None:
    """Академия не строится на чужом тайле."""
    first = make_faction()
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.BUILD_ACADEMY, target=1)),
    )

    assert outcome.academies == ()  # type: ignore[attr-defined]


def test_recruit() -> None:
    """ИИ набирает солдат за золото."""
    faction = make_faction(treasury=100.0, army=10.0)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.RECRUIT, amount=5)),
    )

    changes = outcome.faction_updates[0].changes  # type: ignore[attr-defined]
    assert changes["treasury"] == 90.0
    assert changes["army_size"] == 15.0
    assert any(
        event.type is EventType.RECRUITMENT
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_recruit_without_money() -> None:
    """При нехватке золота набор не происходит."""
    faction = make_faction(treasury=5.0, army=10.0)
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.RECRUIT, amount=5)),
    )

    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_extract_food() -> None:
    """ИИ добывает еду и истощает тайл."""
    faction = make_faction(food=100.0)
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.FOOD,
                "resource_amount": 10.0,
                "resource_depletion": 10.0,
            }
        },
    )

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.EXTRACT_RESOURCE, target=0, amount=5)),
    )

    updates = outcome.tile_updates  # type: ignore[attr-defined]
    assert updates[0].resource_depletion == 5.0
    changes = outcome.faction_updates[0].changes  # type: ignore[attr-defined]
    assert changes["food_stockpile"] == 105.0
    assert any(
        event.type is EventType.CUSTOM
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_extract_gold() -> None:
    """Золото из месторождения попадает в казну."""
    faction = make_faction(treasury=10.0)
    state = make_state(
        factions=(faction,),
        overrides={
            0: {
                "owner_id": 0,
                "resource_type": ResourceType.GOLD,
                "resource_amount": 10.0,
                "resource_depletion": 10.0,
            }
        },
    )

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.EXTRACT_RESOURCE, target=0, amount=4)),
    )

    changes = outcome.faction_updates[0].changes  # type: ignore[attr-defined]
    assert changes["treasury"] == 14.0


def test_redistribute_population() -> None:
    """ИИ переносит население между своими тайлами."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={
            0: {"owner_id": 0, "population": 100},
            1: {"owner_id": 0, "population": 100, "population_capacity": 1_000},
        },
    )

    outcome = run_rule(
        state,
        AICommand(
            0,
            decision(RulerAction.REDISTRIBUTE_POPULATION, target=1, amount=30),
        ),
    )

    updates = {update.tile_id: update for update in outcome.tile_updates}  # type: ignore[attr-defined]
    assert updates[0].population == 70
    assert updates[1].population == 130


def test_hold_changes_nothing() -> None:
    """HOLD не меняет мир."""
    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(state, AICommand(0, decision(RulerAction.HOLD)))

    assert outcome.tile_updates == ()  # type: ignore[attr-defined]
    assert outcome.faction_updates == ()  # type: ignore[attr-defined]
    assert outcome.events == ()  # type: ignore[attr-defined]


def test_unknown_faction_command_is_ignored() -> None:
    """Команда несуществующей фракции игнорируется."""
    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(state, AICommand(5, decision(RulerAction.RECRUIT, amount=5)))

    assert outcome.faction_updates == ()  # type: ignore[attr-defined]


def test_declare_war() -> None:
    """ИИ объявляет войну соседней фракции."""
    first = make_faction()
    second = make_faction(1, capital=1)
    state = make_state(
        factions=(first, second),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.DECLARE_WAR, target=1)),
    )

    assert outcome.wars is not None  # type: ignore[attr-defined]
    assert outcome.wars[0].active  # type: ignore[attr-defined]
    assert outcome.wars[0].attacker_id == 0  # type: ignore[attr-defined]
    assert outcome.wars[0].defender_id == 1  # type: ignore[attr-defined]
    assert any(
        event.type is EventType.WAR
        for event in outcome.events  # type: ignore[attr-defined]
    )


def test_declare_war_ignores_same_faction() -> None:
    """Нельзя объявить войну самому себе."""
    faction = make_faction()
    state = make_state(factions=(faction,), overrides={0: {"owner_id": 0}})

    outcome = run_rule(
        state,
        AICommand(0, decision(RulerAction.DECLARE_WAR, target=0)),
    )

    assert outcome.wars is None  # type: ignore[attr-defined]
