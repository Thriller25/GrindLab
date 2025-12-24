"""
PSD (Particle Size Distribution) — Гранулометрический состав.

Центральный контракт для представления распределения частиц по размерам.
Используется в потоках, материалах, результатах расчёта.

Версия контракта: 1.0
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, computed_field, model_validator


class PSDInterpolation(str, Enum):
    """Метод интерполяции для расчёта квантилей."""

    LINEAR = "linear"
    LOG_LINEAR = "log_linear"  # log по размеру, linear по проценту
    SPLINE = "spline"


class PSDPoint(BaseModel):
    """
    Одна точка распределения.

    Attributes:
        size_mm: Размер частиц в мм (верхняя граница фракции)
        cum_passing: Кумулятивный % прохода (0-100)
        retained: Опционально — % задержки на данном сите
    """

    size_mm: Annotated[float, Field(gt=0, description="Размер сита, мм")]
    cum_passing: Annotated[float, Field(ge=0, le=100, description="Кумулятивный % прохода")]
    retained: Optional[Annotated[float, Field(ge=0, le=100)]] = None

    model_config = {"frozen": True}


class PSDQuantiles(BaseModel):
    """
    Стандартные квантили (P-значения) для PSD.

    P80 = размер, через который проходит 80% материала.
    """

    p10: Optional[float] = Field(None, description="P10 в мм")
    p20: Optional[float] = Field(None, description="P20 в мм")
    p50: Optional[float] = Field(None, description="P50 (медиана) в мм")
    p80: Optional[float] = Field(None, description="P80 в мм — основной показатель крупности")
    p90: Optional[float] = Field(None, description="P90 в мм")
    p95: Optional[float] = Field(None, description="P95 в мм")
    p100: Optional[float] = Field(None, description="P100 (макс размер) в мм")


class PSDStats(BaseModel):
    """
    Статистические характеристики распределения.
    """

    d50: Optional[float] = Field(None, description="Медианный размер, мм")
    d_mean: Optional[float] = Field(None, description="Средний размер, мм")
    span: Optional[float] = Field(None, description="(P90-P10)/P50 — мера разброса")
    uniformity_coefficient: Optional[float] = Field(
        None, description="Cu = D60/D10 — коэффициент однородности"
    )


class PSD(BaseModel):
    """
    Полное представление гранулометрического состава.

    Example:
        >>> psd = PSD(
        ...     points=[
        ...         PSDPoint(size_mm=0.075, cum_passing=15.0),
        ...         PSDPoint(size_mm=0.150, cum_passing=35.0),
        ...         PSDPoint(size_mm=0.300, cum_passing=55.0),
        ...         PSDPoint(size_mm=0.600, cum_passing=75.0),
        ...         PSDPoint(size_mm=1.180, cum_passing=90.0),
        ...         PSDPoint(size_mm=2.360, cum_passing=98.0),
        ...     ]
        ... )
        >>> psd.get_pxx(80)  # P80
        0.789...
    """

    contract_version: str = Field(default="1.0", description="Версия контракта PSD")

    points: List[PSDPoint] = Field(
        ..., min_length=2, description="Точки распределения, отсортированные по size_mm"
    )

    interpolation: PSDInterpolation = Field(
        default=PSDInterpolation.LOG_LINEAR, description="Метод интерполяции"
    )

    # Кэшированные квантили (опционально, для сериализации)
    quantiles: Optional[PSDQuantiles] = None
    stats: Optional[PSDStats] = None

    # Метаданные
    source: Optional[str] = Field(None, description="Источник данных: lab, model, import")
    measured_at: Optional[str] = Field(None, description="ISO datetime замера")

    model_config = {"frozen": False}

    @model_validator(mode="after")
    def validate_and_sort(self) -> "PSD":
        """Сортируем точки и проверяем монотонность."""
        if len(self.points) < 2:
            raise ValueError("PSD должен содержать минимум 2 точки")

        # Сортировка по размеру
        sorted_points = sorted(self.points, key=lambda p: p.size_mm)

        # Проверка монотонности cum_passing
        for i in range(1, len(sorted_points)):
            if sorted_points[i].cum_passing < sorted_points[i - 1].cum_passing:
                raise ValueError(
                    f"cum_passing должен быть монотонно возрастающим: "
                    f"{sorted_points[i-1].size_mm}mm ({sorted_points[i-1].cum_passing}%) > "
                    f"{sorted_points[i].size_mm}mm ({sorted_points[i].cum_passing}%)"
                )

        # Мутируем объект (frozen=False)
        object.__setattr__(self, "points", sorted_points)
        return self

    def get_pxx(self, percent: float) -> Optional[float]:
        """
        Интерполирует размер для заданного процента прохода.

        Args:
            percent: Процент прохода (0-100), например 80 для P80

        Returns:
            Размер в мм или None если вне диапазона
        """
        if not 0 <= percent <= 100:
            raise ValueError(f"percent должен быть 0-100, получено {percent}")

        points = self.points

        # Граничные случаи
        if percent <= points[0].cum_passing:
            return points[0].size_mm
        if percent >= points[-1].cum_passing:
            return points[-1].size_mm

        # Находим интервал для интерполяции
        for i in range(1, len(points)):
            if points[i].cum_passing >= percent:
                p1, p2 = points[i - 1], points[i]

                if self.interpolation == PSDInterpolation.LINEAR:
                    # Линейная интерполяция
                    t = (percent - p1.cum_passing) / (p2.cum_passing - p1.cum_passing)
                    return p1.size_mm + t * (p2.size_mm - p1.size_mm)

                elif self.interpolation == PSDInterpolation.LOG_LINEAR:
                    # Логарифмическая по размеру, линейная по проценту
                    if p1.size_mm <= 0 or p2.size_mm <= 0:
                        # Fallback to linear
                        t = (percent - p1.cum_passing) / (p2.cum_passing - p1.cum_passing)
                        return p1.size_mm + t * (p2.size_mm - p1.size_mm)

                    t = (percent - p1.cum_passing) / (p2.cum_passing - p1.cum_passing)
                    log_size = math.log(p1.size_mm) + t * (
                        math.log(p2.size_mm) - math.log(p1.size_mm)
                    )
                    return math.exp(log_size)

                else:
                    # SPLINE — требует scipy, fallback to linear
                    t = (percent - p1.cum_passing) / (p2.cum_passing - p1.cum_passing)
                    return p1.size_mm + t * (p2.size_mm - p1.size_mm)

        return None

    @computed_field
    @property
    def p80(self) -> Optional[float]:
        """P80 — основной показатель крупности."""
        return self.get_pxx(80)

    @computed_field
    @property
    def p50(self) -> Optional[float]:
        """P50 — медианный размер."""
        return self.get_pxx(50)

    def compute_quantiles(self) -> PSDQuantiles:
        """Вычисляет стандартные квантили."""
        return PSDQuantiles(
            p10=self.get_pxx(10),
            p20=self.get_pxx(20),
            p50=self.get_pxx(50),
            p80=self.get_pxx(80),
            p90=self.get_pxx(90),
            p95=self.get_pxx(95),
            p100=self.points[-1].size_mm if self.points else None,
        )

    def with_computed_quantiles(self) -> "PSD":
        """Возвращает копию PSD с заполненными quantiles."""
        return self.model_copy(update={"quantiles": self.compute_quantiles()})

    @classmethod
    def from_cumulative(cls, sizes_mm: List[float], cum_passing: List[float], **kwargs) -> "PSD":
        """
        Создаёт PSD из двух списков.

        Args:
            sizes_mm: Список размеров сит в мм
            cum_passing: Список кумулятивных % прохода
        """
        if len(sizes_mm) != len(cum_passing):
            raise ValueError("sizes_mm и cum_passing должны быть одинаковой длины")

        points = [PSDPoint(size_mm=s, cum_passing=c) for s, c in zip(sizes_mm, cum_passing)]
        return cls(points=points, **kwargs)

    def to_dict_for_chart(self) -> dict:
        """Экспорт в формат для графика."""
        return {
            "sizes_mm": [p.size_mm for p in self.points],
            "cum_passing": [p.cum_passing for p in self.points],
            "p80": self.p80,
            "p50": self.p50,
        }
