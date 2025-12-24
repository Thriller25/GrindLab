"""
KPI — Ключевые показатели эффективности.

Универсальный контракт для KPI расчёта/узла/схемы.
Поддерживает сравнение, дельты, пороговые значения.

Версия контракта: 1.0
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class KPIType(str, Enum):
    """Категория KPI."""

    THROUGHPUT = "throughput"  # Производительность
    ENERGY = "energy"  # Энергопотребление
    SIZE = "size"  # Крупность (P80, P50)
    EFFICIENCY = "efficiency"  # Эффективность
    UTILIZATION = "utilization"  # Использование оборудования
    CIRCULATING_LOAD = "circulating_load"  # Циркулирующая нагрузка
    RECOVERY = "recovery"  # Извлечение
    QUALITY = "quality"  # Качество продукта
    COST = "cost"  # Стоимость
    CUSTOM = "custom"  # Пользовательский


class KPIStatus(str, Enum):
    """Статус KPI относительно целевого значения."""

    OK = "ok"  # В пределах нормы
    WARNING = "warning"  # Близко к границе
    CRITICAL = "critical"  # За пределами допуска
    UNKNOWN = "unknown"  # Нет целевого значения


class KPI(BaseModel):
    """
    Единичный KPI.

    Example:
        >>> kpi = KPI(
        ...     key="specific_energy",
        ...     name="Удельный расход энергии",
        ...     value=12.5,
        ...     unit="kWh/t",
        ...     kpi_type=KPIType.ENERGY,
        ...     target_value=11.0,
        ...     target_max=13.0,
        ... )
        >>> kpi.status
        KPIStatus.WARNING
    """

    contract_version: str = Field(default="1.0")

    # Идентификация
    key: str = Field(..., description="Уникальный ключ KPI (snake_case)")
    name: Optional[str] = Field(None, description="Человекочитаемое название")

    # Значение
    value: float = Field(..., description="Текущее значение")
    unit: str = Field(default="", description="Единица измерения")

    # Категория
    kpi_type: KPIType = Field(default=KPIType.CUSTOM)

    # Целевые значения и пороги
    target_value: Optional[float] = Field(None, description="Целевое значение")
    target_min: Optional[float] = Field(None, description="Минимально допустимое")
    target_max: Optional[float] = Field(None, description="Максимально допустимое")
    warning_threshold_percent: float = Field(
        default=10.0, description="% отклонения для статуса WARNING"
    )

    # Сравнение с базовой линией
    baseline_value: Optional[float] = Field(None, description="Базовое значение для сравнения")

    # Метаданные
    source_node_id: Optional[UUID] = Field(None, description="UUID узла-источника KPI")
    source_run_id: Optional[UUID] = Field(None, description="UUID расчёта")

    model_config = {"frozen": True}

    @computed_field
    @property
    def status(self) -> KPIStatus:
        """Вычисляет статус относительно целевых значений."""
        if self.target_min is None and self.target_max is None and self.target_value is None:
            return KPIStatus.UNKNOWN

        # Проверка жёстких границ
        if self.target_min is not None and self.value < self.target_min:
            return KPIStatus.CRITICAL
        if self.target_max is not None and self.value > self.target_max:
            return KPIStatus.CRITICAL

        # Проверка отклонения от target_value
        if self.target_value is not None:
            deviation_pct = abs(self.value - self.target_value) / abs(self.target_value) * 100
            if deviation_pct > self.warning_threshold_percent:
                return KPIStatus.WARNING

        return KPIStatus.OK

    @computed_field
    @property
    def delta_from_baseline(self) -> Optional[float]:
        """Абсолютная разница с базовой линией."""
        if self.baseline_value is not None:
            return self.value - self.baseline_value
        return None

    @computed_field
    @property
    def delta_percent(self) -> Optional[float]:
        """Процентное изменение относительно базовой линии."""
        if self.baseline_value is not None and self.baseline_value != 0:
            return ((self.value - self.baseline_value) / abs(self.baseline_value)) * 100
        return None

    def with_baseline(self, baseline: float) -> "KPI":
        """Возвращает KPI с установленным baseline."""
        return self.model_copy(update={"baseline_value": baseline})

    def to_display_dict(self) -> dict:
        """Для отображения в UI."""
        result = {
            "key": self.key,
            "name": self.name or self.key,
            "value": self.value,
            "unit": self.unit,
            "status": self.status.value,
        }
        if self.delta_percent is not None:
            result["delta_percent"] = round(self.delta_percent, 2)
        return result


class KPICollection(BaseModel):
    """
    Коллекция KPI для расчёта/узла/схемы.

    Example:
        >>> collection = KPICollection(
        ...     source_id=calc_run_id,
        ...     kpis=[
        ...         KPI(key="throughput", value=1500, unit="tph", kpi_type=KPIType.THROUGHPUT),
        ...         KPI(key="specific_energy", value=12.5, unit="kWh/t", kpi_type=KPIType.ENERGY),
        ...         KPI(key="p80_product", value=0.075, unit="mm", kpi_type=KPIType.SIZE),
        ...     ]
        ... )
        >>> collection["throughput"]
        1500.0
    """

    contract_version: str = Field(default="1.0")

    # Источник
    source_id: Optional[UUID] = Field(None, description="UUID источника (run, node, flowsheet)")
    source_type: Optional[str] = Field(None, description="Тип источника: calc_run, node, flowsheet")

    # KPI
    kpis: List[KPI] = Field(default_factory=list)

    # Метаданные
    calculated_at: Optional[str] = Field(None, description="ISO datetime расчёта")
    model_version: Optional[str] = Field(None, description="Версия модели расчёта")

    model_config = {"frozen": False}

    def __getitem__(self, key: str) -> Optional[float]:
        """Доступ к значению KPI по ключу."""
        for kpi in self.kpis:
            if kpi.key == key:
                return kpi.value
        return None

    def get(self, key: str) -> Optional[KPI]:
        """Получает полный объект KPI по ключу."""
        for kpi in self.kpis:
            if kpi.key == key:
                return kpi
        return None

    def add(self, kpi: KPI) -> "KPICollection":
        """Добавляет KPI (возвращает новую коллекцию)."""
        return self.model_copy(update={"kpis": self.kpis + [kpi]})

    def filter_by_type(self, kpi_type: KPIType) -> List[KPI]:
        """Фильтрует KPI по типу."""
        return [k for k in self.kpis if k.kpi_type == kpi_type]

    def filter_by_status(self, status: KPIStatus) -> List[KPI]:
        """Фильтрует KPI по статусу."""
        return [k for k in self.kpis if k.status == status]

    @property
    def has_critical(self) -> bool:
        """Есть ли критические KPI."""
        return any(k.status == KPIStatus.CRITICAL for k in self.kpis)

    @property
    def has_warnings(self) -> bool:
        """Есть ли предупреждения."""
        return any(k.status == KPIStatus.WARNING for k in self.kpis)

    def to_dict(self) -> Dict[str, float]:
        """Простой словарь key -> value."""
        return {k.key: k.value for k in self.kpis}

    def to_display_list(self) -> List[dict]:
        """Для отображения в UI."""
        return [k.to_display_dict() for k in self.kpis]

    def compare_with(self, baseline: "KPICollection") -> "KPICollection":
        """
        Создаёт новую коллекцию с baseline values из другой коллекции.
        """
        new_kpis = []
        baseline_dict = {k.key: k.value for k in baseline.kpis}

        for kpi in self.kpis:
            if kpi.key in baseline_dict:
                new_kpis.append(kpi.with_baseline(baseline_dict[kpi.key]))
            else:
                new_kpis.append(kpi)

        return self.model_copy(update={"kpis": new_kpis})


# === Предопределённые стандартные KPI ===


def throughput_kpi(value: float, unit: str = "tph", **kwargs) -> KPI:
    """Создаёт KPI производительности."""
    return KPI(
        key="throughput",
        name="Производительность",
        value=value,
        unit=unit,
        kpi_type=KPIType.THROUGHPUT,
        **kwargs,
    )


def specific_energy_kpi(value: float, unit: str = "kWh/t", **kwargs) -> KPI:
    """Создаёт KPI удельного расхода энергии."""
    return KPI(
        key="specific_energy",
        name="Удельный расход энергии",
        value=value,
        unit=unit,
        kpi_type=KPIType.ENERGY,
        **kwargs,
    )


def p80_kpi(value: float, unit: str = "mm", **kwargs) -> KPI:
    """Создаёт KPI P80."""
    return KPI(
        key="p80_product",
        name="P80 продукта",
        value=value,
        unit=unit,
        kpi_type=KPIType.SIZE,
        **kwargs,
    )


def circulating_load_kpi(value: float, unit: str = "%", **kwargs) -> KPI:
    """Создаёт KPI циркулирующей нагрузки."""
    return KPI(
        key="circulating_load",
        name="Циркулирующая нагрузка",
        value=value,
        unit=unit,
        kpi_type=KPIType.CIRCULATING_LOAD,
        **kwargs,
    )


def mill_utilization_kpi(value: float, unit: str = "%", **kwargs) -> KPI:
    """Создаёт KPI использования мельницы."""
    return KPI(
        key="mill_utilization",
        name="Загрузка мельницы",
        value=value,
        unit=unit,
        kpi_type=KPIType.UTILIZATION,
        **kwargs,
    )
