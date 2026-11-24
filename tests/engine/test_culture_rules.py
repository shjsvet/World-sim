"""Тесты правил культуры и религии."""

from __future__ import annotations

from worldsim.core.chronicle import Chronicle
from worldsim.core.culture import Culture, Religion
from worldsim.core.diplomacy import War
from worldsim.core.events import EventType
from worldsim.core.faction import Faction, Ideology
from worldsim.core.geography import Biome, RegionData, WorldMap
from worldsim.core.state import WorldConfig, WorldState
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.culture import (
    AssimilationRule,
    ConversionRule,
    CultureClashRule,
)


def make_faction(
    faction_id: int = 0,
    *,
    name: str = "Альянс",
    color: str = "#112233",
    culture: str = "Люди",
    capital: int = 0,
) -> Faction:
    """Создаёт фракцию для тестов культуры."""
    return Faction(
        id=faction_id,
        name=name,
        color=color,
        ideology=Ideology.MILITARIST,
        culture=culture,
        capital_tile_id=capital,
    )


def make_war(attacker: int = 0, defender: int = 1) -> War:
    """Создаёт активную войну."""
    return War(
        id=0,
        attacker_id=attacker,
        defender_id=defender,
        started_year=0,
        battles=1,
        active=True,
    )


def make_state(
    *,
    factions: tuple[Faction, ...] = (),
    cultures: tuple[Culture, ...] = (),
    religions: tuple[Religion, ...] = (),
    overrides: dict[int, dict[str, object]] | None = None,
    wars: tuple[War, ...] = (),
    seed: int = 1,
) -> WorldState:
    """Создаёт карту с культурами и переопределениями тайлов."""
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
        config=WorldConfig(seed=seed, size=4, initial_factions=len(factions)),
        year=0,
        map=WorldMap(size=4, tiles=tuple(tiles)),
        factions=factions,
        wars=wars,
        cultures=cultures,
        religions=religions,
    )


def run_years(state: WorldState, rule: object, years: int = 1) -> tuple[WorldState, Chronicle]:
    """Прогоняет правило несколько лет."""
    chronicle = Chronicle()
    engine = SimulationEngine([rule], chronicle, initial_state=state)  # type: ignore[list-item]
    return engine.run(years), chronicle


def test_assimilation_grows_in_peace() -> None:
    """При счастье выше 50 ассимиляция растёт."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Орда", color="#445566", culture="Орки", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(Culture(id=0, name="Люди"), Culture(id=1, name="Орки")),
        overrides={
            0: {"owner_id": 0, "culture": "Орки", "happiness": 80.0},
            1: {"owner_id": 1, "culture": "Орки"},
        },
    )

    updated, _ = run_years(state, AssimilationRule())

    assert 0.05 <= updated.map.tiles[0].assimilation <= 0.1


def test_assimilation_falls_during_war() -> None:
    """Война снижает ассимиляцию."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Орда", color="#445566", culture="Орки", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(Culture(id=0, name="Люди"), Culture(id=1, name="Орки")),
        overrides={
            0: {"owner_id": 0, "culture": "Орки", "happiness": 80.0, "assimilation": 0.5},
            1: {"owner_id": 1, "culture": "Орки"},
        },
        wars=(make_war(),),
    )

    updated, _ = run_years(state, AssimilationRule())

    assert updated.map.tiles[0].assimilation < 0.5


def test_assimilation_switches_culture_at_one() -> None:
    """На единице культура тайла меняется на культуру владельца."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Орда", color="#445566", culture="Орки", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(Culture(id=0, name="Люди"), Culture(id=1, name="Орки")),
        overrides={
            0: {"owner_id": 0, "culture": "Орки", "happiness": 80.0, "assimilation": 0.96},
            1: {"owner_id": 1, "culture": "Орки"},
        },
    )

    updated, _ = run_years(state, AssimilationRule())

    tile = updated.map.tiles[0]
    assert tile.culture == "Люди"
    assert tile.culture_id == 0
    assert tile.assimilation == 0.0


def test_same_culture_resets_assimilation() -> None:
    """Совпадение культур сбрасывает ассимиляцию."""
    faction = make_faction(0, culture="Люди")
    state = make_state(
        factions=(faction,),
        cultures=(Culture(id=0, name="Люди"),),
        overrides={0: {"owner_id": 0, "culture": "Люди", "assimilation": 0.4}},
    )

    updated, _ = run_years(state, AssimilationRule())

    assert updated.map.tiles[0].assimilation == 0.0


def test_culture_clash_on_frontier() -> None:
    """На границе разных культур растёт напряжение и случается конфликт."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Орда", color="#445566", culture="Орки", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(
            Culture(id=0, name="Люди", traits=("торговля", "ремесло")),
            Culture(id=1, name="Орки", traits=("война", "охота")),
        ),
        overrides={
            0: {"owner_id": 0, "culture": "Люди"},
            1: {"owner_id": 1, "culture": "Орки"},
        },
        seed=3,
    )

    updated, chronicle = run_years(state, CultureClashRule(), years=20)

    assert updated.map.tiles[0].cultural_tension > 0
    assert chronicle.filter(type=EventType.CULTURE_CLASH)


def test_same_cultures_do_not_clash() -> None:
    """Одинаковые культуры не создают напряжение."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Союз", color="#445566", culture="Люди", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(Culture(id=0, name="Люди"),),
        overrides={
            0: {"owner_id": 0, "culture": "Люди"},
            1: {"owner_id": 1, "culture": "Люди"},
        },
    )

    updated, chronicle = run_years(state, CultureClashRule(), years=10)

    assert updated.map.tiles[0].cultural_tension == 0.0
    assert chronicle.filter(type=EventType.CULTURE_CLASH) == ()


def test_conversion_by_zeal() -> None:
    """Религия с высоким рвением вытесняет соседнюю."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Орда", color="#445566", culture="Орки", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(Culture(id=0, name="Люди"), Culture(id=1, name="Орки")),
        religions=(
            Religion(id=0, name="Свет", culture_id=0, zeal=0.1),
            Religion(id=1, name="Пламя", culture_id=1, zeal=0.9),
        ),
        overrides={
            0: {"owner_id": 0, "culture": "Люди", "religion_id": 0},
            1: {"owner_id": 1, "culture": "Орки", "religion_id": 1},
        },
        seed=5,
    )

    updated, _ = run_years(state, ConversionRule(), years=20)

    assert updated.map.tiles[0].religion_id == 1


def test_same_religion_is_stable() -> None:
    """Одинаковые религии не меняются."""
    first = make_faction(0, culture="Люди")
    second = make_faction(1, name="Союз", color="#445566", culture="Люди", capital=1)
    state = make_state(
        factions=(first, second),
        cultures=(Culture(id=0, name="Люди"),),
        religions=(Religion(id=0, name="Свет", culture_id=0, zeal=0.2),),
        overrides={
            0: {"owner_id": 0, "culture": "Люди", "religion_id": 0},
            1: {"owner_id": 1, "culture": "Люди", "religion_id": 0},
        },
    )

    updated, _ = run_years(state, ConversionRule(), years=5)

    assert updated.map.tiles[0].religion_id == 0


def test_culture_rules_are_deterministic() -> None:
    """Одинаковый сид даёт одинаковый конфликт."""

    def run_once() -> tuple[str, str]:
        first = make_faction(0, culture="Люди")
        second = make_faction(1, name="Орда", color="#445566", culture="Орки", capital=1)
        state = make_state(
            factions=(first, second),
            cultures=(
                Culture(id=0, name="Люди", traits=("торговля",)),
                Culture(id=1, name="Орки", traits=("война",)),
            ),
            overrides={
                0: {"owner_id": 0, "culture": "Люди"},
                1: {"owner_id": 1, "culture": "Орки"},
            },
            seed=9,
        )
        updated, chronicle = run_years(state, CultureClashRule(), years=15)
        return updated.snapshot_hash(), chronicle.to_json()

    assert run_once() == run_once()
