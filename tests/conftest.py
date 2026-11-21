"""Общие фикстуры и хелперы тестов WorldSim."""

from __future__ import annotations

import pytest

from worldsim.core.rng import Rng


@pytest.fixture()
def seed() -> int:
    """Возвращает фиксированный сид для детерминированных тестов."""
    return 42


def deterministic_rng(seed: int = 42) -> Rng:
    """Возвращает детерминированный генератор для тестов.

    Args:
        seed: Сид генератора; по умолчанию 42.

    Returns:
        Экземпляр ``Rng`` с заданным сидом.
    """
    return Rng(seed)


@pytest.fixture()
def rng(seed: int) -> Rng:
    """Детерминированный генератор на основе фикстуры ``seed``."""
    return deterministic_rng(seed)
