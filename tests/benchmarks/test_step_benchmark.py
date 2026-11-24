"""Бенчмарк шага симуляции 256×256.

По умолчанию не запускается: маркер ``slow`` и переменная окружения
``WORLDSIM_BENCH=1``. Пример:

    WORLDSIM_BENCH=1 pytest tests/benchmarks/test_step_benchmark.py -s
"""

from __future__ import annotations

import os
import time
import tracemalloc

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldConfig
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.rules.army import ArmyMovementRule, FrontlineRule, OccupationRule
from worldsim.engine.rules.culture import AssimilationRule, ConversionRule, CultureClashRule
from worldsim.engine.rules.diplomacy import DiplomacyRule
from worldsim.engine.rules.economy import EconomyRule
from worldsim.engine.rules.expansion import ExpansionRule
from worldsim.engine.rules.extraction import ExtractionRule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.engine.rules.random_events import FamineRule, PlagueRule
from worldsim.engine.rules.social import (
    HappinessRule,
    RiotRule,
    SecessionRule,
    UnrestRule,
    UrbanizationRule,
)
from worldsim.engine.rules.trade import TradeRule
from worldsim.engine.rules.war import WarResolutionRule
from worldsim.generator.world import create_world

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("WORLDSIM_BENCH") != "1",
        reason="бенчмарк запускается с WORLDSIM_BENCH=1",
    ),
]


def full_rules() -> list[object]:
    """Полный набор правил этапа 4."""
    return [
        EconomyRule(),
        ExtractionRule(),
        ArmyMovementRule(),
        FrontlineRule(),
        FamineRule(),
        ExpansionRule(),
        PopulationGrowthRule(),
        HappinessRule(),
        UnrestRule(),
        RiotRule(),
        SecessionRule(),
        UrbanizationRule(),
        AssimilationRule(),
        CultureClashRule(),
        ConversionRule(),
        PlagueRule(),
        WarResolutionRule(),
        OccupationRule(),
        TradeRule(),
        DiplomacyRule(),
    ]


def test_step_benchmark_256() -> None:
    """Печатает время шага и пиковую память на карте 256×256."""
    steps = int(os.environ.get("WORLDSIM_BENCH_STEPS", "3"))
    state = create_world(WorldConfig(seed=42, size=256, initial_factions=3))
    engine = SimulationEngine(full_rules(), Chronicle(), initial_state=state)  # type: ignore[arg-type]

    durations: list[float] = []
    for _ in range(steps):
        started = time.perf_counter()
        engine.step()
        durations.append(time.perf_counter() - started)

    tracemalloc.start()
    engine.step()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    average = sum(durations) / len(durations)
    print(
        f"\n256x256: {average * 1000:.0f} мс/шаг "
        f"(мин {min(durations) * 1000:.0f}, макс {max(durations) * 1000:.0f}), "
        f"пик памяти {peak / 1e6:.1f} МБ"
    )

    assert engine.state.year == steps + 1
