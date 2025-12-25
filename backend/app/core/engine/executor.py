"""
FlowsheetExecutor — Исполнитель расчёта технологической схемы.

Выполняет:
1. Валидацию графа
2. Топологическую сортировку
3. Последовательный расчёт узлов
4. Итеративную конвергенцию для рециклов
5. Сбор KPI
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .graph import FlowsheetGraph, GraphEdge
from .stream import Stream
from .unit_models import UnitModel, UnitResult, create_unit_model

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Результат выполнения расчёта."""

    success: bool
    streams: dict[str, Stream] = field(default_factory=dict)  # edge_id -> Stream
    node_kpi: dict[str, dict[str, float]] = field(default_factory=dict)  # node_id -> kpi
    global_kpi: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    iterations: int = 0
    converged: bool = True
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "streams": {k: v.to_dict() for k, v in self.streams.items()},
            "node_kpi": self.node_kpi,
            "global_kpi": self.global_kpi,
            "errors": self.errors,
            "warnings": self.warnings,
            "iterations": self.iterations,
            "converged": self.converged,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


class FlowsheetExecutor:
    """
    Исполнитель расчёта технологической схемы.

    Использование:
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()
    """

    def __init__(
        self,
        graph: FlowsheetGraph,
        max_iterations: int = 50,
        convergence_tolerance: float = 0.01,
    ):
        self.graph = graph
        self.max_iterations = max_iterations
        self.convergence_tolerance = convergence_tolerance

        # Состояние расчёта
        self._unit_models: dict[str, UnitModel] = {}
        self._streams: dict[str, Stream] = {}  # edge_id -> Stream
        self._node_inputs: dict[str, dict[str, Stream]] = {}  # node_id -> {port_id -> Stream}
        self._node_outputs: dict[str, dict[str, Stream]] = {}  # node_id -> {port_id -> Stream}
        self._node_kpi: dict[str, dict[str, float]] = {}

    def execute(self) -> ExecutionResult:
        """Выполнить расчёт схемы."""
        start_time = time.perf_counter()
        result = ExecutionResult(success=False)

        try:
            # 1. Валидация графа
            validation_errors = self.graph.validate()
            if validation_errors:
                result.errors = validation_errors
                return result

            # 2. Создание моделей узлов
            self._create_unit_models()

            # 3. Топологическая сортировка
            sorted_nodes, recycle_edges = self.graph.topological_sort()
            has_recycles = len(recycle_edges) > 0

            if has_recycles:
                logger.info(f"Found {len(recycle_edges)} recycle streams, using iterative solver")
                result.warnings.append(f"Found {len(recycle_edges)} recycle stream(s)")

            # 4. Расчёт
            if has_recycles:
                self._execute_with_convergence(sorted_nodes, recycle_edges, result)
            else:
                self._execute_sequential(sorted_nodes, result)

            # 5. Сбор результатов
            result.streams = dict(self._streams)
            result.node_kpi = dict(self._node_kpi)
            result.global_kpi = self._compute_global_kpi()
            result.success = len(result.errors) == 0

        except Exception as e:
            logger.exception("Execution failed")
            result.errors.append(f"Execution error: {str(e)}")
            result.success = False

        finally:
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

        return result

    def _create_unit_models(self):
        """Создать модели для всех узлов."""
        for node_id, node in self.graph.nodes.items():
            self._unit_models[node_id] = create_unit_model(
                node_id=node_id,
                node_type=node.node_type,
                params=node.parameters,
            )

    def _execute_sequential(self, sorted_nodes: list[str], result: ExecutionResult):
        """Последовательный расчёт без рециклов."""
        for node_id in sorted_nodes:
            self._calculate_node(node_id, result)

        result.iterations = 1
        result.converged = True

    def _execute_with_convergence(
        self,
        sorted_nodes: list[str],
        recycle_edges: list[GraphEdge],
        result: ExecutionResult,
    ):
        """Итеративный расчёт с конвергенцией для рециклов."""
        # Инициализация рецикловых потоков нулями
        for edge in recycle_edges:
            self._streams[edge.id] = Stream(
                id=edge.id,
                mass_tph=0.0,
                solids_pct=70.0,
                source_node_id=edge.source,
                source_port=edge.source_port,
                target_node_id=edge.target,
                target_port=edge.target_port,
            )

        prev_recycle_values: dict[str, float] = {}
        converged = False

        for iteration in range(1, self.max_iterations + 1):
            # Расчёт всех узлов
            for node_id in sorted_nodes:
                self._calculate_node(node_id, result)

            # Проверка конвергенции рециклов
            max_change = 0.0
            for edge in recycle_edges:
                stream = self._streams.get(edge.id)
                if stream:
                    current_value = stream.mass_tph
                    prev_value = prev_recycle_values.get(edge.id, 0.0)

                    if prev_value > 0:
                        change = abs(current_value - prev_value) / prev_value
                        max_change = max(max_change, change)

                    prev_recycle_values[edge.id] = current_value

            logger.debug(f"Iteration {iteration}: max_change = {max_change:.4f}")

            if iteration > 1 and max_change < self.convergence_tolerance:
                converged = True
                break

        result.iterations = iteration
        result.converged = converged

        if not converged:
            result.warnings.append(
                f"Did not converge after {self.max_iterations} iterations "
                f"(max_change={max_change:.4f})"
            )

    def _calculate_node(self, node_id: str, result: ExecutionResult):
        """Рассчитать один узел."""
        model = self._unit_models.get(node_id)
        if not model:
            result.errors.append(f"No model for node {node_id}")
            return

        # Собираем входные потоки
        inputs = self._collect_node_inputs(node_id)
        self._node_inputs[node_id] = inputs

        # Расчёт
        try:
            unit_result: UnitResult = model.calculate(inputs)
        except Exception as e:
            result.errors.append(f"Error in node {node_id}: {str(e)}")
            return

        if unit_result.error:
            result.errors.append(f"Node {node_id}: {unit_result.error}")
            return

        # Сохраняем выходы
        self._node_outputs[node_id] = unit_result.outputs
        self._node_kpi[node_id] = unit_result.kpi

        # Распространяем потоки по рёбрам
        for edge in self.graph.get_outgoing_edges(node_id):
            output_stream = unit_result.outputs.get(edge.source_port)
            if output_stream:
                # Клонируем поток для ребра
                edge_stream = output_stream.clone(edge.id)
                edge_stream.target_node_id = edge.target
                edge_stream.target_port = edge.target_port
                self._streams[edge.id] = edge_stream

    def _collect_node_inputs(self, node_id: str) -> dict[str, Stream]:
        """Собрать входные потоки для узла."""
        inputs: dict[str, Stream] = {}

        for edge in self.graph.get_incoming_edges(node_id):
            stream = self._streams.get(edge.id)
            if stream:
                port = edge.target_port or "feed"
                # Если уже есть поток на этот порт — смешиваем
                if port in inputs:
                    existing = inputs[port]
                    inputs[port] = self._blend_streams(existing, stream)
                else:
                    inputs[port] = stream

        return inputs

    def _blend_streams(self, s1: Stream, s2: Stream) -> Stream:
        """Смешать два потока."""
        total_mass = s1.mass_tph + s2.mass_tph
        if total_mass <= 0:
            return s1.clone(f"{s1.id}+{s2.id}")

        # Взвешенное среднее плотности
        frac1 = s1.mass_tph / total_mass
        frac2 = s2.mass_tph / total_mass
        blended_solids = s1.solids_pct * frac1 + s2.solids_pct * frac2

        # Смешение PSD
        blended_psd = None
        if s1.psd and s2.psd:
            blended_psd = s1.psd.blend_with(s2.psd, frac1)
        elif s1.psd:
            blended_psd = s1.psd
        elif s2.psd:
            blended_psd = s2.psd

        return Stream(
            id=f"{s1.id}+{s2.id}",
            mass_tph=total_mass,
            solids_pct=blended_solids,
            psd=blended_psd,
        )

    def _compute_global_kpi(self) -> dict[str, float]:
        """Вычислить глобальные KPI схемы."""
        kpi: dict[str, float] = {}

        # Суммарное питание
        total_feed = 0.0
        feed_f80 = None
        feed_f50 = None
        for node in self.graph.get_feed_nodes():
            node_kpi = self._node_kpi.get(node.id, {})
            total_feed += node_kpi.get("feed_tph", 0.0)
            if feed_f80 is None:
                feed_f80 = node_kpi.get("f80_mm")
                feed_f50 = node_kpi.get("f50_mm")

        kpi["total_feed_tph"] = round(total_feed, 1)
        if feed_f80:
            kpi["feed_f80_mm"] = round(feed_f80, 2)
        if feed_f50:
            kpi["feed_f50_mm"] = round(feed_f50, 2)

        # Суммарный продукт
        total_product = 0.0
        product_p80_weighted = 0.0
        product_p50_weighted = 0.0
        product_p98_weighted = 0.0
        product_passing_240_weighted = 0.0

        for node in self.graph.get_product_nodes():
            node_kpi = self._node_kpi.get(node.id, {})
            prod_tph = node_kpi.get("product_tph", 0.0)
            prod_p80 = node_kpi.get("p80_mm", 0.0)
            prod_p50 = node_kpi.get("p50_mm", 0.0)
            prod_p98 = node_kpi.get("p98_mm", 0.0)
            prod_passing_240 = node_kpi.get("passing_240_mesh_pct", 0.0)

            total_product += prod_tph
            product_p80_weighted += prod_tph * prod_p80
            product_p50_weighted += prod_tph * prod_p50
            product_p98_weighted += prod_tph * prod_p98
            product_passing_240_weighted += prod_tph * prod_passing_240

        kpi["total_product_tph"] = round(total_product, 1)
        if total_product > 0:
            kpi["product_p80_mm"] = round(product_p80_weighted / total_product, 4)
            kpi["product_p50_mm"] = round(product_p50_weighted / total_product, 4)
            kpi["product_p98_mm"] = round(product_p98_weighted / total_product, 4)
            kpi["product_passing_240_mesh_pct"] = round(
                product_passing_240_weighted / total_product, 1
            )

        # Массовый баланс
        if total_feed > 0:
            kpi["mass_balance_error_pct"] = round(
                100 * (total_product - total_feed) / total_feed, 2
            )
        else:
            kpi["mass_balance_error_pct"] = 0.0

        # Суммарная мощность
        total_power = 0.0
        for node_kpi in self._node_kpi.values():
            total_power += node_kpi.get("power_kw", 0.0)

        kpi["total_power_kw"] = round(total_power, 1)
        if total_product > 0:
            kpi["specific_energy_kwh_t"] = round(total_power / total_product, 2)

        # Коэффициент измельчения
        if feed_f80 and kpi.get("product_p80_mm"):
            kpi["reduction_ratio"] = round(feed_f80 / kpi["product_p80_mm"], 1)

        # Circulating Load — рассчитываем для рециклов
        circulating_load = self._compute_circulating_load()
        if circulating_load is not None:
            kpi["circulating_load_pct"] = circulating_load

        return kpi

    def _compute_circulating_load(self) -> Optional[float]:
        """
        Вычислить Circulating Load (циркулирующую нагрузку).

        CL = (масса рецикла / масса свежего питания) * 100%

        Для схемы с гидроциклоном:
        CL = underflow / fresh_feed * 100
        """
        # Находим все Mill ноды и их входные/выходные потоки
        fresh_feed_tph = 0.0
        for node in self.graph.get_feed_nodes():
            node_kpi = self._node_kpi.get(node.id, {})
            fresh_feed_tph += node_kpi.get("feed_tph", 0.0)

        if fresh_feed_tph <= 0:
            return None

        # Находим рециклы (потоки, идущие назад в топологии)
        recycle_edges = self.graph.find_recycle_streams()
        if not recycle_edges:
            return None

        # Суммируем массу рециклов
        recycle_mass = 0.0
        for edge in recycle_edges:
            stream = self._streams.get(edge.id)
            if stream:
                recycle_mass += stream.mass_tph

        if recycle_mass <= 0:
            return None

        # CL = recycle / fresh_feed * 100
        circulating_load = (recycle_mass / fresh_feed_tph) * 100.0
        return round(circulating_load, 1)


def execute_flowsheet(nodes_data: list[dict], edges_data: list[dict]) -> dict[str, Any]:
    """
    Удобная функция для расчёта схемы.

    Args:
        nodes_data: список узлов в формате React Flow
        edges_data: список связей в формате React Flow

    Returns:
        dict с результатами расчёта
    """
    graph = FlowsheetGraph.from_flowsheet_data(nodes_data, edges_data)
    executor = FlowsheetExecutor(graph)
    result = executor.execute()
    return result.to_dict()
