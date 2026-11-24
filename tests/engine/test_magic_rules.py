"""Тесты магической экономики."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology, MagicSchool
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.magic import MagicAcademy
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.magic import AcademyRule, MagicResearchRule, ManaRule


def make_faction(
    faction_id: int = 0,
    *,
    treasury: float = 200.0,
    mana_pool: int = 100,
    magic_affinity: int = 0,
    magic_schools: tuple[MagicSchool, ...] = (),
) -> Faction:
    """Создаёт фракцию с магическими параметрами."""
    return Faction(
        id=faction_id,
        name=f"Фракция {faction_id}",
        color="#112233" if faction_id == 0 else "#445566",
        ideology=Ideology.SCHOLARLY,
        culture="Люди",
        capital_tile_id=0,
        treasury=treasury,
        mana_pool=mana_pool,
        magic_affinity=magic_affinity,
        magic_schools=magic_schools,
    )


def make_state(
    *,
    factions: tuple[Faction, ...],
    overrides: dict[int, dict[str, object]],
    academies: tuple[MagicAcademy, ...] = (),
    seed: int = 1,
    year: int = 0,
) -> WorldState:
    """Создаёт карту с магическими переопределениями."""
    tiles: list[RegionData] = []
    for index in range(16):
        data: dict[str, object] = {
            "id": index,
            "x": index % 4,
            "y": index // 4,
            "biome": Biome.PLAINS,
            "fertility": 50.0,
            "elevation": 100.0,
            "population": 10,
            "population_capacity": 1_000,
            "mana_density": 60,
        }
        data.update(overrides.get(index, {}))
        tiles.append(RegionData.model_validate(data))
    return WorldState(
        config=WorldConfig(seed=seed, size=4, initial_factions=len(factions)),
        year=year,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        academies=academies,
    )


def run_rule(
    state: WorldState,
    rule: object,
    years: int = 1,
) -> tuple[WorldState, Chronicle]:
    """Прогоняет одно правило."""
    chronicle = Chronicle()
    engine = SimulationEngine([rule], chronicle, initial_state=state)  # type: ignore[list-item]
    return engine.run(years), chronicle


def test_mana_accumulates_from_tiles_and_leys() -> None:
    """Доход маны включает регенерацию тайлов и бонус лей-линии."""
    faction = make_faction(mana_pool=0)
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0, "mana_regeneration": 3, "ley_line": True}},
    )

    updated, _ = run_rule(state, ManaRule())

    assert updated.factions[0].mana_pool == 5


def test_mana_does_not_go_negative() -> None:
    """Без дохода мана не уходит в минус."""
    faction = make_faction(mana_pool=0)
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0, "mana_regeneration": 0}},
    )

    updated, _ = run_rule(state, ManaRule())

    assert updated.factions[0].mana_pool == 0


def test_academy_is_founded() -> None:
    """Академия строится при достаточных золоте и мане."""
    faction = make_faction(treasury=200.0, mana_pool=100)
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0, "mana_density": 60}},
    )

    updated, chronicle = run_rule(state, AcademyRule())

    academy = updated.academies[0]
    assert academy.faction_id == 0
    assert academy.tile_id == 0
    assert academy.school is MagicSchool.FIRE
    assert updated.factions[0].treasury == 100.0
    assert updated.factions[0].mana_pool == 50
    assert len(chronicle.filter(type=EventType.ACADEMY_FOUNDED)) == 1


def test_academy_requires_resources() -> None:
    """Без золота или маны академия не строится."""
    poor = make_faction(treasury=50.0, mana_pool=100)
    state = make_state(
        factions=(poor,),
        overrides={0: {"owner_id": 0}},
    )

    updated, chronicle = run_rule(state, AcademyRule())

    assert updated.academies == ()
    assert chronicle.filter(type=EventType.ACADEMY_FOUNDED) == ()


def test_academy_requires_density() -> None:
    """На тайле с низкой плотностью маны академия не строится."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0, "mana_density": 30}},
    )

    updated, _ = run_rule(state, AcademyRule())

    assert updated.academies == ()


def test_research_grows_affinity_and_level() -> None:
    """Исследования повышают склонность и уровень академии."""
    faction = make_faction(
        magic_affinity=5,
        magic_schools=(MagicSchool.FIRE,),
        mana_pool=100,
    )
    academy = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.FIRE,
        level=1,
        founded_year=0,
    )
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0}},
        academies=(academy,),
        year=5,
    )

    updated, chronicle = run_rule(state, MagicResearchRule())

    assert updated.factions[0].magic_affinity == 6
    assert updated.factions[0].mana_pool == 80
    assert updated.academies[0].level == 2
    assert len(chronicle.filter(type=EventType.MAGIC_BREAKTHROUGH)) == 1


def test_research_requires_academy() -> None:
    """Без академий склонность не растёт."""
    faction = make_faction(magic_affinity=0, mana_pool=100)
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0}},
    )

    updated, _ = run_rule(state, MagicResearchRule())

    assert updated.factions[0].magic_affinity == 0
    assert updated.factions[0].mana_pool == 100


def test_research_requires_mana() -> None:
    """При нехватке маны исследования не идут."""
    faction = make_faction(
        magic_affinity=5,
        magic_schools=(MagicSchool.FIRE,),
        mana_pool=10,
    )
    academy = MagicAcademy(
        id=0,
        tile_id=0,
        faction_id=0,
        school=MagicSchool.FIRE,
        founded_year=0,
    )
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0}},
        academies=(academy,),
    )

    updated, _ = run_rule(state, MagicResearchRule())

    assert updated.factions[0].magic_affinity == 5
    assert updated.academies[0].level == 1


def test_magic_rules_are_deterministic() -> None:
    """Одинаковый сид даёт одинаковый результат."""
    faction = make_faction()
    state = make_state(
        factions=(faction,),
        overrides={0: {"owner_id": 0}},
        seed=7,
    )

    first, _ = run_rule(state, AcademyRule())
    second, _ = run_rule(state, AcademyRule())

    assert first.snapshot_hash() == second.snapshot_hash()
