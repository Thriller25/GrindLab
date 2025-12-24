"""
PSD Operations — Операции над гранулометрическим составом.

F3.3: bins + rebin + расширенные Pxx операции.

Включает:
- Стандартные сетки сит (Tyler, ISO, ASTM)
- Перебиновка (rebin) между разными сетками
- Математические операции (сложение, усреднение PSD)
- Расчёт характеристик (span, uniformity, средний размер)

Версия: 1.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .psd import PSD, PSDPoint, PSDStats

# ==================== Стандартные сетки сит ====================


class SieveStandard(str, Enum):
    """Стандарты сеток сит."""

    TYLER = "tyler"  # Tyler mesh
    ISO = "iso"  # ISO 565 / ISO 3310
    ASTM = "astm"  # ASTM E11
    CUSTOM = "custom"  # Пользовательская


@dataclass(frozen=True)
class SieveSeries:
    """Серия сит с размерами."""

    standard: SieveStandard
    name: str
    sizes_mm: Tuple[float, ...]

    def __len__(self) -> int:
        return len(self.sizes_mm)

    def __iter__(self):
        return iter(self.sizes_mm)

    def as_list(self) -> List[float]:
        return list(self.sizes_mm)


# Tyler mesh series (основные размеры в мм)
TYLER_SERIES = SieveSeries(
    standard=SieveStandard.TYLER,
    name="Tyler Mesh",
    sizes_mm=(
        0.038,
        0.045,
        0.053,
        0.063,
        0.075,
        0.090,
        0.106,
        0.125,
        0.150,
        0.180,
        0.212,
        0.250,
        0.300,
        0.355,
        0.425,
        0.500,
        0.600,
        0.710,
        0.850,
        1.000,
        1.180,
        1.400,
        1.700,
        2.000,
        2.360,
        2.800,
        3.350,
        4.000,
        4.750,
        5.600,
        6.700,
        8.000,
        9.500,
        11.200,
        13.200,
        16.000,
        19.000,
        22.400,
        26.500,
        31.500,
        37.500,
        45.000,
        53.000,
        63.000,
        75.000,
        90.000,
        106.000,
        125.000,
        150.000,
    ),
)

# ISO 565 R20 series (основные размеры в мм)
ISO_R20_SERIES = SieveSeries(
    standard=SieveStandard.ISO,
    name="ISO 565 R20",
    sizes_mm=(
        0.020,
        0.025,
        0.032,
        0.040,
        0.050,
        0.063,
        0.080,
        0.100,
        0.125,
        0.160,
        0.200,
        0.250,
        0.315,
        0.400,
        0.500,
        0.630,
        0.800,
        1.000,
        1.250,
        1.600,
        2.000,
        2.500,
        3.150,
        4.000,
        5.000,
        6.300,
        8.000,
        10.000,
        12.500,
        16.000,
        20.000,
        25.000,
        31.500,
        40.000,
        50.000,
        63.000,
        80.000,
        100.000,
        125.000,
    ),
)

# Стандартная грубая сетка для измельчения (от P80=0.075 до feed=150mm)
GRINDING_COARSE_SERIES = SieveSeries(
    standard=SieveStandard.CUSTOM,
    name="Grinding Coarse",
    sizes_mm=(
        0.038,
        0.075,
        0.150,
        0.300,
        0.600,
        1.180,
        2.360,
        4.750,
        9.500,
        19.000,
        37.500,
        75.000,
        150.000,
    ),
)

# Тонкая сетка для флотации
FLOTATION_FINE_SERIES = SieveSeries(
    standard=SieveStandard.CUSTOM,
    name="Flotation Fine",
    sizes_mm=(
        0.010,
        0.020,
        0.038,
        0.053,
        0.075,
        0.106,
        0.150,
        0.212,
        0.300,
    ),
)

# Реестр стандартных сеток
SIEVE_SERIES_REGISTRY: Dict[str, SieveSeries] = {
    "tyler": TYLER_SERIES,
    "iso_r20": ISO_R20_SERIES,
    "grinding_coarse": GRINDING_COARSE_SERIES,
    "flotation_fine": FLOTATION_FINE_SERIES,
}


def get_sieve_series(name: str) -> SieveSeries:
    """Получает серию сит по имени."""
    if name not in SIEVE_SERIES_REGISTRY:
        available = ", ".join(SIEVE_SERIES_REGISTRY.keys())
        raise ValueError(f"Unknown sieve series '{name}'. Available: {available}")
    return SIEVE_SERIES_REGISTRY[name]


def create_custom_series(sizes_mm: List[float], name: str = "Custom") -> SieveSeries:
    """Создаёт пользовательскую серию сит."""
    sorted_sizes = tuple(sorted(sizes_mm))
    return SieveSeries(
        standard=SieveStandard.CUSTOM,
        name=name,
        sizes_mm=sorted_sizes,
    )


# ==================== Операции с PSD ====================


def rebin_psd(psd: PSD, target_sizes: List[float]) -> PSD:
    """
    Перебиновка PSD на новую сетку сит.

    Интерполирует исходный PSD на новые размеры сит.

    Args:
        psd: Исходный PSD
        target_sizes: Целевые размеры сит в мм

    Returns:
        Новый PSD на целевой сетке

    Example:
        >>> psd = PSD.from_cumulative([0.1, 0.5, 1.0], [20, 60, 95])
        >>> rebinned = rebin_psd(psd, [0.2, 0.4, 0.6, 0.8])
    """
    sorted_sizes = sorted(target_sizes)

    new_points = []
    for size in sorted_sizes:
        cum_passing = psd.get_pxx_inverse(size)
        if cum_passing is not None:
            new_points.append(PSDPoint(size_mm=size, cum_passing=cum_passing))

    if len(new_points) < 2:
        raise ValueError(
            f"Cannot rebin: insufficient overlap between original PSD "
            f"(range {psd.points[0].size_mm}-{psd.points[-1].size_mm} mm) "
            f"and target sizes ({sorted_sizes[0]}-{sorted_sizes[-1]} mm)"
        )

    return PSD(
        points=new_points,
        interpolation=psd.interpolation,
        source=f"rebinned from {psd.source or 'unknown'}",
    )


def blend_psds(
    psds: List[PSD],
    weights: List[float],
    target_sizes: Optional[List[float]] = None,
) -> PSD:
    """
    Смешивание нескольких PSD с весами.

    Сначала перебиновывает все PSD на общую сетку,
    затем вычисляет средневзвешенный cum_passing.

    Args:
        psds: Список PSD для смешивания
        weights: Весовые коэффициенты (будут нормализованы)
        target_sizes: Целевая сетка (если None, используется объединение)

    Returns:
        Смешанный PSD

    Example:
        >>> blend = blend_psds([psd1, psd2], [0.7, 0.3])
    """
    if len(psds) != len(weights):
        raise ValueError("Number of PSDs must match number of weights")

    if len(psds) == 0:
        raise ValueError("At least one PSD required")

    if len(psds) == 1:
        return psds[0]

    # Нормализуем веса
    total_weight = sum(weights)
    norm_weights = [w / total_weight for w in weights]

    # Определяем целевую сетку
    if target_sizes is None:
        # Объединяем все размеры из всех PSD
        all_sizes = set()
        for psd in psds:
            all_sizes.update(p.size_mm for p in psd.points)
        target_sizes = sorted(all_sizes)

    # Вычисляем средневзвешенный cum_passing для каждого размера
    new_points = []
    for size in target_sizes:
        weighted_sum = 0.0
        valid_weight_sum = 0.0

        for psd, weight in zip(psds, norm_weights):
            cum = psd.get_pxx_inverse(size)
            if cum is not None:
                weighted_sum += cum * weight
                valid_weight_sum += weight

        if valid_weight_sum > 0:
            avg_cum = weighted_sum / valid_weight_sum
            new_points.append(PSDPoint(size_mm=size, cum_passing=avg_cum))

    if len(new_points) < 2:
        raise ValueError("Cannot blend: insufficient overlapping data")

    return PSD(
        points=new_points,
        source="blended",
    )


def compute_psd_stats(psd: PSD) -> PSDStats:
    """
    Вычисляет статистические характеристики PSD.

    Returns:
        PSDStats с d50, d_mean, span, uniformity_coefficient
    """
    p10 = psd.get_pxx(10)
    p50 = psd.get_pxx(50)
    p60 = psd.get_pxx(60)
    p90 = psd.get_pxx(90)

    # Span = (P90 - P10) / P50
    span = None
    if p10 and p50 and p90 and p50 > 0:
        span = (p90 - p10) / p50

    # Uniformity coefficient Cu = D60 / D10
    uniformity = None
    if p10 and p60 and p10 > 0:
        uniformity = p60 / p10

    # Средний размер (log-mean между точками)
    d_mean = _compute_log_mean_size(psd)

    return PSDStats(
        d50=p50,
        d_mean=d_mean,
        span=span,
        uniformity_coefficient=uniformity,
    )


def _compute_log_mean_size(psd: PSD) -> Optional[float]:
    """
    Вычисляет логарифмический средний размер.

    Средневзвешенный по массе с использованием геометрического среднего
    между соседними ситами.
    """
    if len(psd.points) < 2:
        return None

    total_mass = 0.0
    weighted_sum = 0.0

    for i in range(1, len(psd.points)):
        p1, p2 = psd.points[i - 1], psd.points[i]

        # Масса фракции = разница cum_passing
        mass_fraction = p2.cum_passing - p1.cum_passing

        if mass_fraction > 0 and p1.size_mm > 0 and p2.size_mm > 0:
            # Геометрическое среднее размеров фракции
            geom_mean = math.sqrt(p1.size_mm * p2.size_mm)
            weighted_sum += mass_fraction * math.log(geom_mean)
            total_mass += mass_fraction

    if total_mass > 0:
        return math.exp(weighted_sum / total_mass)
    return None


def compute_retained(psd: PSD) -> List[Tuple[float, float, float]]:
    """
    Вычисляет % задержки на каждом сите.

    Returns:
        List of (size_mm, cum_passing, retained_percent) tuples
    """
    result = []
    prev_cum = 0.0

    for point in psd.points:
        retained = point.cum_passing - prev_cum
        result.append((point.size_mm, point.cum_passing, retained))
        prev_cum = point.cum_passing

    return result


def psd_to_histogram(psd: PSD) -> Dict[str, List[float]]:
    """
    Конвертирует PSD в данные для гистограммы.

    Returns:
        Dict с ключами: bin_edges, bin_centers, frequencies
    """
    retained = compute_retained(psd)

    bin_edges = [r[0] for r in retained]
    frequencies = [r[2] for r in retained]

    # Центры бинов (геометрическое среднее)
    bin_centers = []
    for i in range(len(bin_edges)):
        if i == 0:
            # Первый бин: от 0 до первого сита
            bin_centers.append(bin_edges[0] / 2)
        else:
            bin_centers.append(math.sqrt(bin_edges[i - 1] * bin_edges[i]))

    return {
        "bin_edges": bin_edges,
        "bin_centers": bin_centers,
        "frequencies": frequencies,
    }


def truncate_psd(
    psd: PSD,
    min_size: Optional[float] = None,
    max_size: Optional[float] = None,
) -> PSD:
    """
    Обрезает PSD до заданного диапазона размеров.

    Args:
        psd: Исходный PSD
        min_size: Минимальный размер (или None)
        max_size: Максимальный размер (или None)

    Returns:
        Обрезанный PSD (перенормализованный к 0-100%)
    """
    filtered_points = []

    for point in psd.points:
        if min_size is not None and point.size_mm < min_size:
            continue
        if max_size is not None and point.size_mm > max_size:
            continue
        filtered_points.append(point)

    if len(filtered_points) < 2:
        raise ValueError(
            f"Truncation leaves less than 2 points " f"(range {min_size}-{max_size} mm)"
        )

    # Перенормализация: min_cum -> 0%, max_cum -> 100%
    min_cum = filtered_points[0].cum_passing
    max_cum = filtered_points[-1].cum_passing
    range_cum = max_cum - min_cum

    if range_cum <= 0:
        raise ValueError("Cannot normalize: no variation in cum_passing")

    normalized_points = [
        PSDPoint(
            size_mm=p.size_mm,
            cum_passing=(p.cum_passing - min_cum) / range_cum * 100,
        )
        for p in filtered_points
    ]

    return PSD(
        points=normalized_points,
        interpolation=psd.interpolation,
        source=f"truncated({min_size}-{max_size}mm)",
    )


def scale_psd(psd: PSD, factor: float) -> PSD:
    """
    Масштабирует размеры PSD (сдвиг кривой).

    Полезно для моделирования эффекта измельчения.

    Args:
        psd: Исходный PSD
        factor: Коэффициент масштабирования (< 1 = мельче, > 1 = крупнее)

    Returns:
        Масштабированный PSD
    """
    if factor <= 0:
        raise ValueError("Scale factor must be positive")

    new_points = [
        PSDPoint(size_mm=p.size_mm * factor, cum_passing=p.cum_passing) for p in psd.points
    ]

    return PSD(
        points=new_points,
        interpolation=psd.interpolation,
        source=f"scaled({factor:.2f}x)",
    )


# ==================== Расширение PSD класса ====================


def add_psd_inverse_method(psd_class):
    """
    Добавляет метод get_pxx_inverse к классу PSD.

    get_pxx_inverse(size_mm) -> cum_passing
    (обратная операция к get_pxx)
    """

    def get_pxx_inverse(self, size_mm: float) -> Optional[float]:
        """
        Получает cum_passing для заданного размера.

        Args:
            size_mm: Размер частиц в мм

        Returns:
            cum_passing в % или None если вне диапазона
        """
        points = self.points

        # Граничные случаи - возвращаем None для размеров вне диапазона
        if size_mm < points[0].size_mm:
            return None
        if size_mm > points[-1].size_mm:
            return None

        # Точные совпадения с границами
        if size_mm == points[0].size_mm:
            return points[0].cum_passing
        if size_mm == points[-1].size_mm:
            return points[-1].cum_passing

        # Находим интервал
        for i in range(1, len(points)):
            if points[i].size_mm >= size_mm:
                p1, p2 = points[i - 1], points[i]

                if self.interpolation.value == "log_linear":
                    # Log-linear интерполяция
                    if p1.size_mm <= 0 or p2.size_mm <= 0:
                        t = (size_mm - p1.size_mm) / (p2.size_mm - p1.size_mm)
                    else:
                        log_t = (math.log(size_mm) - math.log(p1.size_mm)) / (
                            math.log(p2.size_mm) - math.log(p1.size_mm)
                        )
                        t = log_t
                else:
                    # Linear интерполяция
                    t = (size_mm - p1.size_mm) / (p2.size_mm - p1.size_mm)

                return p1.cum_passing + t * (p2.cum_passing - p1.cum_passing)

        return None

    psd_class.get_pxx_inverse = get_pxx_inverse
    return psd_class


# Применяем расширение к PSD
add_psd_inverse_method(PSD)


# ==================== Экспорт ====================

__all__ = [
    # Sieve standards
    "SieveStandard",
    "SieveSeries",
    "TYLER_SERIES",
    "ISO_R20_SERIES",
    "GRINDING_COARSE_SERIES",
    "FLOTATION_FINE_SERIES",
    "SIEVE_SERIES_REGISTRY",
    "get_sieve_series",
    "create_custom_series",
    # PSD operations
    "rebin_psd",
    "blend_psds",
    "compute_psd_stats",
    "compute_retained",
    "psd_to_histogram",
    "truncate_psd",
    "scale_psd",
]
