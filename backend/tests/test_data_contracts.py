"""
Тесты для Data Contracts (F0.2).

Проверяют:
- PSD: создание, интерполяция, квантили
- Material: создание, слияние, вычисления
- Stream: топология, материал
- KPI: статусы, сравнение
- Blast: прослеживаемость, merge
"""

from uuid import uuid4

import pytest
from app.schemas.contracts import (
    KPI,
    PSD,
    Blast,
    BlastBlock,
    BlastStatus,
    KPICollection,
    KPIStatus,
    KPIType,
    Material,
    MaterialPhase,
    MaterialQuality,
    PSDPoint,
    Stream,
    StreamType,
    p80_kpi,
    specific_energy_kpi,
    throughput_kpi,
)

# ==================== PSD Tests ====================


class TestPSD:
    """Тесты для PSD контракта."""

    @pytest.fixture
    def sample_psd(self) -> PSD:
        """Типичный PSD для тестов."""
        return PSD(
            points=[
                PSDPoint(size_mm=0.075, cum_passing=15.0),
                PSDPoint(size_mm=0.150, cum_passing=35.0),
                PSDPoint(size_mm=0.300, cum_passing=55.0),
                PSDPoint(size_mm=0.600, cum_passing=75.0),
                PSDPoint(size_mm=1.180, cum_passing=90.0),
                PSDPoint(size_mm=2.360, cum_passing=98.0),
            ]
        )

    def test_psd_creation(self, sample_psd: PSD):
        """PSD создаётся корректно."""
        assert len(sample_psd.points) == 6
        assert sample_psd.contract_version == "1.0"

    def test_psd_from_cumulative(self):
        """Создание PSD из двух списков."""
        psd = PSD.from_cumulative(sizes_mm=[0.1, 0.2, 0.5, 1.0], cum_passing=[20, 40, 70, 95])
        assert len(psd.points) == 4
        assert psd.points[0].size_mm == 0.1
        assert psd.points[0].cum_passing == 20

    def test_psd_sorts_points(self):
        """PSD сортирует точки по размеру."""
        psd = PSD(
            points=[
                PSDPoint(size_mm=1.0, cum_passing=80),
                PSDPoint(size_mm=0.1, cum_passing=20),
                PSDPoint(size_mm=0.5, cum_passing=50),
            ]
        )
        assert psd.points[0].size_mm == 0.1
        assert psd.points[1].size_mm == 0.5
        assert psd.points[2].size_mm == 1.0

    def test_psd_validates_monotonicity(self):
        """PSD проверяет монотонность cum_passing."""
        with pytest.raises(ValueError, match="монотонно"):
            PSD(
                points=[
                    PSDPoint(size_mm=0.1, cum_passing=50),
                    PSDPoint(size_mm=0.5, cum_passing=30),  # Уменьшается!
                ]
            )

    def test_psd_requires_min_points(self):
        """PSD требует минимум 2 точки."""
        with pytest.raises(ValueError):
            PSD(points=[PSDPoint(size_mm=0.1, cum_passing=50)])

    def test_psd_get_pxx(self, sample_psd: PSD):
        """Интерполяция P-значений."""
        p80 = sample_psd.get_pxx(80)
        assert p80 is not None
        # P80 должен быть между 0.600 и 1.180 (75% и 90%)
        assert 0.6 < p80 < 1.18

    def test_psd_p80_property(self, sample_psd: PSD):
        """Свойство p80 работает."""
        assert sample_psd.p80 is not None
        assert sample_psd.p80 == sample_psd.get_pxx(80)

    def test_psd_p50_property(self, sample_psd: PSD):
        """Свойство p50 работает."""
        assert sample_psd.p50 is not None
        assert sample_psd.p50 == sample_psd.get_pxx(50)

    def test_psd_compute_quantiles(self, sample_psd: PSD):
        """Вычисление всех квантилей."""
        q = sample_psd.compute_quantiles()
        assert q.p10 is not None
        assert q.p50 is not None
        assert q.p80 is not None
        assert q.p90 is not None
        # P10 < P50 < P80 < P90
        assert q.p10 < q.p50 < q.p80 < q.p90

    def test_psd_with_computed_quantiles(self, sample_psd: PSD):
        """with_computed_quantiles заполняет поле quantiles."""
        psd = sample_psd.with_computed_quantiles()
        assert psd.quantiles is not None
        assert psd.quantiles.p80 is not None

    def test_psd_to_dict_for_chart(self, sample_psd: PSD):
        """Экспорт для графика."""
        data = sample_psd.to_dict_for_chart()
        assert "sizes_mm" in data
        assert "cum_passing" in data
        assert "p80" in data
        assert len(data["sizes_mm"]) == 6


# ==================== Material Tests ====================


class TestMaterial:
    """Тесты для Material контракта."""

    @pytest.fixture
    def sample_quality(self) -> MaterialQuality:
        """Типичное качество."""
        return MaterialQuality(
            chemistry={"Cu": 0.5, "Fe": 15.0, "S": 2.0},
            bond_work_index_kwh_t=14.5,
            sg=2.7,
            moisture_percent=3.0,
        )

    @pytest.fixture
    def sample_material(self, sample_quality: MaterialQuality) -> Material:
        """Типичный материал."""
        return Material(
            name="SAG Feed",
            phase=MaterialPhase.SOLID,
            solids_tph=1500.0,
            quality=sample_quality,
        )

    def test_material_creation(self, sample_material: Material):
        """Material создаётся корректно."""
        assert sample_material.solids_tph == 1500.0
        assert sample_material.total_tph == 1500.0  # Нет воды
        assert sample_material.contract_version == "1.0"

    def test_material_with_water(self):
        """Material с водой."""
        mat = Material(
            phase=MaterialPhase.SLURRY,
            solids_tph=1000.0,
            water_tph=500.0,
        )
        assert mat.total_tph == 1500.0
        assert mat.water_solids_ratio == 0.5

    def test_material_computes_solids_percent(self):
        """Вычисление % твёрдого из water_tph."""
        mat = Material(
            phase=MaterialPhase.SLURRY,
            solids_tph=1000.0,
            water_tph=500.0,
        )
        # solids_percent = 1000 / 1500 * 100 ≈ 66.67%
        assert mat.solids_percent is not None
        assert 66 < mat.solids_percent < 67

    def test_material_computes_water_from_percent(self):
        """Вычисление воды из % твёрдого."""
        mat = Material(
            phase=MaterialPhase.SLURRY,
            solids_tph=1000.0,
            solids_percent=50.0,  # 50% твёрдого = равные части
        )
        assert mat.water_tph == 1000.0  # 1000 т/ч воды при 50%

    def test_material_density(self, sample_material: Material):
        """Плотность из quality."""
        assert sample_material.density_t_m3 == 2.7

    def test_material_with_psd(self, sample_material: Material):
        """with_psd возвращает копию с PSD."""
        psd = PSD.from_cumulative([0.1, 0.5, 1.0], [20, 60, 95])
        new_mat = sample_material.with_psd(psd)

        assert new_mat.psd is not None
        assert sample_material.psd is None  # Оригинал не изменён
        assert new_mat.p80_mm is not None

    def test_material_blend(self, sample_material: Material):
        """Смешивание материалов."""
        other = Material(
            name="Recycle",
            phase=MaterialPhase.SOLID,
            solids_tph=500.0,
        )

        blended = sample_material.blend_with(other, other_fraction=0.25)

        # 1500 * 0.75 + 500 * 0.25 = 1125 + 125 = 1250
        assert blended.solids_tph == 1250.0
        assert len(blended.components) == 2


class TestMaterialQuality:
    """Тесты для MaterialQuality."""

    def test_quality_creation(self):
        """Качество создаётся."""
        q = MaterialQuality(
            chemistry={"Cu": 0.5},
            bond_work_index_kwh_t=14.0,
            sg=2.7,
        )
        assert q.chemistry["Cu"] == 0.5
        assert q.bond_work_index_kwh_t == 14.0

    def test_quality_extra_fields(self):
        """Дополнительные поля в extra."""
        q = MaterialQuality(extra={"custom_index": 42.0})
        assert q.extra["custom_index"] == 42.0


# ==================== Stream Tests ====================


class TestStream:
    """Тесты для Stream контракта."""

    def test_stream_creation(self):
        """Stream создаётся."""
        source_id = uuid4()
        target_id = uuid4()

        stream = Stream(
            name="SAG Discharge",
            stream_type=StreamType.SLURRY,
            source_node_id=source_id,
            target_node_id=target_id,
        )

        assert stream.source_node_id == source_id
        assert stream.target_node_id == target_id
        assert stream.stream_type == StreamType.SLURRY
        assert stream.is_calculated is False

    def test_stream_with_material(self):
        """Stream с материалом."""
        stream = Stream(
            source_node_id=uuid4(),
            target_node_id=uuid4(),
        )

        material = Material(solids_tph=1000.0, water_tph=500.0)
        new_stream = stream.with_material(material)

        assert new_stream.material is not None
        assert new_stream.solids_tph == 1000.0
        assert new_stream.total_tph == 1500.0
        assert new_stream.is_calculated is True

    def test_stream_summary(self):
        """summary() для логов."""
        stream = Stream(
            name="Product",
            stream_type=StreamType.PRODUCT,
            source_node_id=uuid4(),
            target_node_id=uuid4(),
            material=Material(
                solids_tph=500.0, psd=PSD.from_cumulative([0.05, 0.1, 0.2], [40, 70, 95])
            ),
        )

        summary = stream.summary()
        assert "Product" in summary
        assert "500.0 tph" in summary
        assert "P80=" in summary


# ==================== KPI Tests ====================


class TestKPI:
    """Тесты для KPI контракта."""

    def test_kpi_creation(self):
        """KPI создаётся."""
        kpi = KPI(
            key="throughput",
            name="Производительность",
            value=1500.0,
            unit="tph",
            kpi_type=KPIType.THROUGHPUT,
        )

        assert kpi.key == "throughput"
        assert kpi.value == 1500.0

    def test_kpi_status_ok(self):
        """Статус OK когда в пределах."""
        kpi = KPI(
            key="energy",
            value=12.0,
            target_value=12.0,
            target_min=10.0,
            target_max=14.0,
        )
        assert kpi.status == KPIStatus.OK

    def test_kpi_status_warning(self):
        """Статус WARNING при отклонении."""
        kpi = KPI(
            key="energy",
            value=14.0,  # 14% отклонение от 12.0
            target_value=12.0,
            warning_threshold_percent=10.0,
        )
        assert kpi.status == KPIStatus.WARNING

    def test_kpi_status_critical(self):
        """Статус CRITICAL при выходе за пределы."""
        kpi = KPI(
            key="energy",
            value=16.0,  # Больше max
            target_max=15.0,
        )
        assert kpi.status == KPIStatus.CRITICAL

    def test_kpi_status_unknown(self):
        """Статус UNKNOWN без целевых значений."""
        kpi = KPI(key="custom", value=42.0)
        assert kpi.status == KPIStatus.UNKNOWN

    def test_kpi_delta_from_baseline(self):
        """Дельта от базовой линии."""
        kpi = KPI(
            key="throughput",
            value=1600.0,
            baseline_value=1500.0,
        )
        assert kpi.delta_from_baseline == 100.0
        # (1600-1500)/1500*100 ≈ 6.67%
        assert 6 < kpi.delta_percent < 7

    def test_kpi_with_baseline(self):
        """with_baseline добавляет baseline."""
        kpi = KPI(key="throughput", value=1600.0)
        kpi_with_bl = kpi.with_baseline(1500.0)

        assert kpi_with_bl.baseline_value == 1500.0
        assert kpi_with_bl.delta_from_baseline == 100.0


class TestKPICollection:
    """Тесты для KPICollection."""

    @pytest.fixture
    def sample_collection(self) -> KPICollection:
        """Типичная коллекция KPI."""
        return KPICollection(
            kpis=[
                throughput_kpi(1500.0),
                specific_energy_kpi(12.5),
                p80_kpi(0.075),
            ]
        )

    def test_collection_creation(self, sample_collection: KPICollection):
        """Коллекция создаётся."""
        assert len(sample_collection.kpis) == 3

    def test_collection_getitem(self, sample_collection: KPICollection):
        """Доступ по ключу."""
        assert sample_collection["throughput"] == 1500.0
        assert sample_collection["nonexistent"] is None

    def test_collection_get(self, sample_collection: KPICollection):
        """get() возвращает полный KPI."""
        kpi = sample_collection.get("specific_energy")
        assert kpi is not None
        assert kpi.value == 12.5

    def test_collection_add(self, sample_collection: KPICollection):
        """add() добавляет KPI."""
        new_kpi = KPI(key="recovery", value=92.0, unit="%")
        new_collection = sample_collection.add(new_kpi)

        assert len(new_collection.kpis) == 4
        assert new_collection["recovery"] == 92.0

    def test_collection_filter_by_type(self, sample_collection: KPICollection):
        """Фильтр по типу."""
        energy_kpis = sample_collection.filter_by_type(KPIType.ENERGY)
        assert len(energy_kpis) == 1
        assert energy_kpis[0].key == "specific_energy"

    def test_collection_to_dict(self, sample_collection: KPICollection):
        """to_dict() создаёт простой словарь."""
        d = sample_collection.to_dict()
        assert d["throughput"] == 1500.0
        assert d["specific_energy"] == 12.5

    def test_collection_compare_with(self):
        """compare_with() добавляет baseline."""
        current = KPICollection(kpis=[throughput_kpi(1600.0)])
        baseline = KPICollection(kpis=[throughput_kpi(1500.0)])

        compared = current.compare_with(baseline)

        kpi = compared.get("throughput")
        assert kpi.baseline_value == 1500.0
        assert kpi.delta_from_baseline == 100.0


# ==================== Blast Tests ====================


class TestBlast:
    """Тесты для Blast контракта."""

    @pytest.fixture
    def sample_blast(self) -> Blast:
        """Типичный взрыв."""
        return Blast(
            blast_id="BL-2024-001",
            name="Zone A, Jan 15",
            total_tonnage_t=50000.0,
            psd=PSD.from_cumulative(
                sizes_mm=[50, 100, 200, 300, 500], cum_passing=[5, 20, 50, 80, 98]
            ),
            quality=MaterialQuality(
                chemistry={"Cu": 0.55, "Fe": 14.0},
                bond_work_index_kwh_t=14.2,
                sg=2.75,
            ),
            status=BlastStatus.BLASTED,
        )

    def test_blast_creation(self, sample_blast: Blast):
        """Blast создаётся."""
        assert sample_blast.blast_id == "BL-2024-001"
        assert sample_blast.total_tonnage_t == 50000.0
        assert sample_blast.status == BlastStatus.BLASTED

    def test_blast_p80(self, sample_blast: Blast):
        """P80 взрыва."""
        assert sample_blast.p80_mm is not None
        # P80 около 300mm (80% при 300mm)
        assert 290 < sample_blast.p80_mm < 310

    def test_blast_consume(self, sample_blast: Blast):
        """consume() уменьшает остаток."""
        consumed = sample_blast.consume(10000.0)

        assert consumed.remaining_tonnage_t == 40000.0
        assert consumed.status == BlastStatus.PROCESSING

    def test_blast_consume_complete(self, sample_blast: Blast):
        """consume() всего тоннажа → COMPLETED."""
        consumed = sample_blast.consume(50000.0)

        assert consumed.remaining_tonnage_t == 0.0
        assert consumed.status == BlastStatus.COMPLETED

    def test_blast_merge(self, sample_blast: Blast):
        """merge_with() объединяет взрывы."""
        other = Blast(
            blast_id="BL-2024-002",
            total_tonnage_t=30000.0,
            quality=MaterialQuality(
                chemistry={"Cu": 0.40, "Fe": 16.0},
            ),
        )

        merged = sample_blast.merge_with(other)

        assert merged.total_tonnage_t == 80000.0
        assert "MERGE" in merged.blast_id
        # Среднее содержание Cu: (0.55*50000 + 0.40*30000) / 80000 ≈ 0.49
        assert 0.48 < merged.quality.chemistry["Cu"] < 0.50

    def test_blast_to_material(self, sample_blast: Blast):
        """to_material() конвертирует в Material."""
        material = sample_blast.to_material(rate_tph=1500.0)

        assert material.solids_tph == 1500.0
        assert material.psd is not None
        assert material.quality is not None
        assert material.source_blast_id == "BL-2024-001"

    def test_blast_summary(self, sample_blast: Blast):
        """summary() для логов."""
        summary = sample_blast.summary()

        assert "BL-2024-001" in summary
        assert "50000t" in summary
        assert "P80=" in summary
        assert "Cu=" in summary

    def test_blast_is_composite(self, sample_blast: Blast):
        """is_composite для составных взрывов."""
        assert not sample_blast.is_composite

        composite = Blast(
            blast_id="BL-COMP",
            total_tonnage_t=100000.0,
            blocks=[
                BlastBlock(block_id="B1", tonnage_t=60000.0),
                BlastBlock(block_id="B2", tonnage_t=40000.0),
            ],
        )
        assert composite.is_composite
