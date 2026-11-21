"""Единственный источник случайности в симуляции.

Модуль инкапсулирует ``random.Random`` и запрещает использовать глобальный
``random`` в остальном коде: одинаковый сид даёт одинаковую последовательность
на любой платформе и в любом процессе.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, MutableSequence, Sequence
from typing import Any, TypeVar

T = TypeVar("T")

RandomState = dict[str, Any]


class Rng:
    """Детерминированный генератор случайных чисел.

    Все правила симуляции получают случайность только через экземпляр ``Rng``.
    Состояние можно сохранить в снимок мира через :meth:`getstate` и
    восстановить через :meth:`setstate`.
    """

    def __init__(self, seed: int) -> None:
        """Создаёт генератор с заданным сидом.

        Args:
            seed: Целочисленный сид; одинаковый сид даёт одинаковый поток.
        """
        self._seed = seed
        self._random = random.Random(seed)

    @property
    def seed(self) -> int:
        """Сид, с которым создан генератор."""
        return self._seed

    def int(self, low: int, high: int) -> int:
        """Возвращает целое число в диапазоне ``[low, high]`` включительно.

        Args:
            low: Нижняя граница.
            high: Верхняя граница.

        Raises:
            ValueError: Если ``low > high``.
        """
        if low > high:
            raise ValueError("нижняя граница больше верхней")
        return self._random.randint(low, high)

    def uniform(self, low: float, high: float) -> float:
        """Возвращает вещественное число в диапазоне ``[low, high)``.

        Args:
            low: Нижняя граница.
            high: Верхняя граница.

        Raises:
            ValueError: Если ``low > high``.
        """
        if low > high:
            raise ValueError("нижняя граница больше верхней")
        return self._random.uniform(low, high)

    def random(self) -> float:
        """Возвращает вещественное число в диапазоне ``[0.0, 1.0)``."""
        return self._random.random()

    def choice(self, seq: Sequence[T]) -> T:
        """Возвращает случайный элемент непустой последовательности.

        Args:
            seq: Непустая последовательность.

        Raises:
            IndexError: Если последовательность пуста.
        """
        if not seq:
            raise IndexError("нельзя выбрать элемент из пустой последовательности")
        return self._random.choice(seq)

    def weighted_choice(self, items: Mapping[T, float]) -> T:
        """Выбирает ключ с вероятностью, пропорциональной его весу.

        Порядок обхода — порядок элементов ``items``; веса должны быть
        неотрицательными, а их сумма — положительной.

        Args:
            items: Отображение «ключ → неотрицательный вес».

        Returns:
            Выбранный ключ.

        Raises:
            ValueError: Если отображение пустое, содержит отрицательные или
                нечисловые веса либо сумма весов не положительна.
        """
        if not items:
            raise ValueError("нельзя выбрать из пустого отображения")

        total = 0.0
        for weight in items.values():
            if math.isnan(weight) or weight < 0:
                raise ValueError("вес должен быть неотрицательным числом")
            total += weight
        if total <= 0:
            raise ValueError("сумма весов должна быть положительной")

        threshold = self._random.random() * total
        cumulative = 0.0
        fallback: T | None = None
        for key, weight in items.items():
            if weight > 0:
                fallback = key
            cumulative += weight
            if threshold < cumulative:
                return key

        if fallback is None:  # pragma: no cover - защита от погрешности float
            raise ValueError("не удалось выбрать элемент по весам")
        return fallback

    def shuffle(self, seq: MutableSequence[T]) -> None:
        """Перемешивает последовательность на месте.

        Args:
            seq: Изменяемая последовательность.
        """
        self._random.shuffle(seq)

    def chance(self, probability: float) -> bool:
        """Возвращает ``True`` с заданной вероятностью.

        Args:
            probability: Вероятность в диапазоне ``[0, 1]``.

        Raises:
            ValueError: Если вероятность вне диапазона ``[0, 1]``.
        """
        if math.isnan(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("вероятность должна быть в диапазоне [0, 1]")
        return self._random.random() < probability

    def fork(self, label: str) -> Rng:
        """Создаёт независимый подпоток случайности.

        Сид подпотока считается как ``sha256(f"{seed}:{label}")``, поэтому он
        стабилен между процессами и не зависит от того, сколько чисел уже
        было получено из текущего генератора.

        Args:
            label: Непустая метка подпотока (например, ``"battle"``).

        Raises:
            ValueError: Если метка пуста.
        """
        if not label:
            raise ValueError("метка подпотока не может быть пустой")
        digest = hashlib.sha256(f"{self._seed}:{label}".encode()).digest()
        return Rng(int.from_bytes(digest[:8], "big"))

    def getstate(self) -> RandomState:
        """Возвращает состояние генератора в JSON-совместимом виде."""
        version, internal, gauss = self._random.getstate()
        return {"version": version, "internal": list(internal), "gauss": gauss}

    def setstate(self, state: Mapping[str, Any]) -> None:
        """Восстанавливает состояние, полученное из :meth:`getstate`.

        Args:
            state: Словарь с ключами ``version``, ``internal`` и ``gauss``.
        """
        internal = tuple(int(value) for value in state["internal"])
        gauss = state.get("gauss")
        self._random.setstate((int(state["version"]), internal, gauss))

    def __repr__(self) -> str:
        """Краткое представление без раскрытия состояния."""
        return f"Rng(seed={self._seed})"
