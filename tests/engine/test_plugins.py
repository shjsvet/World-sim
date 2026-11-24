"""Тесты загрузки плагинов правил."""

from __future__ import annotations

from pathlib import Path

import pytest

from worldsim.core.chronicle import Chronicle
from worldsim.core.rng import Rng
from worldsim.core.state import WorldConfig
from worldsim.engine import plugins
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.plugins import PluginError, PluginRule, load_rules
from worldsim.engine.rules import RuleOutcome, StepContext
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.generator.world import create_world

PLUGIN_TEMPLATE = """
from worldsim.engine.rules import RuleOutcome


class {class_name}:
    name = "{name}"
    priority = {priority}

    def apply(self, state, ctx):
        return RuleOutcome()


RULES = [{class_name}()]
"""


def write_plugin(
    directory: Path,
    filename: str,
    *,
    class_name: str,
    name: str,
    priority: int,
) -> Path:
    """Создаёт файл плагина."""
    path = directory / filename
    path.write_text(
        PLUGIN_TEMPLATE.format(
            class_name=class_name,
            name=name,
            priority=priority,
        ),
        encoding="utf-8",
    )
    return path


def make_context() -> StepContext:
    """Создаёт контекст шага для вызова правила."""
    state = create_world(WorldConfig(seed=1, size=8))
    return StepContext(year=0, config=state.config, rng=Rng(1))


def test_load_plugin_from_directory(tmp_path: Path) -> None:
    """Правило загружается из каталога."""
    write_plugin(tmp_path, "demo_rule.py", class_name="DemoRule", name="demo", priority=15)

    loaded = load_rules([tmp_path])

    assert [rule.name for rule in loaded] == ["demo"]
    assert loaded[0].priority == 15
    assert loaded[0].enabled is True


def test_load_plugin_from_file(tmp_path: Path) -> None:
    """Правило загружается из конкретного файла."""
    path = write_plugin(
        tmp_path,
        "single_rule.py",
        class_name="SingleRule",
        name="single",
        priority=3,
    )

    loaded = load_rules([path])

    assert [rule.name for rule in loaded] == ["single"]


def test_load_from_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """Правило загружается из entry point."""
    from worldsim.engine.rules import RuleOutcome as Outcome

    class EntryRule:
        name = "entry"
        priority = 4

        def apply(self, state: object, ctx: object) -> Outcome:
            return Outcome()

    class EntryPoint:
        name = "entry"

        def load(self) -> type[EntryRule]:
            return EntryRule

    monkeypatch.setattr(plugins, "_entry_points", lambda: [EntryPoint()])

    loaded = load_rules([])

    assert [rule.name for rule in loaded] == ["entry"]


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    """Одинаковые имена правил дают ошибку."""
    write_plugin(tmp_path, "first_rule.py", class_name="FirstRule", name="same", priority=1)
    write_plugin(tmp_path, "second_rule.py", class_name="SecondRule", name="same", priority=2)

    with pytest.raises(PluginError, match="конфликт"):
        load_rules([tmp_path])


def test_invalid_rule_is_rejected(tmp_path: Path) -> None:
    """Класс без apply не считается правилом."""
    path = tmp_path / "bad_rule.py"
    path.write_text(
        """
class BadRule:
    name = "bad"
    priority = 1

RULES = [BadRule()]
""",
        encoding="utf-8",
    )

    with pytest.raises(PluginError):
        load_rules([path])


def test_load_sorts_by_priority(tmp_path: Path) -> None:
    """Правила возвращаются по возрастанию приоритета."""
    write_plugin(tmp_path, "late_rule.py", class_name="LateRule", name="late", priority=20)
    write_plugin(tmp_path, "early_rule.py", class_name="EarlyRule", name="early", priority=5)

    loaded = load_rules([tmp_path])

    assert [rule.name for rule in loaded] == ["early", "late"]


def test_failing_rule_is_isolated() -> None:
    """Падающее правило отключается и даёт CUSTOM."""
    from worldsim.core.events import EventType

    class BrokenRule:
        name = "broken"
        priority = 1

        def apply(self, state: object, ctx: object) -> RuleOutcome:
            raise RuntimeError("сломалось")

    wrapper = PluginRule(inner=BrokenRule())
    context = make_context()
    state = create_world(WorldConfig(seed=1, size=8))

    outcome = wrapper.apply(state, context)

    assert wrapper.enabled is False
    assert outcome.events[0].type is EventType.CUSTOM

    second = wrapper.apply(state, context)
    assert second.events == ()
    assert second.tile_updates == ()


def test_disabled_rule_is_skipped() -> None:
    """Отключённое правило не вызывается."""
    wrapper = PluginRule(inner=PopulationGrowthRule(), enabled=False)
    state = create_world(WorldConfig(seed=1, size=8))

    outcome = wrapper.apply(state, make_context())

    assert outcome == RuleOutcome()


def test_example_plugin_boosts_population() -> None:
    """Пример плагина ускоряет рост населения при мане."""
    state = create_world(WorldConfig(seed=1, size=8))
    magic_state = state.evolve(config=state.config.evolve(magic_level=0.5))
    loaded = load_rules([Path("plugins/mana_rule.py")])
    assert [rule.name for rule in loaded] == ["mana_regeneration"]

    plain = SimulationEngine(
        [PopulationGrowthRule()],
        Chronicle(),
        initial_state=magic_state,
    ).run(1)
    boosted = SimulationEngine(
        [PopulationGrowthRule(), *loaded],
        Chronicle(),
        initial_state=magic_state,
    ).run(1)

    plain_population = sum(tile.population for tile in plain.map.tiles)
    boosted_population = sum(tile.population for tile in boosted.map.tiles)
    assert boosted_population > plain_population


def test_example_plugin_emits_custom_event() -> None:
    """При высокой мане плагин иногда пишет CUSTOM."""
    from worldsim.core.chronicle import Chronicle
    from worldsim.core.events import EventType

    state = create_world(WorldConfig(seed=1, size=8))
    state = state.evolve(config=state.config.evolve(magic_level=1.0))
    chronicle = Chronicle()
    engine = SimulationEngine(
        load_rules([Path("plugins/mana_rule.py")]),
        chronicle,
        initial_state=state,
    )

    engine.run(50)

    assert chronicle.filter(type=EventType.CUSTOM)
