"""N-арное дерево (Composite) для иерархий мира: континент → регион → тайл."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


class Node(Generic[T]):
    """Узел N-арного дерева с родителем, детьми и полезной нагрузкой.

    Дерево защищено от циклов: ни ``add_child``, ни ``move_to`` не позволяют
    сделать узел потомком самого себя или своего потомка.
    """

    __slots__ = ("children", "id", "name", "parent", "value")

    def __init__(self, node_id: int, name: str = "", value: T | None = None) -> None:
        """Создаёт узел без родителя.

        Args:
            node_id: Уникальный идентификатор узла (неотрицательный).
            name: Человекочитаемое имя узла.
            value: Полезная нагрузка произвольного типа.

        Raises:
            ValueError: Если ``node_id`` отрицательный.
        """
        if node_id < 0:
            raise ValueError("id узла не может быть отрицательным")
        self.id: int = node_id
        self.name: str = name
        self.value: T | None = value
        self.parent: Node[T] | None = None
        self.children: list[Node[T]] = []

    def add_child(self, node: Node[T]) -> None:
        """Добавляет узел в дети.

        Args:
            node: Узел без родителя, который станет ребёнком.

        Raises:
            ValueError: Если узел добавляется сам в себя, уже имеет родителя
                или является предком текущего узла (цикл).
        """
        if node is self:
            raise ValueError("узел не может быть ребёнком самого себя")
        if node.parent is not None:
            raise ValueError(f"узел {node.id} уже имеет родителя")
        if node.children and node.is_ancestor(self):
            raise ValueError(f"узел {node.id} является предком и создаст цикл")
        node.parent = self
        self.children.append(node)

    def remove_child(self, node: Node[T]) -> bool:
        """Убирает узел из детей, если он там есть.

        Args:
            node: Узел-ребёнок.

        Returns:
            ``True``, если узел был ребёнком и удалён.
        """
        try:
            self.children.remove(node)
        except ValueError:
            return False
        node.parent = None
        return True

    def move_to(self, new_parent: Node[T] | None) -> None:
        """Переносит узел к другому родителю.

        Args:
            new_parent: Новый родитель или ``None``, чтобы сделать узел корнем.

        Raises:
            ValueError: Если перенос создаёт цикл.
        """
        if new_parent is None:
            if self.parent is not None:
                self.parent.remove_child(self)
            return
        if new_parent is self:
            raise ValueError("узел не может быть родителем самого себя")
        if self.is_ancestor(new_parent):
            raise ValueError(f"перенос к узлу {new_parent.id} создаст цикл")
        if self.parent is new_parent:
            return
        if self.parent is not None:
            self.parent.remove_child(self)
        new_parent.add_child(self)

    def find(self, node_id: int) -> Node[T] | None:
        """Ищет узел по id в поддереве, начиная с текущего узла."""
        for node in self.walk():
            if node.id == node_id:
                return node
        return None

    def path_to_root(self) -> list[Node[T]]:
        """Возвращает путь от текущего узла до корня включительно."""
        path: list[Node[T]] = []
        node: Node[T] | None = self
        while node is not None:
            path.append(node)
            node = node.parent
        return path

    def depth(self) -> int:
        """Возвращает глубину узла: корень имеет глубину 0."""
        depth = 0
        node = self.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    def is_ancestor(self, other: Node[T]) -> bool:
        """Проверяет, является ли текущий узел предком ``other``."""
        node = other.parent
        while node is not None:
            if node is self:
                return True
            node = node.parent
        return False

    def walk(self) -> Iterator[Node[T]]:
        """Обходит поддерево в прямом порядке (pre-order), включая себя."""
        stack: list[Node[T]] = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def walk_postorder(self) -> Iterator[Node[T]]:
        """Обходит поддерево в обратном порядке (post-order), включая себя."""
        stack: list[tuple[Node[T], bool]] = [(self, False)]
        while stack:
            node, visited = stack.pop()
            if visited:
                yield node
                continue
            stack.append((node, True))
            for child in reversed(node.children):
                stack.append((child, False))

    def leaves(self) -> Iterator[Node[T]]:
        """Итерирует листья поддерева."""
        for node in self.walk():
            if not node.children:
                yield node

    def to_dict(self) -> dict[str, Any]:
        """Сериализует поддерево в JSON-совместимый словарь.

        Обход итеративный, поэтому глубокие деревья не упираются в лимит
        рекурсии. Значения должны быть JSON-сериализуемыми.

        Returns:
            Словарь с ключами ``id``, ``name``, ``value`` и ``children``.
        """
        root: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "children": [],
        }
        stack: list[tuple[Node[T], dict[str, Any]]] = [(self, root)]
        while stack:
            node, payload = stack.pop()
            children: list[dict[str, Any]] = []
            for child in node.children:
                child_payload: dict[str, Any] = {
                    "id": child.id,
                    "name": child.name,
                    "value": child.value,
                    "children": [],
                }
                children.append(child_payload)
                stack.append((child, child_payload))
            payload["children"] = children
        return root

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Node[T]:
        """Восстанавливает поддерево из словаря, созданного ``to_dict``.

        Args:
            data: Словарь с ключами ``id``, ``name``, ``value`` и ``children``.

        Returns:
            Корень восстановленного дерева; ссылки ``parent`` выставлены.
        """
        root: Node[T] = cls(int(data["id"]), str(data["name"]), data.get("value"))
        stack: list[tuple[Node[T], Mapping[str, Any]]] = [(root, data)]
        while stack:
            node, payload = stack.pop()
            children = cast("list[Mapping[str, Any]]", payload.get("children", []))
            for child_data in children:
                child: Node[T] = cls(
                    int(child_data["id"]),
                    str(child_data["name"]),
                    child_data.get("value"),
                )
                node.add_child(child)
                stack.append((child, child_data))
        return root

    def __repr__(self) -> str:
        """Краткое представление без рекурсивного обхода детей."""
        return (
            f"Node(id={self.id}, name={self.name!r}, "
            f"children={len(self.children)}, depth={self.depth()})"
        )
