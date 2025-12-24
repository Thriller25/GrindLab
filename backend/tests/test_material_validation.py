"""
Тесты для Material Validation (F3.2).

Проверяют:
- MaterialValidator
- MaterialPassport
- ValidationResult
- PSD Metrics
"""

import pytest
from app.schemas.contracts import (
    PSD,
    CompletenessLevel,
    Material,
    MaterialPhase,
    MaterialQuality,
    PSDPoint,
    PSDQuality,
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
    compute_psd_metrics,
    generate_passport,
    get_material_passport,
    is_material_valid,
    validate_material,
)

# ==================== Fixtures ====================


@pytest.fixture
def valid_psd() -> PSD:
    """Валидный PSD с достаточным количеством точек."""
    return PSD(
        points=[
            PSDPoint(size_mm=0.075, cum_passing=10.0),
            PSDPoint(size_mm=0.150, cum_passing=25.0),
            PSDPoint(size_mm=0.300, cum_passing=42.0),
            PSDPoint(size_mm=0.600, cum_passing=58.0),
            PSDPoint(size_mm=1.180, cum_passing=72.0),
            PSDPoint(size_mm=2.360, cum_passing=85.0),
            PSDPoint(size_mm=4.750, cum_passing=94.0),
            PSDPoint(size_mm=9.500, cum_passing=100.0),
        ]
    )


@pytest.fixture
def minimal_psd() -> PSD:
    """Минимальный PSD (3 точки)."""
    return PSD(
        points=[
            PSDPoint(size_mm=0.5, cum_passing=30.0),
            PSDPoint(size_mm=2.0, cum_passing=65.0),
            PSDPoint(size_mm=6.0, cum_passing=100.0),
        ]
    )


@pytest.fixture
def valid_quality() -> MaterialQuality:
    """Валидные качественные характеристики."""
    return MaterialQuality(
        chemistry={"Cu": 0.45, "Fe": 12.0, "S": 2.5},
        bond_work_index_kwh_t=14.5,
        sg=2.7,
        moisture_percent=3.0,
    )


@pytest.fixture
def valid_material(valid_psd: PSD, valid_quality: MaterialQuality) -> Material:
    """Полностью валидный материал."""
    return Material(
        name="SAG Feed",
        phase=MaterialPhase.SOLID,
        solids_tph=1500.0,
        psd=valid_psd,
        quality=valid_quality,
    )


# ==================== Validation Result Tests ====================


class TestValidationResult:
    """Тесты для ValidationResult."""

    def test_empty_result_is_valid(self):
        """Пустой результат валиден."""
        result = ValidationResult.from_issues([])
        assert result.is_valid is True
        assert result.errors_count == 0
        assert result.warnings_count == 0

    def test_result_with_warning_is_valid(self):
        """Результат с предупреждением валиден."""
        from app.schemas.contracts.material_validation import ValidationIssue

        issues = [
            ValidationIssue(
                code="TEST_WARNING",
                message="Test warning",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.RANGE,
            )
        ]
        result = ValidationResult.from_issues(issues)

        assert result.is_valid is True
        assert result.warnings_count == 1
        assert result.errors_count == 0

    def test_result_with_error_is_invalid(self):
        """Результат с ошибкой невалиден."""
        from app.schemas.contracts.material_validation import ValidationIssue

        issues = [
            ValidationIssue(
                code="TEST_ERROR",
                message="Test error",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.CONSISTENCY,
            )
        ]
        result = ValidationResult.from_issues(issues)

        assert result.is_valid is False
        assert result.errors_count == 1

    def test_to_dict(self):
        """Сериализация в словарь."""
        result = ValidationResult.from_issues([])
        d = result.to_dict()

        assert "is_valid" in d
        assert "errors_count" in d
        assert "warnings_count" in d
        assert "issues" in d


# ==================== Material Validator Tests ====================


class TestMaterialValidator:
    """Тесты для MaterialValidator."""

    def test_valid_material_passes(self, valid_material: Material):
        """Валидный материал проходит проверку."""
        result = validate_material(valid_material)

        assert result.is_valid is True
        assert result.errors_count == 0

    def test_slurry_without_water_fails(self, valid_psd: PSD):
        """Пульпа без воды — ошибка."""
        material = Material(
            name="Bad Slurry",
            phase=MaterialPhase.SLURRY,
            solids_tph=1000.0,
            water_tph=0.0,  # Нет воды!
            psd=valid_psd,
        )

        result = validate_material(material)

        assert result.is_valid is False
        assert any(i.code == "SLURRY_NO_WATER" for i in result.issues)

    def test_water_with_solids_fails(self):
        """Вода с твёрдым — ошибка."""
        material = Material(
            name="Bad Water",
            phase=MaterialPhase.WATER,
            solids_tph=100.0,  # Не должно быть!
        )

        result = validate_material(material)

        assert result.is_valid is False
        assert any(i.code == "WATER_HAS_SOLIDS" for i in result.issues)

    def test_psd_too_few_points(self):
        """PSD с недостаточным количеством точек."""
        psd = PSD(
            points=[
                PSDPoint(size_mm=1.0, cum_passing=50.0),
                PSDPoint(size_mm=5.0, cum_passing=100.0),
            ]
        )
        material = Material(
            phase=MaterialPhase.SOLID,
            solids_tph=100.0,
            psd=psd,
        )

        result = validate_material(material)

        assert result.is_valid is False
        assert any(i.code == "PSD_TOO_FEW_POINTS" for i in result.issues)

    def test_psd_not_monotonic(self):
        """Немонотонный PSD проверяется в PSD constructor."""
        # PSD валидация монотонности происходит при создании PSD
        # Если PSD невалиден, он не создастся - это правильное поведение
        # Тестируем что создание немонотонного PSD вызывает ошибку
        with pytest.raises(Exception):  # ValidationError from Pydantic
            PSD(
                points=[
                    PSDPoint(size_mm=1.0, cum_passing=50.0),
                    PSDPoint(size_mm=2.0, cum_passing=40.0),  # Уменьшается!
                    PSDPoint(size_mm=3.0, cum_passing=60.0),
                    PSDPoint(size_mm=4.0, cum_passing=80.0),
                    PSDPoint(size_mm=5.0, cum_passing=100.0),
                ]
            )

    def test_components_fraction_sum(self):
        """Сумма долей компонентов != 1."""
        from app.schemas.contracts import MaterialComponent

        material = Material(
            phase=MaterialPhase.SOLID,
            solids_tph=1000.0,
            components=[
                MaterialComponent(component_id="ore1", mass_fraction=0.4),
                MaterialComponent(component_id="ore2", mass_fraction=0.4),
                # Сумма = 0.8, не 1.0
            ],
        )

        result = validate_material(material)

        assert result.is_valid is False
        assert any(i.code == "COMPONENTS_FRACTION_SUM" for i in result.issues)

    def test_bond_wi_out_of_range(self):
        """Bond WI вне диапазона — предупреждение."""
        quality = MaterialQuality(bond_work_index_kwh_t=50.0)  # Слишком высокий
        material = Material(
            phase=MaterialPhase.SOLID,
            solids_tph=100.0,
            quality=quality,
        )

        result = validate_material(material)

        assert any(i.code == "BOND_WI_OUT_OF_RANGE" for i in result.warnings)

    def test_convenience_function_is_material_valid(self, valid_material: Material):
        """is_material_valid возвращает bool."""
        assert is_material_valid(valid_material) is True


# ==================== PSD Metrics Tests ====================


class TestPSDMetrics:
    """Тесты для PSD Metrics."""

    def test_compute_metrics(self, valid_psd: PSD):
        """Вычисление метрик."""
        metrics = compute_psd_metrics(valid_psd)

        assert metrics.points_count == 8
        assert metrics.quality in [PSDQuality.EXCELLENT, PSDQuality.GOOD]
        assert metrics.is_monotonic is True
        assert metrics.p80 is not None
        assert metrics.size_min_mm == 0.075
        assert metrics.size_max_mm == 9.5

    def test_empty_psd_invalid(self):
        """Пустой PSD вызывает ошибку при создании."""
        # PSD требует минимум 3 точки
        with pytest.raises(Exception):
            PSD(points=[])

    def test_minimal_psd_poor_quality(self, minimal_psd: PSD):
        """Минимальный PSD — POOR качество."""
        metrics = compute_psd_metrics(minimal_psd)

        assert metrics.quality in [PSDQuality.POOR, PSDQuality.ACCEPTABLE]
        assert metrics.points_count == 3

    def test_metrics_has_fines(self, valid_psd: PSD):
        """has_fines определяется правильно."""
        metrics = compute_psd_metrics(valid_psd)
        assert metrics.has_fines is True  # 0.075 < 0.1

    def test_metrics_has_coarse(self):
        """has_coarse определяется правильно."""
        psd = PSD(
            points=[
                PSDPoint(size_mm=1.0, cum_passing=10.0),
                PSDPoint(size_mm=5.0, cum_passing=40.0),
                PSDPoint(size_mm=15.0, cum_passing=70.0),
                PSDPoint(size_mm=25.0, cum_passing=90.0),
                PSDPoint(size_mm=50.0, cum_passing=100.0),
            ]
        )
        metrics = compute_psd_metrics(psd)
        assert metrics.has_coarse is True  # 50 > 10

    def test_to_dict(self, valid_psd: PSD):
        """Сериализация метрик."""
        metrics = compute_psd_metrics(valid_psd)
        d = metrics.to_dict()

        assert "points_count" in d
        assert "quality" in d
        assert "size_range_mm" in d
        assert "p80" in d


# ==================== Material Passport Tests ====================


class TestMaterialPassport:
    """Тесты для MaterialPassport."""

    def test_generate_passport_full(self, valid_material: Material):
        """Генерация полного паспорта."""
        passport = generate_passport(valid_material)

        assert passport.name == "SAG Feed"
        assert passport.phase == MaterialPhase.SOLID
        assert passport.solids_tph == 1500.0
        assert passport.has_psd is True
        assert passport.has_quality is True
        assert passport.has_chemistry is True
        assert passport.has_work_index is True

    def test_passport_completeness_full(self, valid_material: Material):
        """Полный материал имеет FULL completeness."""
        passport = generate_passport(valid_material)

        assert passport.completeness_level == CompletenessLevel.FULL
        assert passport.completeness_score >= 90

    def test_passport_completeness_minimal(self):
        """Минимальный материал имеет MINIMAL completeness."""
        material = Material(phase=MaterialPhase.SOLID, solids_tph=100.0)
        passport = generate_passport(material)

        assert passport.completeness_level == CompletenessLevel.MINIMAL
        assert passport.completeness_score < 50

    def test_passport_readiness_for_sizing(self, valid_material: Material):
        """Проверка готовности для расчёта размера."""
        passport = generate_passport(valid_material)

        assert passport.ready_for_sizing is True
        assert passport.ready_for_simulation is True
        assert passport.ready_for_energy_calc is True

    def test_passport_not_ready_without_psd(self):
        """Без PSD не готов для sizing."""
        quality = MaterialQuality(bond_work_index_kwh_t=14.0)
        material = Material(
            phase=MaterialPhase.SOLID,
            solids_tph=100.0,
            quality=quality,
        )
        passport = generate_passport(material)

        assert passport.ready_for_sizing is False
        assert passport.ready_for_simulation is False

    def test_passport_recommendations(self):
        """Паспорт содержит рекомендации."""
        material = Material(phase=MaterialPhase.SOLID, solids_tph=100.0)
        passport = generate_passport(material)

        assert len(passport.recommendations) > 0
        assert any("PSD" in r for r in passport.recommendations)

    def test_passport_to_dict(self, valid_material: Material):
        """Сериализация паспорта."""
        d = get_material_passport(valid_material)

        assert "name" in d
        assert "phase" in d
        assert "completeness" in d
        assert "mass_flow" in d
        assert "psd" in d
        assert "quality" in d
        assert "validation" in d
        assert "readiness" in d
        assert "recommendations" in d

    def test_passport_psd_metrics_included(self, valid_material: Material):
        """PSD metrics включены в паспорт."""
        d = get_material_passport(valid_material)

        assert d["psd"]["available"] is True
        assert d["psd"]["metrics"] is not None
        assert "p80" in d["psd"]["metrics"]

    def test_passport_chemistry_elements(self, valid_material: Material):
        """Список химических элементов."""
        passport = generate_passport(valid_material)

        assert "Cu" in passport.chemistry_elements
        assert "Fe" in passport.chemistry_elements
        assert "S" in passport.chemistry_elements


# ==================== Integration Tests ====================


class TestIntegration:
    """Интеграционные тесты."""

    def test_slurry_with_solids_percent(self, valid_psd: PSD):
        """Пульпа с заданием через % твёрдого."""
        material = Material(
            name="Ball Mill Discharge",
            phase=MaterialPhase.SLURRY,
            solids_tph=1000.0,
            solids_percent=65.0,
            psd=valid_psd,
        )

        result = validate_material(material)
        passport = generate_passport(material)

        assert result.is_valid is True
        assert passport.water_tph > 0
        assert passport.water_solids_ratio is not None

    def test_multi_component_material(self, valid_psd: PSD):
        """Многокомпонентный материал."""
        from app.schemas.contracts import MaterialComponent

        material = Material(
            name="Blended Feed",
            phase=MaterialPhase.SOLID,
            solids_tph=2000.0,
            psd=valid_psd,
            components=[
                MaterialComponent(component_id="ore1", name="Oxide Ore", mass_fraction=0.6),
                MaterialComponent(component_id="ore2", name="Sulfide Ore", mass_fraction=0.4),
            ],
        )

        result = validate_material(material)
        passport = generate_passport(material)

        assert result.is_valid is True
        assert passport.solids_tph == 2000.0

    def test_validation_and_passport_consistency(self, valid_material: Material):
        """Валидация и паспорт согласованы."""
        result = validate_material(valid_material)
        passport = generate_passport(valid_material)

        assert result.is_valid == passport.validation.is_valid
        assert result.errors_count == passport.validation.errors_count
