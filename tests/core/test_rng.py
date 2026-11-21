"""Тесты детерминированного генератора случайных чисел."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from worldsim.core.rng import Rng


def test_same_seed_same_sequence() -> None:
    """Одинаковый сид даёт одинаковую последовательность."""
    first = Rng(42)
    second = Rng(42)

    assert [first.int(0, 100) for _ in range(10)] == [second.int(0, 100) for _ in range(10)]
    assert [first.uniform(0.0, 1.0) for _ in range(5)] == [
        second.uniform(0.0, 1.0) for _ in range(5)
    ]


def test_different_seeds_differ() -> None:
    """Разные сиды дают разные последовательности."""
    first = Rng(1)
    second = Rng(2)

    assert [first.int(0, 1000) for _ in range(20)] != [second.int(0, 1000) for _ in range(20)]


def test_fork_is_repeatable() -> None:
    """Одинаковая метка даёт одинаковый подпоток."""
    left = Rng(42).fork("battle")
    right = Rng(42).fork("battle")

    assert [left.int(0, 100) for _ in range(10)] == [right.int(0, 100) for _ in range(10)]


def test_fork_depends_on_label() -> None:
    """Разные метки дают разные подпотоки."""
    battle = Rng(42).fork("battle")
    trade = Rng(42).fork("trade")

    assert [battle.int(0, 100) for _ in range(10)] != [trade.int(0, 100) for _ in range(10)]


def test_fork_ignores_parent_progress() -> None:
    """Подпоток не зависит от того, сколько чисел уже получено из родителя."""
    fresh = Rng(42).fork("nested")
    used = Rng(42)
    for _ in range(20):
        used.int(0, 10)
    forked = used.fork("nested")

    assert [forked.int(0, 100) for _ in range(10)] == [fresh.int(0, 100) for _ in range(10)]


def test_int_and_uniform_validation() -> None:
    """Некорректные границы отклоняются."""
    with pytest.raises(ValueError):
        Rng(1).int(10, 5)
    with pytest.raises(ValueError):
        Rng(1).uniform(1.0, 0.0)


def test_choice() -> None:
    """``choice`` возвращает элемент последовательности и падает на пустой."""
    rng = Rng(5)
    items = ["a", "b", "c"]

    assert rng.choice(items) in items
    with pytest.raises(IndexError):
        rng.choice([])


def test_weighted_choice_zero_weights() -> None:
    """Ключи с нулевым весом не выбираются."""
    rng = Rng(7)
    items = {"a": 0.0, "b": 1.0}

    assert {rng.weighted_choice(items) for _ in range(50)} == {"b"}


def test_weighted_choice_validation() -> None:
    """Пустые, отрицательные и нулевые веса отклоняются."""
    with pytest.raises(ValueError):
        Rng(1).weighted_choice({})
    with pytest.raises(ValueError):
        Rng(1).weighted_choice({"a": 0.0, "b": 0.0})
    with pytest.raises(ValueError):
        Rng(1).weighted_choice({"a": -1.0, "b": 1.0})


def test_weighted_choice_distribution() -> None:
    """Частоты примерно соответствуют весам 1:3."""
    rng = Rng(11)
    items = {"a": 1.0, "b": 3.0}
    counts = {"a": 0, "b": 0}

    for _ in range(2_000):
        counts[rng.weighted_choice(items)] += 1

    share = counts["a"] / 2_000
    assert 0.15 < share < 0.35


def test_chance_boundaries() -> None:
    """``chance(0)`` всегда ``False``, ``chance(1)`` всегда ``True``."""
    rng = Rng(3)

    assert all(not rng.chance(0.0) for _ in range(100))
    assert all(rng.chance(1.0) for _ in range(100))

    with pytest.raises(ValueError):
        rng.chance(1.5)
    with pytest.raises(ValueError):
        rng.chance(-0.1)


def test_shuffle_is_permutation_and_repeatable() -> None:
    """Перемешивание детерминировано и сохраняет состав."""
    first = list(range(20))
    second = list(range(20))

    Rng(5).shuffle(first)
    Rng(5).shuffle(second)

    assert first == second
    assert sorted(first) == list(range(20))
    assert first != list(range(20))


def test_shuffle_empty_and_single() -> None:
    """Пустая и одноэлементная последовательности перемешиваются без ошибок."""
    empty: list[int] = []
    single = [1]

    Rng(1).shuffle(empty)
    Rng(1).shuffle(single)

    assert empty == []
    assert single == [1]


def test_state_round_trip_via_json() -> None:
    """Состояние переживает JSON-сериализацию и продолжает последовательность."""
    rng = Rng(42)
    for _ in range(5):
        rng.int(0, 100)

    state = json.loads(json.dumps(rng.getstate()))
    expected = [rng.int(0, 100) for _ in range(10)]

    restored = Rng(42)
    restored.setstate(state)

    assert [restored.int(0, 100) for _ in range(10)] == expected


def test_cross_process_determinism() -> None:
    """В отдельном процессе с тем же сидом получается та же последовательность."""
    code = (
        "from worldsim.core.rng import Rng\n"
        "rng = Rng(123)\n"
        "print([rng.int(0, 1000) for _ in range(5)])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )

    rng = Rng(123)
    expected = [rng.int(0, 1000) for _ in range(5)]

    assert result.stdout.strip() == str(expected)


def test_only_rng_module_imports_random() -> None:
    """Глобальный ``random`` используется только внутри ``rng.py``."""
    root = pathlib.Path(__file__).resolve().parents[2]
    needles = ["import " + "random", "from " + "random import"]
    candidates = list((root / "src").rglob("*.py")) + list((root / "tests").rglob("*.py"))
    offenders: list[str] = []

    for path in candidates:
        if path.name == "rng.py":
            continue
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in needles):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []
