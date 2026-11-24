"""Тесты боевой магии."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology, MagicSchool
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules import BattleRequest, RuleOutcome, StepContext
from worldsim.engine.rules.battle_magic import (
    SCHOOL_ADVANTAGE,
    SCHOOL_PENALTY,
    MagicCombatRule,
)
from worldsim.engine.rules.war import WarResolutionRule


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    capital: int = 0,
    army: float = 10.0,
    mana_pool: int = 100,
    magic_affinity: int = 100,
    magic_schools: tuple[MagicSchool, ...] = (MagicSchool.FIRE,),
) -> Faction:
    """Создаёт фракцию с магическими параметрами."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture="Люди",
        capital_tile_id=capital,
        army_size=army,
        mana_pool=mana_pool,
        magic_affinity=magic_affinity,
        magic_schools=magic_schools,
    )


def make_state(
    *,
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    seed: int = 1,
) -> WorldState:
    """Создаёт карту с фракциями."""
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
        data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=seed, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
    )


class BattleInjector:
    """Добавляет заявку на бой до магической подготовки."""

    name = "inject"
    priority = 17

    def __init__(self, request: BattleRequest) -> None:
        self.request = request

    def apply(self, state: WorldState, ctx: StepContext) -> RuleOutcome:
        """Добавляет заявку."""
        ctx.pending_battles.append(self.request)
        return RuleOutcome()


def magic_context(state: WorldState, request: BattleRequest) -> StepContext:
    """Создаёт контекст с одной заявкой на бой."""
    return StepContext(
        year=0,
        config=state.config,
        rng=Rng(1),
        pending_battles=[request],
    )


def test_school_advantage() -> None:
    """Контршкола даёт атакующему преимущество."""
    attacker = make_faction(0)
    defender = make_faction(
        1,
        name="Орда",
        color="#445566",
        capital=1,
        magic_schools=(MagicSchool.ICE,),
    )
    state = make_state(
        factions=(attacker, defender),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )
    context = magic_context(state, BattleRequest(0, 1, 1))

    outcome = MagicCombatRule().apply(state, context)

    boost = context.magic_boosts[0]
    assert boost.mana_spent == 10
    assert boost.school_modifier == SCHOOL_ADVANTAGE
    assert boost.magic_bonus > 0.0
    assert outcome.faction_updates[0].changes["mana_pool"] == 90


def test_school_penalty() -> None:
    """Без побеждающей школы атака получает штраф."""
    attacker = make_faction(0)
    defender = make_faction(
        1,
        name="Орда",
        color="#445566",
        capital=1,
        magic_schools=(MagicSchool.FIRE,),
    )
    state = make_state(
        factions=(attacker, defender),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )
    context = magic_context(state, BattleRequest(0, 1, 1))

    MagicCombatRule().apply(state, context)

    assert context.magic_boosts[0].school_modifier == SCHOOL_PENALTY


def test_no_mana_gives_no_bonus() -> None:
    """При нулевой мане бонус и расход равны нулю."""
    attacker = make_faction(0, mana_pool=0)
    defender = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        factions=(attacker, defender),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )
    context = magic_context(state, BattleRequest(0, 1, 1))

    outcome = MagicCombatRule().apply(state, context)

    boost = context.magic_boosts[0]
    assert boost.mana_spent == 0
    assert boost.magic_bonus == 0.0
    assert outcome.faction_updates == ()


def test_spend_does_not_exceed_mana() -> None:
    """Расход маны не превышает запас."""
    attacker = make_faction(0, mana_pool=25)
    defender = make_faction(1, name="Орда", color="#445566", capital=1)
    state = make_state(
        factions=(attacker, defender),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )
    context = magic_context(state, BattleRequest(0, 1, 1))

    outcome = MagicCombatRule().apply(state, context)

    assert context.magic_boosts[0].mana_spent <= 25
    assert outcome.faction_updates[0].changes["mana_pool"] >= 0


def test_war_event_contains_mana_spent() -> None:
    """Событие WAR получает payload с потраченной маной."""
    attacker = make_faction(0, army=1_000.0, mana_pool=100)
    defender = make_faction(
        1,
        name="Орда",
        color="#445566",
        capital=1,
        army=1.0,
        magic_schools=(MagicSchool.ICE,),
    )
    state = make_state(
        factions=(attacker, defender),
        overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
    )
    chronicle = Chronicle()
    engine = SimulationEngine(
        [
            BattleInjector(BattleRequest(0, 1, 1)),
            MagicCombatRule(),
            WarResolutionRule(),
        ],
        chronicle,
        initial_state=state,
    )

    engine.step()

    war_events = chronicle.filter(type=EventType.WAR)
    assert len(war_events) == 1
    assert war_events[0].payload["mana_spent"] == 10


def test_battle_magic_is_deterministic() -> None:
    """Фиксированный seed даёт одинаковый бой."""

    def run_once() -> tuple[str, str]:
        attacker = make_faction(0, army=1_000.0)
        defender = make_faction(
            1,
            name="Орда",
            color="#445566",
            capital=1,
            army=1.0,
            magic_schools=(MagicSchool.ICE,),
        )
        state = make_state(
            factions=(attacker, defender),
            overrides={0: {"owner_id": 0}, 1: {"owner_id": 1}},
            seed=4,
        )
        chronicle = Chronicle()
        engine = SimulationEngine(
            [
                BattleInjector(BattleRequest(0, 1, 1)),
                MagicCombatRule(),
                WarResolutionRule(),
            ],
            chronicle,
            initial_state=state,
        )
        updated = engine.step()
        return updated.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()
