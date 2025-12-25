"""
Tests for Execution Engine — F5.1

Тесты расчётного ядра технологических схем.
"""

from app.core.engine import FlowsheetExecutor, FlowsheetGraph, Stream, StreamPSD
from app.core.engine.unit_models import (
    CrusherUnit,
    FeedUnit,
    HydrocycloneUnit,
    MillUnit,
    ProductUnit,
    ScreenUnit,
    create_unit_model,
)


class TestStreamPSD:
    """Тесты для StreamPSD."""

    def test_from_f80_creates_valid_psd(self):
        """PSD из F80 должен иметь правильный P80."""
        psd = StreamPSD.from_f80(100.0)
        assert psd.p80 is not None
        assert 80 < psd.p80 < 130  # Близко к 100 (±30%)

    def test_pxx_interpolation(self):
        """Интерполяция P-значений должна работать."""
        psd = StreamPSD(
            points=[
                (10.0, 20.0),
                (50.0, 50.0),
                (100.0, 80.0),
                (200.0, 95.0),
            ]
        )
        # Точки интерполируются
        assert psd.p50 is not None
        assert 40 < psd.p50 < 60  # Близко к 50
        assert psd.p80 is not None
        assert 90 < psd.p80 < 110  # Близко к 100
        assert psd.p20 is not None

    def test_scale_by_factor(self):
        """Масштабирование PSD уменьшает размеры."""
        psd = StreamPSD.from_f80(100.0)
        scaled = psd.scale_by_factor(2.0)
        assert scaled.p80 is not None
        assert scaled.p80 < psd.p80

    def test_blend_with(self):
        """Смешение двух PSD."""
        psd1 = StreamPSD.from_f80(100.0)
        psd2 = StreamPSD.from_f80(50.0)
        blended = psd1.blend_with(psd2, 0.5)
        assert blended.p80 is not None
        # P80 должен быть между 50 и 100
        assert 45 < blended.p80 < 105


class TestStream:
    """Тесты для Stream."""

    def test_water_calculation(self):
        """Расчёт воды в потоке."""
        stream = Stream(id="test", mass_tph=100.0, solids_pct=75.0)
        # При 75% твёрдого: 100 т/ч твёрдого, 33.3 т/ч воды
        assert abs(stream.water_tph - 33.33) < 1.0

    def test_dry_stream_no_water(self):
        """Сухой поток не имеет воды."""
        stream = Stream(id="test", mass_tph=100.0, solids_pct=100.0)
        assert stream.water_tph == 0.0

    def test_clone(self):
        """Клонирование потока."""
        psd = StreamPSD.from_f80(100.0)
        stream = Stream(id="original", mass_tph=500.0, solids_pct=80.0, psd=psd)
        clone = stream.clone("clone")
        assert clone.id == "clone"
        assert clone.mass_tph == stream.mass_tph
        assert clone.psd is not None


class TestUnitModels:
    """Тесты для моделей оборудования."""

    def test_feed_unit_generates_stream(self):
        """Feed узел генерирует поток."""
        unit = FeedUnit("feed-1", "feed", {"tph": 1000, "f80_mm": 150, "solids_pct": 100})
        result = unit.calculate({})
        assert "out" in result.outputs
        assert result.outputs["out"].mass_tph == 1000
        assert result.kpi["feed_tph"] == 1000

    def test_product_unit_receives_stream(self):
        """Product узел принимает поток."""
        unit = ProductUnit("prod-1", "product", {})
        feed_stream = Stream(
            id="feed",
            mass_tph=500.0,
            psd=StreamPSD.from_f80(0.075),
        )
        result = unit.calculate({"in": feed_stream})
        assert result.kpi["product_tph"] == 500.0

    def test_crusher_reduces_size(self):
        """Дробилка уменьшает размер."""
        unit = CrusherUnit(
            "crusher-1",
            "jaw_crusher",
            {"css": 100, "reduction_ratio": 5, "capacity_tph": 1000},
        )
        feed = Stream(id="feed", mass_tph=800, psd=StreamPSD.from_f80(500))
        result = unit.calculate({"feed": feed})

        assert "product" in result.outputs
        product = result.outputs["product"]
        assert product.mass_tph == 800  # Масса сохраняется
        assert product.p80_mm < 500  # Размер уменьшился

    def test_mill_grinds_material(self):
        """Мельница измельчает материал."""
        unit = MillUnit(
            "mill-1",
            "ball_mill",
            {"power_kw": 5000, "diameter_m": 5},
        )
        feed = Stream(id="feed", mass_tph=200, psd=StreamPSD.from_f80(10))
        result = unit.calculate({"feed": feed})

        assert "product" in result.outputs
        product = result.outputs["product"]
        assert product.p80_mm < 10  # Измельчение произошло
        assert result.kpi["power_kw"] == 5000

    def test_hydrocyclone_splits_stream(self):
        """Гидроциклон разделяет поток."""
        unit = HydrocycloneUnit(
            "cyc-1",
            "hydrocyclone",
            {"d50_um": 75, "sharpness": 2.5},
        )
        feed = Stream(id="feed", mass_tph=1000, solids_pct=70, psd=StreamPSD.from_f80(0.2))
        result = unit.calculate({"feed": feed})

        assert "overflow" in result.outputs
        assert "underflow" in result.outputs

        of = result.outputs["overflow"]
        uf = result.outputs["underflow"]

        # Массовый баланс (с допуском на численные ошибки)
        assert abs(of.mass_tph + uf.mass_tph - 1000) < 50.0

    def test_screen_splits_stream(self):
        """Грохот разделяет поток."""
        unit = ScreenUnit(
            "screen-1",
            "vib_screen",
            {"aperture_mm": 25, "efficiency": 90},
        )
        feed = Stream(id="feed", mass_tph=500, psd=StreamPSD.from_f80(50))
        result = unit.calculate({"feed": feed})

        assert "oversize" in result.outputs
        assert "undersize" in result.outputs

        over = result.outputs["oversize"]
        under = result.outputs["undersize"]

        # Массовый баланс
        assert abs(over.mass_tph + under.mass_tph - 500) < 1.0

    def test_create_unit_model_factory(self):
        """Фабрика создаёт правильные модели."""
        crusher = create_unit_model("c1", "jaw_crusher", {})
        assert isinstance(crusher, CrusherUnit)

        mill = create_unit_model("m1", "sag_mill", {})
        assert isinstance(mill, MillUnit)


class TestFlowsheetGraph:
    """Тесты для графа схемы."""

    def test_from_flowsheet_data(self):
        """Создание графа из данных React Flow."""
        nodes = [
            {"id": "feed-1", "data": {"type": "feed", "parameters": {"tph": 100}}},
            {"id": "prod-1", "data": {"type": "product", "parameters": {}}},
        ]
        edges = [
            {"id": "e1", "source": "feed-1", "target": "prod-1"},
        ]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)

        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert "feed-1" in graph.nodes

    def test_topological_sort_simple(self):
        """Топологическая сортировка простой схемы."""
        nodes = [
            {"id": "a", "data": {"type": "feed"}},
            {"id": "b", "data": {"type": "jaw_crusher"}},
            {"id": "c", "data": {"type": "product"}},
        ]
        edges = [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "b", "target": "c"},
        ]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        sorted_nodes, back_edges = graph.topological_sort()

        assert len(sorted_nodes) == 3
        assert len(back_edges) == 0
        assert sorted_nodes.index("a") < sorted_nodes.index("b")
        assert sorted_nodes.index("b") < sorted_nodes.index("c")

    def test_detects_recycle(self):
        """Обнаружение рецикла в схеме."""
        # Feed -> Crusher -> Cyclone
        #                     ↓ underflow -> Crusher (рецикл)
        nodes = [
            {"id": "feed", "data": {"type": "feed"}},
            {"id": "crusher", "data": {"type": "cone_crusher"}},
            {"id": "cyclone", "data": {"type": "hydrocyclone"}},
            {"id": "product", "data": {"type": "product"}},
        ]
        edges = [
            {"id": "e1", "source": "feed", "target": "crusher"},
            {"id": "e2", "source": "crusher", "target": "cyclone"},
            {"id": "e3", "source": "cyclone", "target": "product", "sourceHandle": "overflow"},
            {
                "id": "e4",
                "source": "cyclone",
                "target": "crusher",
                "sourceHandle": "underflow",
            },  # Рецикл!
        ]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)

        assert graph.has_cycles()
        back_edges = graph.find_recycle_streams()
        assert len(back_edges) >= 1

    def test_validation_empty_graph(self):
        """Валидация: пустой граф."""
        nodes = []
        edges = []
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        errors = graph.validate()

        # Должна быть ошибка — нет узлов
        assert len(errors) > 0
        assert any("no nodes" in e.lower() for e in errors)


class TestFlowsheetExecutor:
    """Тесты для исполнителя расчёта."""

    def test_simple_feed_to_product(self):
        """Простая схема: питание -> продукт."""
        nodes = [
            {"id": "feed-1", "data": {"type": "feed", "parameters": {"tph": 1000, "f80_mm": 150}}},
            {"id": "prod-1", "data": {"type": "product", "parameters": {}}},
        ]
        edges = [
            {
                "id": "e1",
                "source": "feed-1",
                "target": "prod-1",
                "sourceHandle": "out",
                "targetHandle": "in",
            },
        ]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()

        assert result.success
        assert result.global_kpi["total_feed_tph"] == 1000
        assert result.global_kpi["total_product_tph"] == 1000
        assert abs(result.global_kpi["mass_balance_error_pct"]) < 0.1

    def test_crusher_circuit(self):
        """Схема с дробилкой."""
        nodes = [
            {"id": "feed", "data": {"type": "feed", "parameters": {"tph": 500, "f80_mm": 300}}},
            {
                "id": "crusher",
                "data": {
                    "type": "jaw_crusher",
                    "parameters": {"css": 100, "reduction_ratio": 5, "capacity_tph": 600},
                },
            },
            {"id": "product", "data": {"type": "product", "parameters": {}}},
        ]
        edges = [
            {
                "id": "e1",
                "source": "feed",
                "target": "crusher",
                "sourceHandle": "out",
                "targetHandle": "feed",
            },
            {
                "id": "e2",
                "source": "crusher",
                "target": "product",
                "sourceHandle": "product",
                "targetHandle": "in",
            },
        ]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()

        assert result.success
        assert result.global_kpi["total_product_tph"] == 500
        assert result.global_kpi["product_p80_mm"] < 300  # Измельчился
        assert result.global_kpi["total_power_kw"] > 0

    def test_grinding_circuit_with_cyclone(self):
        """Схема измельчения с гидроциклоном (без рецикла)."""
        nodes = [
            {
                "id": "feed",
                "data": {
                    "type": "feed",
                    "parameters": {"tph": 200, "f80_mm": 10, "solids_pct": 75},
                },
            },
            {
                "id": "mill",
                "data": {"type": "ball_mill", "parameters": {"power_kw": 3000, "diameter_m": 4}},
            },
            {"id": "cyclone", "data": {"type": "hydrocyclone", "parameters": {"d50_um": 75}}},
            {"id": "product", "data": {"type": "product", "parameters": {}}},
        ]
        edges = [
            {
                "id": "e1",
                "source": "feed",
                "target": "mill",
                "sourceHandle": "out",
                "targetHandle": "feed",
            },
            {
                "id": "e2",
                "source": "mill",
                "target": "cyclone",
                "sourceHandle": "product",
                "targetHandle": "feed",
            },
            {
                "id": "e3",
                "source": "cyclone",
                "target": "product",
                "sourceHandle": "overflow",
                "targetHandle": "in",
            },
        ]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()

        assert result.success
        assert len(result.streams) >= 3
        assert "mill" in result.node_kpi

    def test_execution_time_tracked(self):
        """Время выполнения отслеживается."""
        nodes = [
            {"id": "f", "data": {"type": "feed", "parameters": {"tph": 100}}},
            {"id": "p", "data": {"type": "product", "parameters": {}}},
        ]
        edges = [{"id": "e1", "source": "f", "target": "p"}]
        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()

        assert result.execution_time_ms > 0


class TestSimulationAPI:
    """Тесты для API эндпоинтов."""

    def test_run_simulation_endpoint(self):
        """POST /api/simulation/run возвращает результат."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        payload = {
            "nodes": [
                {"id": "f1", "data": {"type": "feed", "parameters": {"tph": 100, "f80_mm": 50}}},
                {"id": "p1", "data": {"type": "product", "parameters": {}}},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "f1",
                    "target": "p1",
                    "sourceHandle": "out",
                    "targetHandle": "in",
                },
            ],
        }

        response = client.post("/api/simulation/run", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["global_kpi"]["total_feed_tph"] == 100

    def test_validate_endpoint(self):
        """POST /api/simulation/validate проверяет схему."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        payload = {
            "nodes": [
                {"id": "f1", "data": {"type": "feed"}},
                {"id": "c1", "data": {"type": "jaw_crusher"}},
                {"id": "p1", "data": {"type": "product"}},
            ],
            "edges": [
                {"id": "e1", "source": "f1", "target": "c1"},
                {"id": "e2", "source": "c1", "target": "p1"},
            ],
        }

        response = client.post("/api/simulation/validate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is True
        assert data["node_count"] == 3
        assert data["edge_count"] == 2

    def test_run_simulation_empty_nodes_error(self):
        """Пустой список узлов возвращает ошибку."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.post("/api/simulation/run", json={"nodes": [], "edges": []})
        assert response.status_code == 400


class TestKPIComputation:
    """Тесты для F5.2 — KPI computation."""

    def test_psd_passing_at_size(self):
        """passing_at_size() интерполирует % прохода."""
        psd = StreamPSD(
            points=[
                (0.01, 5.0),
                (0.063, 25.0),  # 240 mesh
                (0.1, 40.0),
                (0.5, 75.0),
                (1.0, 90.0),
            ]
        )
        # Точное значение в точке
        assert abs(psd.passing_at_size(0.063) - 25.0) < 0.1
        # Интерполяция между точками
        passing_at_0_2 = psd.passing_at_size(0.2)
        assert 40.0 < passing_at_0_2 < 75.0

    def test_psd_get_passing_240_mesh(self):
        """get_passing_240_mesh() возвращает % при 63 мкм."""
        psd = StreamPSD.from_f80(1.0)  # F80 = 1мм
        passing_240 = psd.get_passing_240_mesh()
        # Должно быть низкое значение (крупный материал)
        assert passing_240 < 50.0
        assert passing_240 >= 0.0

    def test_psd_p98_property(self):
        """P98 свойство работает."""
        psd = StreamPSD(
            points=[
                (10.0, 20.0),
                (50.0, 50.0),
                (100.0, 80.0),
                (200.0, 98.0),
                (300.0, 100.0),
            ]
        )
        assert psd.p98 is not None
        assert 195 < psd.p98 < 210  # Близко к 200

    def test_product_unit_extended_kpi(self):
        """ProductUnit выдаёт расширенные KPI."""
        psd = StreamPSD.from_f80(1.0)
        stream = Stream(
            id="test",
            mass_tph=100.0,
            solids_pct=70.0,
            psd=psd,
        )
        unit = ProductUnit(node_id="p1", node_type="product", params={})
        result = unit.calculate({"in": stream})

        assert result.error is None
        kpi = result.kpi
        assert "product_tph" in kpi
        assert "p80_mm" in kpi
        assert "p50_mm" in kpi
        assert "p98_mm" in kpi
        assert "passing_240_mesh_pct" in kpi

    def test_feed_unit_extended_kpi(self):
        """FeedUnit выдаёт расширенные KPI."""
        unit = FeedUnit(node_id="f1", node_type="feed", params={"tph": 100.0, "f80_mm": 50.0})
        result = unit.calculate({})

        assert result.error is None
        kpi = result.kpi
        assert "feed_tph" in kpi
        assert "f80_mm" in kpi
        assert "f50_mm" in kpi

    def test_global_kpi_extended(self):
        """Глобальные KPI включают P50, P98, passing_240."""
        nodes = [
            {"id": "f1", "data": {"type": "feed", "params": {"tph": 100, "f80_mm": 50}}},
            {"id": "p1", "data": {"type": "product"}},
        ]
        edges = [
            {
                "id": "e1",
                "source": "f1",
                "target": "p1",
                "sourceHandle": "out",
                "targetHandle": "in",
            },
        ]

        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()

        assert result.success
        kpi = result.global_kpi

        assert "total_feed_tph" in kpi
        assert "feed_f80_mm" in kpi
        assert "product_p80_mm" in kpi
        assert "product_p50_mm" in kpi
        assert "product_p98_mm" in kpi
        assert "product_passing_240_mesh_pct" in kpi

    def test_circulating_load_with_recycle(self):
        """Circulating Load вычисляется для схемы с рециклом."""
        # Схема: Feed -> Mill -> Cyclone -> Product
        #                    ^    |
        #                    +----+ underflow (recycle)
        nodes = [
            {"id": "f1", "data": {"type": "feed", "params": {"tph": 100, "f80_mm": 5}}},
            {
                "id": "m1",
                "data": {
                    "type": "ball_mill",
                    "params": {"power_kw": 500, "reduction_ratio": 5},
                },
            },
            {
                "id": "cy1",
                "data": {
                    "type": "hydrocyclone",
                    "params": {"d50c_mm": 0.3, "split_to_underflow": 0.7},
                },
            },
            {"id": "p1", "data": {"type": "product"}},
        ]
        edges = [
            {
                "id": "e1",
                "source": "f1",
                "target": "m1",
                "sourceHandle": "out",
                "targetHandle": "feed",
            },
            {
                "id": "e2",
                "source": "m1",
                "target": "cy1",
                "sourceHandle": "out",
                "targetHandle": "feed",
            },
            {
                "id": "e3",
                "source": "cy1",
                "target": "p1",
                "sourceHandle": "overflow",
                "targetHandle": "in",
            },
            {
                "id": "e4",
                "source": "cy1",
                "target": "m1",
                "sourceHandle": "underflow",
                "targetHandle": "feed",
            },  # Recycle!
        ]

        graph = FlowsheetGraph.from_flowsheet_data(nodes, edges)
        executor = FlowsheetExecutor(graph)
        result = executor.execute()

        assert result.success
        assert result.converged
        assert result.iterations > 1  # Итеративное решение

        kpi = result.global_kpi
        # Circulating Load должен быть рассчитан
        assert "circulating_load_pct" in kpi
        # При split_to_underflow=0.7, CL зависит от конвергенции
        # Проверяем что значение разумное (> 0)
        assert kpi["circulating_load_pct"] >= 100  # Значимая циркуляция

    def test_psd_to_dict_extended(self):
        """StreamPSD.to_dict() включает все метрики."""
        psd = StreamPSD.from_f80(10.0)
        d = psd.to_dict()

        assert "points" in d
        assert "p80_mm" in d
        assert "p50_mm" in d
        assert "p98_mm" in d
        assert "p20_mm" in d
        assert "passing_240_mesh_pct" in d
