from collections import defaultdict
from collections.abc import Iterable

from twin.common.topology import Edge


class AssetGraph:
    def __init__(self, edges: Iterable[Edge]) -> None:
        self._depends_on: dict[str, set[str]] = defaultdict(set)
        self._dependents: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            self._depends_on[edge.src].add(edge.dst)
            self._dependents[edge.dst].add(edge.src)

    def dependencies(self, node: str) -> set[str]:
        return set(self._depends_on.get(node, ()))

    def dependents(self, node: str) -> set[str]:
        return set(self._dependents.get(node, ()))

    def upstream(self, node: str) -> set[str]:
        return self._walk(node, self._depends_on)

    def downstream(self, node: str) -> set[str]:
        return self._walk(node, self._dependents)

    @staticmethod
    def _walk(start: str, adjacency: dict[str, set[str]]) -> set[str]:
        seen: set[str] = set()
        stack = [start]
        while stack:
            for neighbour in adjacency.get(stack.pop(), ()):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        return seen
