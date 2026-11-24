"""Запуск симуляции с плагинами правил."""

from __future__ import annotations

import argparse
from pathlib import Path

from worldsim.core.chronicle import Chronicle
from worldsim.core.state import WorldConfig
from worldsim.engine.engine import SimulationEngine
from worldsim.engine.plugins import load_rules
from worldsim.engine.rules import Rule
from worldsim.engine.rules.population import PopulationGrowthRule
from worldsim.generator.world import create_world


def main(argv: list[str] | None = None) -> int:
    """Запускает мир на заданное число лет и печатает сводку."""
    parser = argparse.ArgumentParser(description="WorldSim: запуск симуляции")
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="путь к файлу или каталогу с *_rule.py (можно несколько)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--years", type=int, default=10)
    args = parser.parse_args(argv)

    rules: list[Rule] = [PopulationGrowthRule()]
    if args.plugin:
        rules.extend(load_rules(args.plugin))

    state = create_world(WorldConfig(seed=args.seed, size=args.size))
    engine = SimulationEngine(rules, Chronicle(), initial_state=state)
    final = engine.run(args.years)

    population = sum(tile.population for tile in final.map.tiles)
    print(f"Год: {final.year}")
    print(f"Население: {population}")
    print(f"Событий: {len(engine.chronicle)}")
    print(f"Правил: {', '.join(rule.name for rule in engine.rules)}")
    print(f"Каталог плагинов: {Path('plugins').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
