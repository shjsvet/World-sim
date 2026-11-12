"""Общие фикстуры и хелперы тестов WorldSim."""

from __future__ import annotations

import random

import pytest


@pytest.fixture()
def seed() -> int:
    """Возвращает фиксированный сид для детерминированных тестов."""
    return 42


def deterministic_rng(seed: int = 42) -> random.Random:
    """Возвращает детерминированный генератор для тестов.

    Args:
        seed: Сид генератора; по умолчанию 42.

    Returns:
        Экземпляр ``random.Random`` с заданным сидом.

    Note:
        Временная реализация до появления ``worldsim.core.rng.Rng`` (T07):
        после T07 хелпер будет переключён на него.
    """
    return random.Random(seed)


@pytest.fixture()
def rng(seed: int) -> random.Random:
    """Детерминированный генератор на основе фикстуры ``seed``."""
    return deterministic_rng(seed)
