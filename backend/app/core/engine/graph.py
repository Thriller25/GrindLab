"""
FlowsheetGraph — Граф технологической схемы.

Реализует топологическую сортировку и поиск рециклов.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """Узел графа."""

    id: str
    node_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    material_id: str | None = None


@dataclass
class GraphEdge:
    """Ребро графа (связь между узлами)."""

    id: str
    source: str  # node_id
    target: str  # node_id
    source_port: str = "out"
    target_port: str = "in"


@dataclass
class FlowsheetGraph:
    """
    Граф технологической схемы.

    Поддерживает:
    - Топологическую сортировку (Kahn's algorithm)
    - Обнаружение рециклов
    - Поиск входных узлов (feed)
    - Поиск выходных узлов (product)
    """

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    # Кэшированные структуры
    _adjacency: dict[str, list[str]] = field(default_factory=dict)
    _reverse_adjacency: dict[str, list[str]] = field(default_factory=dict)
    _edge_map: dict[tuple[str, str], GraphEdge] = field(default_factory=dict)

    def __post_init__(self):
        self._rebuild_adjacency()

    def _rebuild_adjacency(self):
        """Построить списки смежности."""
        self._adjacency = defaultdict(list)
        self._reverse_adjacency = defaultdict(list)
        self._edge_map = {}

        for edge in self.edges:
            self._adjacency[edge.source].append(edge.target)
            self._reverse_adjacency[edge.target].append(edge.source)
            self._edge_map[(edge.source, edge.target)] = edge

    @classmethod
    def from_flowsheet_data(
        cls, nodes_data: list[dict], edges_data: list[dict]
    ) -> "FlowsheetGraph":
        """
        Создать граф из данных флоушита (формат React Flow).

        Args:
            nodes_data: список узлов [{id, type, data: {type, label, parameters, ...}}]
            edges_data: список связей [{id, source, target, sourceHandle, targetHandle}]
        """
        nodes = {}
        for n in nodes_data:
            node_data = n.get("data", {})
            nodes[n["id"]] = GraphNode(
                id=n["id"],
                node_type=node_data.get("type", n.get("type", "unknown")),
                parameters=node_data.get("parameters", {}),
                label=node_data.get("label", ""),
                material_id=node_data.get("materialId"),
            )

        edges = []
        for e in edges_data:
            edges.append(
                GraphEdge(
                    id=e["id"],
                    source=e["source"],
                    target=e["target"],
                    source_port=e.get("sourceHandle", "out"),
                    target_port=e.get("targetHandle", "in"),
                )
            )

        graph = cls(nodes=nodes, edges=edges)
        graph._rebuild_adjacency()
        return graph

    def get_feed_nodes(self) -> list[GraphNode]:
        """Получить узлы питания (без входящих связей или type=feed)."""
        feeds = []
        for node_id, node in self.nodes.items():
            if node.node_type == "feed":
                feeds.append(node)
            elif not self._reverse_adjacency.get(node_id):
                # Узел без входящих связей — тоже может быть источником
                feeds.append(node)
        return feeds

    def get_product_nodes(self) -> list[GraphNode]:
        """Получить узлы продукта (без исходящих связей или type=product)."""
        products = []
        for node_id, node in self.nodes.items():
            if node.node_type == "product":
                products.append(node)
            elif not self._adjacency.get(node_id):
                products.append(node)
        return products

    def get_predecessors(self, node_id: str) -> list[str]:
        """Получить предшественников узла."""
        return list(self._reverse_adjacency.get(node_id, []))

    def get_successors(self, node_id: str) -> list[str]:
        """Получить последователей узла."""
        return list(self._adjacency.get(node_id, []))

    def get_edge(self, source_id: str, target_id: str) -> GraphEdge | None:
        """Получить ребро между узлами."""
        return self._edge_map.get((source_id, target_id))

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        """Получить все входящие рёбра узла."""
        result = []
        for src in self._reverse_adjacency.get(node_id, []):
            edge = self._edge_map.get((src, node_id))
            if edge:
                result.append(edge)
        return result

    def get_outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        """Получить все исходящие рёбра узла."""
        result = []
        for tgt in self._adjacency.get(node_id, []):
            edge = self._edge_map.get((node_id, tgt))
            if edge:
                result.append(edge)
        return result

    def topological_sort(self) -> tuple[list[str], list[GraphEdge]]:
        """
        Топологическая сортировка с обнаружением рециклов (Kahn's algorithm).

        Returns:
            (sorted_node_ids, back_edges) — отсортированные узлы и обратные рёбра (рециклы)
        """
        # Подсчёт входящих степеней
        in_degree = {node_id: 0 for node_id in self.nodes}
        for edge in self.edges:
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        # Очередь узлов с нулевой входящей степенью
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        sorted_nodes = []

        while queue:
            node_id = queue.popleft()
            sorted_nodes.append(node_id)

            for successor in self._adjacency.get(node_id, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        # Если не все узлы обработаны — есть циклы
        back_edges = []
        if len(sorted_nodes) < len(self.nodes):
            # Находим рёбра, образующие циклы
            sorted_set = set(sorted_nodes)
            for edge in self.edges:
                if edge.source not in sorted_set or edge.target not in sorted_set:
                    back_edges.append(edge)

            # Добавляем оставшиеся узлы в конец (для итеративного расчёта)
            for node_id in self.nodes:
                if node_id not in sorted_set:
                    sorted_nodes.append(node_id)

        return sorted_nodes, back_edges

    def has_cycles(self) -> bool:
        """Проверить наличие циклов в графе."""
        _, back_edges = self.topological_sort()
        return len(back_edges) > 0

    def find_recycle_streams(self) -> list[GraphEdge]:
        """Найти рёбра, образующие рециклы."""
        _, back_edges = self.topological_sort()
        return back_edges

    def validate(self) -> list[str]:
        """
        Валидация графа.

        Returns:
            Список ошибок (пустой если всё ок)
        """
        errors = []

        # Проверка наличия узлов
        if not self.nodes:
            errors.append("Flowsheet has no nodes")
            return errors

        # Проверка наличия feed узлов
        feeds = self.get_feed_nodes()
        if not feeds:
            errors.append("No feed nodes found")

        # Проверка наличия product узлов
        products = self.get_product_nodes()
        if not products:
            errors.append("No product nodes found")

        # Проверка связности — все узлы должны быть достижимы из feed
        reachable = set()
        queue = deque([f.id for f in feeds])
        while queue:
            node_id = queue.popleft()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            for successor in self._adjacency.get(node_id, []):
                if successor not in reachable:
                    queue.append(successor)

        unreachable = set(self.nodes.keys()) - reachable
        if unreachable:
            errors.append(f"Unreachable nodes: {', '.join(unreachable)}")

        # Проверка что все связи ведут к существующим узлам
        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Edge {edge.id} references unknown source: {edge.source}")
            if edge.target not in self.nodes:
                errors.append(f"Edge {edge.id} references unknown target: {edge.target}")

        return errors
