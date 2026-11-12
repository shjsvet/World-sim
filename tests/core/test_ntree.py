"""Тесты N-арного дерева."""

from __future__ import annotations

import json

import pytest

from worldsim.core.ntree import Node


def build_sample() -> tuple[Node[str], Node[str], Node[str], Node[str]]:
    """Собирает дерево root → (a → b, c) и возвращает все узлы."""
    root: Node[str] = Node(1, "root", "world")
    a: Node[str] = Node(2, "a", "continent")
    b: Node[str] = Node(3, "b", "region")
    c: Node[str] = Node(4, "c", "region2")
    root.add_child(a)
    root.add_child(c)
    a.add_child(b)
    return root, a, b, c


def test_add_child_sets_parent_and_order() -> None:
    """Дети добавляются в порядке вызова, родитель выставлен."""
    root, a, b, c = build_sample()

    assert root.children == [a, c]
    assert a.parent is root
    assert b.parent is a
    assert c.parent is root
    assert a.children == [b]


def test_add_self_is_forbidden() -> None:
    """Узел нельзя добавить ребёнком самому себе."""
    node: Node[str] = Node(1, "node")

    with pytest.raises(ValueError, match="самого себя"):
        node.add_child(node)


def test_add_node_with_parent_is_forbidden() -> None:
    """Узел с родителем нельзя добавить повторно."""
    root, _, b, _ = build_sample()

    with pytest.raises(ValueError, match="уже имеет родителя"):
        root.add_child(b)


def test_add_child_cycle_is_forbidden() -> None:
    """Нельзя сделать предка ребёнком потомка."""
    root, _, b, _ = build_sample()

    with pytest.raises(ValueError, match="предком"):
        b.add_child(root)

    assert root.parent is None
    assert b.children == []


def test_move_to_reparents_node() -> None:
    """Перенос к другому родителю убирает узел из старых детей."""
    _, a, b, c = build_sample()

    b.move_to(c)

    assert a.children == []
    assert c.children == [b]
    assert b.parent is c


def test_move_to_root_detaches_node() -> None:
    """``move_to(None)`` делает узел корнем."""
    _, a, b, _ = build_sample()

    b.move_to(None)

    assert b.parent is None
    assert a.children == []


def test_move_to_cycle_is_forbidden() -> None:
    """Нельзя перенести предка под собственного потомка."""
    root, a, b, _ = build_sample()

    with pytest.raises(ValueError, match="цикл"):
        root.move_to(b)

    assert root.parent is None
    assert a.parent is root


def test_remove_child() -> None:
    """``remove_child`` сообщает результат и снимает родителя."""
    root, a, _b, c = build_sample()

    assert root.remove_child(c) is True
    assert c.parent is None
    assert root.children == [a]
    assert root.remove_child(c) is False


def test_find_path_and_depth() -> None:
    """Поиск, путь до корня и глубина работают на поддереве."""
    root, a, b, _ = build_sample()

    assert root.find(3) is b
    assert a.find(3) is b
    assert b.find(1) is None
    assert [node.id for node in b.path_to_root()] == [3, 2, 1]
    assert root.depth() == 0
    assert a.depth() == 1
    assert b.depth() == 2


def test_walk_orders_and_leaves() -> None:
    """Pre-order, post-order и листья возвращают узлы в правильном порядке."""
    root, _a, _b, _c = build_sample()

    assert [node.id for node in root.walk()] == [1, 2, 3, 4]
    assert [node.id for node in root.walk_postorder()] == [3, 2, 4, 1]
    assert [node.id for node in root.leaves()] == [3, 4]


def test_serialization_round_trip() -> None:
    """``to_dict`` и ``from_dict`` сохраняют структуру и значения."""
    root, _, _, _ = build_sample()

    data = root.to_dict()
    restored = Node.from_dict(data)
    payload = Node.from_dict(json.loads(json.dumps(data)))

    assert [node.id for node in restored.walk()] == [1, 2, 3, 4]
    assert restored.find(3) is not None
    assert restored.find(3).value == "region"  # type: ignore[union-attr]
    assert [node.id for node in payload.walk()] == [1, 2, 3, 4]
    assert payload.find(2).parent is payload  # type: ignore[union-attr]


def test_deep_tree_without_recursion_error() -> None:
    """Глубокое дерево (10 000 узлов) обходится и сериализуется без падения."""
    root: Node[int] = Node(0, "root", 0)
    current = root
    for node_id in range(1, 10_000):
        child: Node[int] = Node(node_id, f"node-{node_id}", node_id)
        current.add_child(child)
        current = child

    assert sum(1 for _ in root.walk()) == 10_000
    assert current.depth() == 9_999
    assert len(root.to_dict()["children"]) == 1

    restored = Node.from_dict(root.to_dict())
    assert restored.find(9_999) is not None
    assert restored.find(9_999).depth() == 9_999  # type: ignore[union-attr]


def test_repr_is_not_recursive() -> None:
    """``repr`` глубокого дерева не уходит в рекурсию."""
    root: Node[int] = Node(0, "root", 0)
    current = root
    for node_id in range(1, 3_000):
        child: Node[int] = Node(node_id, f"node-{node_id}", node_id)
        current.add_child(child)
        current = child

    text = repr(root)

    assert "children=1" in text
    assert "node-2999" not in text


def test_negative_id_is_forbidden() -> None:
    """Отрицательный id узла отклоняется."""
    with pytest.raises(ValueError, match="отрицательным"):
        Node(-1, "bad")
