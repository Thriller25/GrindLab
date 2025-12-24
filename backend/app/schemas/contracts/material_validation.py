"""
Material Validation — Модуль валидации материалов (F3.2).

Включает:
- MaterialValidator — класс для валидации Material
- MaterialPassport — полный "паспорт" материала с метриками качества
- ValidationRule — правила валидации
- ValidationResult — результаты валидации

Версия контракта: 1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .material import Material, MaterialPhase, MaterialQuality
from .psd import PSD

# ============================================================
# Validation Enums
# ============================================================


class ValidationSeverity(str, Enum):
    """Уровень критичности ошибки валидации."""

    ERROR = "error"  # Критическая ошибка, данные невалидны
    WARNING = "warning"  # Предупреждение, данные можно использовать с осторожностью
    INFO = "info"  # Информационное сообщение


class ValidationCategory(str, Enum):
    """Категория валидации."""

    COMPLETENESS = "completeness"  # Полнота данных
    CONSISTENCY = "consistency"  # Согласованность данных
    RANGE = "range"  # Диапазоны значений
    PSD = "psd"  # Валидация гранулометрии
    QUALITY = "quality"  # Качественные параметры
    PHYSICS = "physics"  # Физическая корректность


class CompletenessLevel(str, Enum):
    """Уровень полноты данных материала."""

    MINIMAL = "minimal"  # Только обязательные поля
    BASIC = "basic"  # Основные характеристики
    STANDARD = "standard"  # Стандартный набор для расчётов
    FULL = "full"  # Полный набор данных


class PSDQuality(str, Enum):
    """Качество PSD."""

    EXCELLENT = "excellent"  # Отличное: много точек, полный диапазон
    GOOD = "good"  # Хорошее: достаточно точек
    ACCEPTABLE = "acceptable"  # Приемлемое: минимум для расчётов
    POOR = "poor"  # Плохое: мало точек, экстраполяция
    INVALID = "invalid"  # Невалидное: нельзя использовать


# ============================================================
# Validation Result
# ============================================================


@dataclass
class ValidationIssue:
    """Отдельная проблема валидации."""

    code: str  # Уникальный код ошибки, например "PSD_TOO_FEW_POINTS"
    message: str  # Человекочитаемое описание
    severity: ValidationSeverity
    category: ValidationCategory
    field: Optional[str] = None  # Путь к полю: "psd.points[0].cum_passing"
    expected: Optional[str] = None  # Ожидаемое значение
    actual: Optional[str] = None  # Фактическое значение
    suggestion: Optional[str] = None  # Рекомендация по исправлению

    def to_dict(self) -> dict:
        """Сериализация для API."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Результат валидации материала."""

    is_valid: bool  # True если нет ошибок (ERROR)
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0
    info_count: int = 0

    @classmethod
    def from_issues(cls, issues: List[ValidationIssue]) -> "ValidationResult":
        """Создать результат из списка проблем."""
        errors = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        infos = sum(1 for i in issues if i.severity == ValidationSeverity.INFO)

        return cls(
            is_valid=errors == 0,
            issues=issues,
            errors_count=errors,
            warnings_count=warnings,
            info_count=infos,
        )

    def add_issue(self, issue: ValidationIssue) -> None:
        """Добавить проблему."""
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.errors_count += 1
            self.is_valid = False
        elif issue.severity == ValidationSeverity.WARNING:
            self.warnings_count += 1
        else:
            self.info_count += 1

    @property
    def errors(self) -> List[ValidationIssue]:
        """Только ошибки."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Только предупреждения."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def to_dict(self) -> dict:
        """Сериализация для API."""
        return {
            "is_valid": self.is_valid,
            "errors_count": self.errors_count,
            "warnings_count": self.warnings_count,
            "info_count": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
        }


# ============================================================
# PSD Metrics
# ============================================================


@dataclass
class PSDMetrics:
    """Метрики качества PSD."""

    points_count: int
    quality: PSDQuality

    # Диапазон размеров
    size_min_mm: float
    size_max_mm: float
    size_range_decades: float  # log10(max/min)

    # Квантили
    p10: Optional[float] = None
    p50: Optional[float] = None
    p80: Optional[float] = None
    p90: Optional[float] = None

    # Характеристики распределения
    span: Optional[float] = None  # (P80 - P20) / P50
    uniformity_coefficient: Optional[float] = None  # P60 / P10

    # Покрытие диапазона
    has_fines: bool = False  # Есть точки < 0.1 мм
    has_coarse: bool = False  # Есть точки > 10 мм

    # Монотонность
    is_monotonic: bool = True

    # Ошибки
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Сериализация для API."""
        return {
            "points_count": self.points_count,
            "quality": self.quality.value,
            "size_range_mm": [self.size_min_mm, self.size_max_mm],
            "size_range_decades": round(self.size_range_decades, 2),
            "p10": self.p10,
            "p50": self.p50,
            "p80": self.p80,
            "p90": self.p90,
            "span": self.span,
            "uniformity_coefficient": self.uniformity_coefficient,
            "has_fines": self.has_fines,
            "has_coarse": self.has_coarse,
            "is_monotonic": self.is_monotonic,
            "issues": self.issues,
        }


def compute_psd_metrics(psd: PSD) -> PSDMetrics:
    """Вычислить метрики качества PSD."""
    import math

    if not psd.points or len(psd.points) == 0:
        return PSDMetrics(
            points_count=0,
            quality=PSDQuality.INVALID,
            size_min_mm=0,
            size_max_mm=0,
            size_range_decades=0,
            issues=["PSD не содержит точек"],
        )

    points = sorted(psd.points, key=lambda p: p.size_mm)
    n = len(points)
    sizes = [p.size_mm for p in points]
    passings = [p.cum_passing for p in points]

    # Базовые метрики
    size_min = sizes[0]
    size_max = sizes[-1]
    decades = math.log10(size_max / size_min) if size_min > 0 else 0

    issues = []

    # Проверка монотонности
    is_monotonic = all(passings[i] <= passings[i + 1] for i in range(n - 1))
    if not is_monotonic:
        issues.append("cum_passing не монотонно возрастает")

    # Проверка диапазона cum_passing
    if passings[-1] < 95:
        issues.append(f"Максимальный cum_passing={passings[-1]:.1f}%, ожидается близко к 100%")
    if passings[0] > 30:
        issues.append(f"Минимальный cum_passing={passings[0]:.1f}%, нет данных в мелком классе")

    # Квантили
    try:
        p10 = psd.get_pxx(10)
        p50 = psd.get_pxx(50)
        p80 = psd.get_pxx(80)
        p90 = psd.get_pxx(90)
    except (ValueError, IndexError):
        p10 = p50 = p80 = p90 = None
        issues.append("Не удалось вычислить квантили")

    # Span и UC
    span = None
    uc = None
    if p10 and p50 and p80:
        try:
            p20 = psd.get_pxx(20)
            span = (p80 - p20) / p50 if p50 > 0 else None
        except Exception:
            pass
    if p10:
        try:
            p60 = psd.get_pxx(60)
            uc = p60 / p10 if p10 > 0 else None
        except Exception:
            pass

    # Определение качества
    quality = _assess_psd_quality(n, decades, is_monotonic, passings, issues)

    return PSDMetrics(
        points_count=n,
        quality=quality,
        size_min_mm=size_min,
        size_max_mm=size_max,
        size_range_decades=decades,
        p10=p10,
        p50=p50,
        p80=p80,
        p90=p90,
        span=span,
        uniformity_coefficient=uc,
        has_fines=size_min < 0.1,
        has_coarse=size_max > 10,
        is_monotonic=is_monotonic,
        issues=issues,
    )


def _assess_psd_quality(
    n: int, decades: float, is_monotonic: bool, passings: List[float], issues: List[str]
) -> PSDQuality:
    """Оценить качество PSD."""
    if not is_monotonic:
        return PSDQuality.INVALID

    if n < 3:
        return PSDQuality.INVALID

    # Оценка по количеству точек и диапазону
    if n >= 10 and decades >= 2.0 and passings[-1] >= 98:
        return PSDQuality.EXCELLENT
    if n >= 6 and decades >= 1.5 and passings[-1] >= 95:
        return PSDQuality.GOOD
    if n >= 4 and decades >= 1.0:
        return PSDQuality.ACCEPTABLE
    if n >= 3:
        return PSDQuality.POOR

    return PSDQuality.INVALID


# ============================================================
# Material Passport
# ============================================================


@dataclass
class MaterialPassport:
    """
    Паспорт материала — полная характеристика с метриками качества.

    Используется для:
    - Отображения сводки о материале в UI
    - Проверки готовности к расчётам
    - Экспорта в отчёты
    """

    # Идентификация
    name: Optional[str]
    phase: MaterialPhase

    # Полнота данных
    completeness_level: CompletenessLevel
    completeness_score: float  # 0-100%

    # Массовые расходы
    solids_tph: float
    water_tph: float
    total_tph: float
    water_solids_ratio: Optional[float]
    solids_percent: Optional[float]

    # Гранулометрия
    has_psd: bool
    psd_metrics: Optional[PSDMetrics]

    # Качество
    has_quality: bool
    has_chemistry: bool
    has_work_index: bool
    has_sg: bool
    chemistry_elements: List[str]

    # Валидация
    validation: ValidationResult

    # Готовность к расчётам
    ready_for_sizing: bool  # Готов для расчёта размера мельницы
    ready_for_simulation: bool  # Готов для симуляции
    ready_for_energy_calc: bool  # Готов для энергетических расчётов

    # Рекомендации
    recommendations: List[str]

    def to_dict(self) -> dict:
        """Сериализация для API."""
        return {
            "name": self.name,
            "phase": self.phase.value,
            "completeness": {
                "level": self.completeness_level.value,
                "score": round(self.completeness_score, 1),
            },
            "mass_flow": {
                "solids_tph": self.solids_tph,
                "water_tph": self.water_tph,
                "total_tph": self.total_tph,
                "water_solids_ratio": self.water_solids_ratio,
                "solids_percent": self.solids_percent,
            },
            "psd": {
                "available": self.has_psd,
                "metrics": self.psd_metrics.to_dict() if self.psd_metrics else None,
            },
            "quality": {
                "available": self.has_quality,
                "has_chemistry": self.has_chemistry,
                "has_work_index": self.has_work_index,
                "has_sg": self.has_sg,
                "chemistry_elements": self.chemistry_elements,
            },
            "validation": self.validation.to_dict(),
            "readiness": {
                "for_sizing": self.ready_for_sizing,
                "for_simulation": self.ready_for_simulation,
                "for_energy_calc": self.ready_for_energy_calc,
            },
            "recommendations": self.recommendations,
        }


# ============================================================
# Material Validator
# ============================================================


class MaterialValidator:
    """
    Валидатор материалов.

    Выполняет комплексную проверку Material на:
    - Полноту данных
    - Корректность диапазонов
    - Согласованность параметров
    - Качество PSD
    - Физическую реалистичность
    """

    # Диапазоны значений для проверки
    VALID_RANGES = {
        "solids_tph": (0, 50000),  # т/ч
        "water_solids_ratio": (0, 10),  # Ж:Т
        "solids_percent": (10, 100),  # %
        "sg": (1.0, 8.0),  # т/м³
        "bond_wi": (5, 30),  # кВт·ч/т
        "moisture": (0, 15),  # %
        "chemistry_ppm_max": 1_000_000,  # ppm = 100%
    }

    def validate(self, material: Material) -> ValidationResult:
        """
        Выполнить полную валидацию материала.

        Returns:
            ValidationResult с найденными проблемами
        """
        issues: List[ValidationIssue] = []

        # 1. Проверка обязательных полей
        issues.extend(self._check_required_fields(material))

        # 2. Проверка диапазонов
        issues.extend(self._check_ranges(material))

        # 3. Проверка согласованности
        issues.extend(self._check_consistency(material))

        # 4. Проверка PSD
        if material.psd:
            issues.extend(self._check_psd(material.psd))

        # 5. Проверка качества
        if material.quality:
            issues.extend(self._check_quality(material.quality))

        return ValidationResult.from_issues(issues)

    def _check_required_fields(self, material: Material) -> List[ValidationIssue]:
        """Проверка обязательных полей."""
        issues = []

        if material.solids_tph == 0 and material.phase != MaterialPhase.WATER:
            issues.append(
                ValidationIssue(
                    code="ZERO_SOLIDS",
                    message="Расход твёрдого равен нулю",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.COMPLETENESS,
                    field="solids_tph",
                    suggestion="Укажите расход твёрдого для материала",
                )
            )

        return issues

    def _check_ranges(self, material: Material) -> List[ValidationIssue]:
        """Проверка диапазонов значений."""
        issues = []

        # Расход
        if material.solids_tph > self.VALID_RANGES["solids_tph"][1]:
            issues.append(
                ValidationIssue(
                    code="SOLIDS_TPH_TOO_HIGH",
                    message=(
                        f"Расход твёрдого ({material.solids_tph} т/ч) "
                        "превышает реалистичный максимум"
                    ),
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.RANGE,
                    field="solids_tph",
                    expected=f"< {self.VALID_RANGES['solids_tph'][1]} т/ч",
                    actual=f"{material.solids_tph} т/ч",
                )
            )

        # Ж:Т
        if material.water_solids_ratio:
            ws_min, ws_max = self.VALID_RANGES["water_solids_ratio"]
            if not (ws_min <= material.water_solids_ratio <= ws_max):
                issues.append(
                    ValidationIssue(
                        code="WATER_SOLIDS_RATIO_INVALID",
                        message=(
                            f"Соотношение Ж:Т = {material.water_solids_ratio:.2f} "
                            "вне допустимого диапазона"
                        ),
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.RANGE,
                        field="water_solids_ratio",
                        expected=f"{ws_min} - {ws_max}",
                        actual=f"{material.water_solids_ratio:.2f}",
                    )
                )

        return issues

    def _check_consistency(self, material: Material) -> List[ValidationIssue]:
        """Проверка согласованности параметров."""
        issues = []

        # Пульпа должна иметь воду
        if material.phase == MaterialPhase.SLURRY and material.water_tph == 0:
            issues.append(
                ValidationIssue(
                    code="SLURRY_NO_WATER",
                    message="Пульпа (phase=slurry) не содержит воды",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONSISTENCY,
                    field="water_tph",
                    suggestion="Укажите water_tph или solids_percent",
                )
            )

        # Вода не должна иметь твёрдого
        if material.phase == MaterialPhase.WATER and material.solids_tph > 0:
            issues.append(
                ValidationIssue(
                    code="WATER_HAS_SOLIDS",
                    message="Вода (phase=water) содержит твёрдое",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONSISTENCY,
                    field="solids_tph",
                )
            )

        # Компоненты должны суммироваться в 1
        if material.components:
            total_fraction = sum(c.mass_fraction for c in material.components)
            if abs(total_fraction - 1.0) > 0.01:
                issues.append(
                    ValidationIssue(
                        code="COMPONENTS_FRACTION_SUM",
                        message=f"Сумма долей компонентов = {total_fraction:.2f}, должна быть 1.0",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.CONSISTENCY,
                        field="components",
                        expected="1.0",
                        actual=f"{total_fraction:.3f}",
                    )
                )

        return issues

    def _check_psd(self, psd: PSD) -> List[ValidationIssue]:
        """Проверка PSD."""
        issues = []

        if not psd.points:
            issues.append(
                ValidationIssue(
                    code="PSD_EMPTY",
                    message="PSD не содержит точек",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.PSD,
                    field="psd.points",
                )
            )
            return issues

        n = len(psd.points)

        if n < 3:
            issues.append(
                ValidationIssue(
                    code="PSD_TOO_FEW_POINTS",
                    message=f"PSD содержит только {n} точек, минимум 3",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.PSD,
                    field="psd.points",
                    expected=">= 3",
                    actual=str(n),
                )
            )

        elif n < 5:
            issues.append(
                ValidationIssue(
                    code="PSD_FEW_POINTS",
                    message=f"PSD содержит {n} точек, рекомендуется минимум 5",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.PSD,
                    field="psd.points",
                    suggestion="Добавьте больше точек для повышения точности интерполяции",
                )
            )

        # Проверка монотонности
        sorted_points = sorted(psd.points, key=lambda p: p.size_mm)
        for i in range(len(sorted_points) - 1):
            if sorted_points[i].cum_passing > sorted_points[i + 1].cum_passing:
                issues.append(
                    ValidationIssue(
                        code="PSD_NOT_MONOTONIC",
                        message="cum_passing должен монотонно возрастать с размером",
                        severity=ValidationSeverity.ERROR,
                        category=ValidationCategory.PSD,
                        field=f"psd.points[{i}].cum_passing",
                        expected=f"<= {sorted_points[i+1].cum_passing}",
                        actual=str(sorted_points[i].cum_passing),
                    )
                )
                break

        # Проверка диапазона cum_passing
        passings = [p.cum_passing for p in sorted_points]
        if passings[-1] < 90:
            issues.append(
                ValidationIssue(
                    code="PSD_INCOMPLETE_TOP",
                    message=(
                        f"Максимальный cum_passing = {passings[-1]:.1f}%, "
                        "нет данных в крупном классе"
                    ),
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.PSD,
                    suggestion="Добавьте точки с размером, где cum_passing близок к 100%",
                )
            )

        return issues

    def _check_quality(self, quality: MaterialQuality) -> List[ValidationIssue]:
        """Проверка качественных параметров."""
        issues = []

        # Bond WI
        if quality.bond_work_index_kwh_t is not None:
            wi_min, wi_max = self.VALID_RANGES["bond_wi"]
            if not (wi_min <= quality.bond_work_index_kwh_t <= wi_max):
                issues.append(
                    ValidationIssue(
                        code="BOND_WI_OUT_OF_RANGE",
                        message=(
                            f"Bond Work Index = {quality.bond_work_index_kwh_t} кВт·ч/т "
                            "вне типичного диапазона"
                        ),
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.QUALITY,
                        field="quality.bond_work_index_kwh_t",
                        expected=f"{wi_min} - {wi_max} кВт·ч/т",
                        actual=f"{quality.bond_work_index_kwh_t}",
                    )
                )

        # SG
        if quality.sg is not None:
            sg_min, sg_max = self.VALID_RANGES["sg"]
            if not (sg_min <= quality.sg <= sg_max):
                issues.append(
                    ValidationIssue(
                        code="SG_OUT_OF_RANGE",
                        message=f"Удельный вес SG = {quality.sg} вне типичного диапазона",
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.QUALITY,
                        field="quality.sg",
                        expected=f"{sg_min} - {sg_max}",
                        actual=f"{quality.sg}",
                    )
                )

        # Химия — сумма не должна превышать 100%
        if quality.chemistry:
            total = sum(quality.chemistry.values())
            if total > 105:  # Небольшой допуск для погрешностей
                issues.append(
                    ValidationIssue(
                        code="CHEMISTRY_SUM_EXCEEDS",
                        message=f"Сумма химических элементов = {total:.1f}%, превышает 100%",
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.QUALITY,
                        field="quality.chemistry",
                    )
                )

        return issues


# ============================================================
# Passport Generator
# ============================================================


def generate_passport(material: Material) -> MaterialPassport:
    """
    Сгенерировать полный паспорт материала.

    Args:
        material: Материал для анализа

    Returns:
        MaterialPassport с полной характеристикой
    """
    validator = MaterialValidator()
    validation = validator.validate(material)

    # Метрики PSD
    psd_metrics = None
    has_psd = material.psd is not None and bool(material.psd.points)
    if has_psd:
        psd_metrics = compute_psd_metrics(material.psd)

    # Качество
    has_quality = material.quality is not None
    has_chemistry = bool(material.quality and material.quality.chemistry)
    has_work_index = bool(material.quality and material.quality.bond_work_index_kwh_t is not None)
    has_sg = bool(material.quality and material.quality.sg is not None)
    chemistry_elements = list(material.quality.chemistry.keys()) if has_chemistry else []

    # Полнота
    completeness_level, completeness_score = _assess_completeness(
        material, has_psd, has_quality, has_chemistry, has_work_index, has_sg
    )

    # Готовность к расчётам
    ready_for_sizing = (
        has_psd
        and has_work_index
        and material.solids_tph > 0
        and (psd_metrics is None or psd_metrics.quality != PSDQuality.INVALID)
    )

    ready_for_simulation = (
        has_psd
        and material.solids_tph > 0
        and (psd_metrics is None or psd_metrics.quality != PSDQuality.INVALID)
    )

    ready_for_energy_calc = has_work_index and material.solids_tph > 0

    # Рекомендации
    recommendations = _generate_recommendations(
        material,
        validation,
        has_psd,
        has_work_index,
        psd_metrics,
    )

    return MaterialPassport(
        name=material.name,
        phase=material.phase,
        completeness_level=completeness_level,
        completeness_score=completeness_score,
        solids_tph=material.solids_tph,
        water_tph=material.water_tph,
        total_tph=material.total_tph,
        water_solids_ratio=material.water_solids_ratio,
        solids_percent=material.solids_percent,
        has_psd=has_psd,
        psd_metrics=psd_metrics,
        has_quality=has_quality,
        has_chemistry=has_chemistry,
        has_work_index=has_work_index,
        has_sg=has_sg,
        chemistry_elements=chemistry_elements,
        validation=validation,
        ready_for_sizing=ready_for_sizing,
        ready_for_simulation=ready_for_simulation,
        ready_for_energy_calc=ready_for_energy_calc,
        recommendations=recommendations,
    )


def _assess_completeness(
    material: Material,
    has_psd: bool,
    has_quality: bool,
    has_chemistry: bool,
    has_work_index: bool,
    has_sg: bool,
) -> tuple[CompletenessLevel, float]:
    """Оценить уровень полноты данных."""
    score = 0
    # max_score = 100 — подразумевается, score нормализован к 100

    # Обязательные (40 баллов)
    if material.solids_tph >= 0:
        score += 20
    if material.phase:
        score += 10
    if material.name:
        score += 10

    # PSD (30 баллов)
    if has_psd:
        score += 20
        if material.psd and len(material.psd.points) >= 8:
            score += 10

    # Качество (30 баллов)
    if has_quality:
        score += 5
    if has_chemistry:
        score += 10
    if has_work_index:
        score += 10
    if has_sg:
        score += 5

    # Уровень
    if score >= 90:
        level = CompletenessLevel.FULL
    elif score >= 70:
        level = CompletenessLevel.STANDARD
    elif score >= 50:
        level = CompletenessLevel.BASIC
    else:
        level = CompletenessLevel.MINIMAL

    return level, score


def _generate_recommendations(
    material: Material,
    validation: ValidationResult,
    has_psd: bool,
    has_work_index: bool,
    psd_metrics: Optional[PSDMetrics],
) -> List[str]:
    """Сгенерировать рекомендации по улучшению данных."""
    recs = []

    if not has_psd:
        recs.append("Добавьте гранулометрический состав (PSD) для расчёта размера мельницы")

    if not has_work_index:
        recs.append("Укажите Bond Work Index для энергетических расчётов")

    if psd_metrics and psd_metrics.quality == PSDQuality.POOR:
        recs.append("PSD низкого качества: добавьте больше точек для точности расчётов")

    if psd_metrics and not psd_metrics.has_fines:
        recs.append("PSD не содержит мелких классов (< 0.1 мм) — возможна экстраполяция")

    if validation.warnings_count > 0:
        recs.append(
            f"Исправьте {validation.warnings_count} предупреждение(й) для повышения качества данных"
        )

    if material.phase == MaterialPhase.SLURRY and not material.quality:
        recs.append("Для пульпы рекомендуется указать плотность (SG) для расчёта объёмов")

    return recs


# ============================================================
# Convenience functions
# ============================================================


def validate_material(material: Material) -> ValidationResult:
    """
    Быстрая валидация материала.

    Args:
        material: Материал для валидации

    Returns:
        ValidationResult с найденными проблемами
    """
    return MaterialValidator().validate(material)


def is_material_valid(material: Material) -> bool:
    """
    Проверить валидность материала.

    Args:
        material: Материал для проверки

    Returns:
        True если материал валиден (нет ошибок)
    """
    return validate_material(material).is_valid


def get_material_passport(material: Material) -> dict:
    """
    Получить паспорт материала в виде словаря.

    Args:
        material: Материал

    Returns:
        dict с полной характеристикой материала
    """
    return generate_passport(material).to_dict()
