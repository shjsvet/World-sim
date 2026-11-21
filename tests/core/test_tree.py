"""Тесты бинарного дерева поиска."""

from __future__ import annotations

import json

from worldsim.core.rng import Rng
from worldsim.core.tree import BinarySearchTree


def test_empty_tree() -> None:
    """Пустое дерево корректно отвечает на все запросы."""
    tree: BinarySearchTree[int, str] = BinarySearchTree()

    assert len(tree) == 0
    assert tree.key_count == 0
    assert tree.value_count == 0
    assert tree.height() == 0
    assert tree.get(1) is None
    assert tree.get_all(1) == []
    assert tree.contains(1) is False
    assert tree.min_key() is None
    assert tree.max_key() is None
    assert list(tree) == []
    assert list(tree.items()) == []
    assert list(tree.range_query(0, 10)) == []
    assert tree.remove(1) is False


def test_insert_and_get_duplicates() -> None:
    """Один ключ хранит несколько значений; ``get`` возвращает первое."""
    tree: BinarySearchTree[int, str] = BinarySearchTree()
    tree.insert(2020, "a")
    tree.insert(2020, "b")
    tree.insert(2019, "c")

    assert tree.get(2020) == "a"
    assert tree.get_all(2020) == ["a", "b"]
    assert tree.get(2019) == "c"
    assert tree.get(2018) is None
    assert len(tree) == 2
    assert tree.value_count == 3
    assert list(tree) == [2019, 2020]
    assert list(tree.items()) == [(2019, "c"), (2020, "a"), (2020, "b")]


def test_inorder_sorted_for_shuffled_input() -> None:
    """In-order обход отдаёт ключи по возрастанию при любом порядке вставки."""
    keys = list(range(200))
    Rng(1234).shuffle(keys)
    tree: BinarySearchTree[int, int] = BinarySearchTree()
    for key in keys:
        tree.insert(key, key * 10)

    assert list(tree) == sorted(keys)
    assert [value for _, value in tree.items()] == [key * 10 for key in sorted(keys)]
    assert tree.min_key() == 0
    assert tree.max_key() == 199


def test_range_query_boundaries() -> None:
    """``range_query`` соблюдает включаемые и исключаемые границы."""
    tree: BinarySearchTree[int, str] = BinarySearchTree()
    for key in (10, 20, 30, 40):
        tree.insert(key, f"v{key}")

    assert [key for key, _ in tree.range_query(20, 30)] == [20, 30]
    assert list(tree.range_query(20, 30, inclusive=False)) == []
    assert [key for key, _ in tree.range_query(20, 40, inclusive=False)] == [30]
    assert [key for key, _ in tree.range_query(0, 100)] == [10, 20, 30, 40]
    assert list(tree.range_query(50, 60)) == []


def test_height() -> None:
    """Высота растёт по уровням, пустое дерево имеет высоту 0."""
    tree: BinarySearchTree[int, int] = BinarySearchTree()
    assert tree.height() == 0

    tree.insert(10, 0)
    assert tree.height() == 1

    tree.insert(5, 0)
    tree.insert(15, 0)
    assert tree.height() == 2

    tree.insert(3, 0)
    tree.insert(7, 0)
    assert tree.height() == 3


def test_remove_variants() -> None:
    """Удаление листа, узла с одним и с двумя потомками сохраняет порядок."""
    tree: BinarySearchTree[int, str] = BinarySearchTree()
    for key in (50, 30, 70, 20, 40, 60, 80):
        tree.insert(key, str(key))

    assert tree.remove(20) is True  # лист
    assert tree.remove(30) is True  # один потомок
    assert tree.remove(50) is True  # два потомка
    assert tree.remove(999) is False

    assert list(tree) == [40, 60, 70, 80]
    assert len(tree) == 4
    assert tree.value_count == 4


def test_remove_duplicates_removes_all_values() -> None:
    """Удаление ключа убирает все значения этого ключа."""
    tree: BinarySearchTree[int, str] = BinarySearchTree()
    tree.insert(1, "a")
    tree.insert(1, "b")
    tree.insert(2, "c")

    assert tree.remove(1) is True
    assert tree.get_all(1) == []
    assert tree.value_count == 1
    assert len(tree) == 1


def test_large_tree_without_recursion_error() -> None:
    """10 000 вставок в случайном порядке и полный обход не вызывают рекурсию."""
    keys = list(range(10_000))
    Rng(7).shuffle(keys)
    tree: BinarySearchTree[int, int] = BinarySearchTree()
    for key in keys:
        tree.insert(key, key)

    assert len(tree) == 10_000
    assert list(tree) == list(range(10_000))
    assert tree.min_key() == 0
    assert tree.max_key() == 9_999


def test_degenerate_tree_height_is_iterative() -> None:
    """Вырожденное дерево (вставка по возрастанию) обходится без рекурсии."""
    tree: BinarySearchTree[int, int] = BinarySearchTree()
    for key in range(2_000):
        tree.insert(key, key)

    assert tree.height() == 2_000
    assert list(tree) == list(range(2_000))


def test_clear() -> None:
    """``clear`` сбрасывает дерево в пустое состояние."""
    tree: BinarySearchTree[int, int] = BinarySearchTree()
    tree.insert(1, 1)
    tree.insert(2, 2)

    tree.clear()

    assert len(tree) == 0
    assert tree.value_count == 0
    assert tree.height() == 0
    assert tree.get(1) is None


def test_serialization_round_trip() -> None:
    """``to_dict``/``from_dict`` переживают JSON-сериализацию."""
    tree: BinarySearchTree[int, str] = BinarySearchTree()
    tree.insert(1, "a")
    tree.insert(1, "b")
    tree.insert(2, "c")

    data = tree.to_dict()
    restored = BinarySearchTree.from_dict(data)
    loaded = BinarySearchTree.from_dict(json.loads(json.dumps(data)))

    assert list(restored.items()) == list(tree.items())
    assert list(loaded.items()) == list(tree.items())
    assert len(loaded) == len(tree)
    assert loaded.value_count == tree.value_count


def test_string_keys() -> None:
    """Дерево работает не только с целочисленными ключами."""
    tree: BinarySearchTree[str, int] = BinarySearchTree()
    tree.insert("b", 2)
    tree.insert("a", 1)
    tree.insert("c", 3)

    assert list(tree) == ["a", "b", "c"]
    assert tree.min_key() == "a"
    assert tree.max_key() == "c"
