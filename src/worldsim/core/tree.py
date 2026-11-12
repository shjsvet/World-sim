"""Бинарное дерево поиска с поддержкой нескольких значений на ключ."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Generic, Self, TypeVar

K = TypeVar("K", int, str)
V = TypeVar("V")


def _equal(left: K, right: K) -> bool:
    """Сравнивает ключи через ``<``, не требуя поддержки ``__eq__``."""
    return not left < right and not right < left


class _Node(Generic[K, V]):
    """Узел дерева: ключ, список значений и ссылки на потомков."""

    __slots__ = ("key", "left", "right", "values")

    def __init__(self, key: K, value: V) -> None:
        self.key: K = key
        self.values: list[V] = [value]
        self.left: _Node[K, V] | None = None
        self.right: _Node[K, V] | None = None


class BinarySearchTree(Generic[K, V]):
    """BST-мультимножество: одному ключу соответствует список значений.

    Итерация и обходы выполняются итеративно, поэтому дерево переживает
    вставку десятков тысяч элементов без ``RecursionError``.

    ``len(tree)`` возвращает число ключей (узлов), а ``value_count`` — общее
    число сохранённых значений. Для снимков мира ключом служит год, поэтому
    значение может повторяться.
    """

    def __init__(self) -> None:
        self._root: _Node[K, V] | None = None
        self._key_count = 0
        self._value_count = 0

    def __len__(self) -> int:
        """Возвращает число ключей в дереве."""
        return self._key_count

    @property
    def key_count(self) -> int:
        """Число ключей (то же, что ``len(tree)``)."""
        return self._key_count

    @property
    def value_count(self) -> int:
        """Общее число сохранённых значений, включая дубликаты ключей."""
        return self._value_count

    def insert(self, key: K, value: V) -> None:
        """Добавляет значение по ключу.

        Если ключ уже есть, значение дописывается в список значений этого ключа.

        Args:
            key: Ключ узла.
            value: Сохраняемое значение.
        """
        if self._root is None:
            self._root = _Node(key, value)
            self._key_count = 1
            self._value_count = 1
            return

        node = self._root
        while True:
            if _equal(key, node.key):
                node.values.append(value)
                self._value_count += 1
                return
            if key < node.key:
                if node.left is None:
                    node.left = _Node(key, value)
                    self._key_count += 1
                    self._value_count += 1
                    return
                node = node.left
            else:
                if node.right is None:
                    node.right = _Node(key, value)
                    self._key_count += 1
                    self._value_count += 1
                    return
                node = node.right

    def get(self, key: K) -> V | None:
        """Возвращает первое значение по ключу или ``None``."""
        node = self._find_node(key)
        return None if node is None else node.values[0]

    def get_all(self, key: K) -> list[V]:
        """Возвращает копию списка всех значений по ключу (пустой, если ключа нет)."""
        node = self._find_node(key)
        return [] if node is None else list(node.values)

    def contains(self, key: K) -> bool:
        """Проверяет наличие ключа в дереве."""
        return self._find_node(key) is not None

    def min_key(self) -> K | None:
        """Возвращает минимальный ключ или ``None`` для пустого дерева."""
        if self._root is None:
            return None
        node = self._root
        while node.left is not None:
            node = node.left
        return node.key

    def max_key(self) -> K | None:
        """Возвращает максимальный ключ или ``None`` для пустого дерева."""
        if self._root is None:
            return None
        node = self._root
        while node.right is not None:
            node = node.right
        return node.key

    def __iter__(self) -> Iterator[K]:
        """Итерирует ключи по возрастанию (in-order)."""
        return self.keys()

    def keys(self) -> Iterator[K]:
        """Итерирует ключи по возрастанию."""
        for key, _ in self._key_items():
            yield key

    def items(self) -> Iterator[tuple[K, V]]:
        """Итерирует пары ``(ключ, значение)`` в порядке возрастания ключей."""
        for key, values in self._key_items():
            for value in values:
                yield (key, value)

    def range_query(self, low: K, high: K, inclusive: bool = True) -> Iterator[tuple[K, V]]:
        """Итерирует пары с ключом в диапазоне ``[low, high]``.

        Args:
            low: Нижняя граница.
            high: Верхняя граница.
            inclusive: Если ``True``, границы включаются; иначе исключаются.

        Yields:
            Пары ``(ключ, значение)`` по возрастанию ключей.
        """
        for key, values in self._key_items():
            if not self._inside(key, low, high, inclusive):
                continue
            for value in values:
                yield (key, value)

    def height(self) -> int:
        """Возвращает высоту дерева; пустое дерево имеет высоту 0."""
        if self._root is None:
            return 0
        max_depth = 1
        stack: list[tuple[_Node[K, V], int]] = [(self._root, 1)]
        while stack:
            node, depth = stack.pop()
            if depth > max_depth:
                max_depth = depth
            if node.left is not None:
                stack.append((node.left, depth + 1))
            if node.right is not None:
                stack.append((node.right, depth + 1))
        return max_depth

    def remove(self, key: K) -> bool:
        """Удаляет ключ вместе со всеми его значениями.

        Args:
            key: Удаляемый ключ.

        Returns:
            ``True``, если ключ был найден и удалён.
        """
        parent: _Node[K, V] | None = None
        node = self._root
        while node is not None and not _equal(key, node.key):
            parent = node
            node = node.left if key < node.key else node.right
        if node is None:
            return False

        self._key_count -= 1
        self._value_count -= len(node.values)
        self._delete_node(parent, node)
        return True

    def clear(self) -> None:
        """Удаляет все узлы и обнуляет счётчики."""
        self._root = None
        self._key_count = 0
        self._value_count = 0

    def to_dict(self) -> dict[str, list[tuple[K, list[V]]]]:
        """Сериализует дерево в JSON-совместимый словарь.

        Returns:
            Словарь ``{"items": [(ключ, [значения]), ...]}`` по возрастанию ключей.
        """
        return {"items": [(key, list(values)) for key, values in self._key_items()]}

    @classmethod
    def from_dict(cls, data: Mapping[str, list[tuple[K, list[V]]]]) -> Self:
        """Восстанавливает дерево из словаря, созданного ``to_dict``.

        Args:
            data: Словарь с ключом ``items``.

        Returns:
            Новое дерево с теми же ключами и значениями.
        """
        tree: Self = cls()
        for key, values in data["items"]:
            for value in values:
                tree.insert(key, value)
        return tree

    def __repr__(self) -> str:
        """Краткое представление без рекурсивного обхода."""
        return f"BinarySearchTree(keys={self._key_count}, values={self._value_count})"

    def _find_node(self, key: K) -> _Node[K, V] | None:
        """Ищет узел по ключу итеративно."""
        node = self._root
        while node is not None:
            if _equal(key, node.key):
                return node
            node = node.left if key < node.key else node.right
        return None

    def _key_items(self) -> Iterator[tuple[K, list[V]]]:
        """Итерирует ``(ключ, значения)`` в порядке возрастания ключей."""
        stack: list[_Node[K, V]] = []
        node = self._root
        while stack or node is not None:
            while node is not None:
                stack.append(node)
                node = node.left
            node = stack.pop()
            yield (node.key, node.values)
            node = node.right

    @staticmethod
    def _inside(key: K, low: K, high: K, inclusive: bool) -> bool:
        """Проверяет попадание ключа в диапазон."""
        if inclusive:
            return not key < low and not high < key
        return low < key and key < high

    def _delete_node(self, parent: _Node[K, V] | None, node: _Node[K, V]) -> None:
        """Удаляет узел из дерева, сохраняя порядок."""
        if node.left is None and node.right is None:
            self._replace_child(parent, node, None)
            return
        if node.left is None:
            self._replace_child(parent, node, node.right)
            return
        if node.right is None:
            self._replace_child(parent, node, node.left)
            return

        successor_parent = node
        successor = node.right
        while successor.left is not None:
            successor_parent = successor
            successor = successor.left

        node.key = successor.key
        node.values = successor.values
        if successor_parent is node:
            successor_parent.right = successor.right
        else:
            successor_parent.left = successor.right

    def _replace_child(
        self,
        parent: _Node[K, V] | None,
        node: _Node[K, V],
        replacement: _Node[K, V] | None,
    ) -> None:
        """Подменяет ссылку родителя на потомка."""
        if parent is None:
            self._root = replacement
        elif parent.left is node:
            parent.left = replacement
        else:
            parent.right = replacement
