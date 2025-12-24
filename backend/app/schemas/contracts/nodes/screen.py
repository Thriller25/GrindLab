"""
Screen Models — Модели грохотов.

Реализует модель вибрационного грохота:
- Эффективность классификации по размеру сита
- Расчёт пропускной способности

Версия: 1.0
"""

from __future__ import annotations

import math
from typing import ClassVar, Dict

from ..material import Material, MaterialPhase
from ..psd import PSD, PSDPoint
from ..stream import Stream, StreamType
from .base import (
    BaseNode,
    NodeCategory,
    NodeParameter,
    NodePort,
    NodeRegistry,
    NodeResult,
    ParameterType,
    PortDirection,
    PortType,
)

# ============================================================
# Screen Efficiency Model
# ============================================================


def screen_efficiency_curve(
    size_mm: float,
    aperture_mm: float,
    efficiency: float = 0.95,
) -> float:
    """
    Вероятность прохождения частицы через сито.

    Модифицированная формула Gaudin-Schuhmann:
    - Частицы < 0.5*aperture: 100% проходят
    - Частицы = aperture: ~50% проходят
    - Частицы > 1.5*aperture: 0% проходят

    Args:
        size_mm: Размер частицы, мм
        aperture_mm: Размер ячейки сита, мм
        efficiency: Эффективность грохочения (0-1)

    Returns:
        Вероятность прохода (0-1)
    """
    if aperture_mm <= 0:
        return 0.0

    ratio = size_mm / aperture_mm

    if ratio < 0.5:
        # Мелкие частицы легко проходят
        prob = 1.0
    elif ratio < 1.0:
        # Переходная зона
        prob = 1.0 - 0.5 * ((ratio - 0.5) / 0.5) ** 2
    elif ratio < 1.5:
        # Около размера ячейки
        prob = 0.5 * (1 - ((ratio - 1.0) / 0.5)) ** 2
    else:
        # Крупные частицы не проходят
        prob = 0.0

    return prob * efficiency


def partition_by_screen(
    feed_psd: PSD,
    aperture_mm: float,
    efficiency: float = 0.95,
) -> tuple[float, float]:
    """
    Расчёт распределения массы между надситовым и подситовым.

    Args:
        feed_psd: PSD питания
        aperture_mm: Размер ячейки, мм
        efficiency: Эффективность

    Returns:
        (доля в подситовый, доля в надситовый)
    """
    total_undersize = 0.0
    total_mass = 0.0

    sorted_points = sorted(feed_psd.points, key=lambda p: p.size_mm)

    for i, point in enumerate(sorted_points):
        size = point.size_mm

        # Масса фракции (разность cum_passing)
        if i == 0:
            mass_frac = point.cum_passing
        else:
            mass_frac = point.cum_passing - sorted_points[i - 1].cum_passing

        mass_frac = max(0, mass_frac)

        # Вероятность прохода
        prob = screen_efficiency_curve(size, aperture_mm, efficiency)

        total_undersize += mass_frac * prob
        total_mass += mass_frac

    if total_mass <= 0:
        return 0.5, 0.5

    undersize_fraction = total_undersize / 100  # Нормируем к 0-1
    oversize_fraction = 1 - undersize_fraction

    return undersize_fraction, oversize_fraction


def generate_screen_product_psd(
    feed_psd: PSD,
    aperture_mm: float,
    is_oversize: bool,
) -> PSD:
    """
    Генерация PSD продукта грохота.

    Args:
        feed_psd: PSD питания
        aperture_mm: Размер ячейки, мм
        is_oversize: True для надситового, False для подситового

    Returns:
        PSD продукта
    """
    if is_oversize:
        # Надситовый - только крупнее апертуры
        target_p80 = aperture_mm * 2.0
        min_size = aperture_mm * 0.8
        sizes = [
            min_size,
            aperture_mm,
            aperture_mm * 1.3,
            aperture_mm * 1.6,
            aperture_mm * 2.0,
            aperture_mm * 3.0,
            aperture_mm * 5.0,
        ]
    else:
        # Подситовый - только мельче апертуры
        target_p80 = aperture_mm * 0.6
        sizes = [
            aperture_mm * 0.05,
            aperture_mm * 0.1,
            aperture_mm * 0.2,
            aperture_mm * 0.4,
            aperture_mm * 0.6,
            aperture_mm * 0.8,
            aperture_mm,
        ]

    # Генерация Rosin-Rammler
    n = 2.5
    x63 = target_p80 / (0.84 ** (1 / n))

    points = []
    for size in sizes:
        if size > 0:
            cum_passing = 100 * (1 - math.exp(-((size / x63) ** n)))
            cum_passing = max(0, min(100, cum_passing))
            points.append(PSDPoint(size_mm=size, cum_passing=cum_passing))

    points = sorted(points, key=lambda p: p.size_mm)

    # Для надситового ограничиваем снизу
    if is_oversize:
        # Очень мало мелочи
        for i, p in enumerate(points):
            if p.size_mm < aperture_mm:
                # Только небольшой % проскальзывания
                points[i] = PSDPoint(size_mm=p.size_mm, cum_passing=min(10, p.cum_passing))

    # Для подситового ограничиваем сверху
    if not is_oversize:
        for i, p in enumerate(points):
            if p.size_mm >= aperture_mm:
                # Почти 100%
                points[i] = PSDPoint(size_mm=p.size_mm, cum_passing=min(98, p.cum_passing))

    # Монотонность
    for i in range(1, len(points)):
        if points[i].cum_passing < points[i - 1].cum_passing:
            points[i] = PSDPoint(size_mm=points[i].size_mm, cum_passing=points[i - 1].cum_passing)

    return PSD(points=points)


# ============================================================
# Vibrating Screen
# ============================================================


@NodeRegistry.register
class VibScreen(BaseNode):
    """
    Вибрационный грохот.

    Разделяет сухой или влажный материал по размеру:
    - Надситовый (oversize) - крупнее размера ячейки
    - Подситовый (undersize) - мельче размера ячейки
    """

    node_type: ClassVar[str] = "vibrating_screen"
    display_name: ClassVar[str] = "Vibrating Screen"
    category: ClassVar[NodeCategory] = NodeCategory.SCREEN
    description: ClassVar[str] = "Вибрационный грохот"
    icon: ClassVar[str] = "📊"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
                description="Питание грохота",
            )
        )
        self._add_port(
            NodePort(
                name="oversize",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
                description="Надситовый продукт (крупный)",
            )
        )
        self._add_port(
            NodePort(
                name="undersize",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
                description="Подситовый продукт (мелкий)",
            )
        )

    def _define_parameters(self) -> None:
        # Конструкция
        self._add_parameter(
            NodeParameter(
                name="width_m",
                display_name="Ширина",
                param_type=ParameterType.FLOAT,
                default=3.0,
                unit="m",
                min_value=1.0,
                max_value=5.0,
                description="Ширина сита",
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="length_m",
                display_name="Длина",
                param_type=ParameterType.FLOAT,
                default=6.0,
                unit="m",
                min_value=2.0,
                max_value=10.0,
                description="Длина сита",
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="aperture_mm",
                display_name="Размер ячейки",
                param_type=ParameterType.FLOAT,
                default=25.0,
                unit="mm",
                min_value=0.5,
                max_value=200.0,
                description="Размер отверстия сита",
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="deck_count",
                display_name="Количество дек",
                param_type=ParameterType.INT,
                default=1,
                unit="",
                min_value=1,
                max_value=3,
                description="Количество сит",
                group="geometry",
            )
        )

        # Операционные
        self._add_parameter(
            NodeParameter(
                name="efficiency",
                display_name="Эффективность",
                param_type=ParameterType.FLOAT,
                default=0.92,
                unit="",
                min_value=0.7,
                max_value=0.98,
                description="Эффективность грохочения",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="moisture_pct",
                display_name="Влажность питания",
                param_type=ParameterType.FLOAT,
                default=5.0,
                unit="%",
                min_value=0.0,
                max_value=20.0,
                description="Влияет на эффективность",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="spray_water",
                display_name="Орошение",
                param_type=ParameterType.BOOL,
                default=False,
                unit="",
                description="Подача воды на сито",
                group="operating",
            )
        )

        # Мощность
        self._add_parameter(
            NodeParameter(
                name="installed_power_kw",
                display_name="Установленная мощность",
                param_type=ParameterType.FLOAT,
                default=45.0,
                unit="kW",
                min_value=10.0,
                max_value=150.0,
                group="design",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт грохота."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material

        if not feed or not feed.psd:
            return NodeResult(success=False, errors=["Feed must have PSD defined"])

        # Параметры
        width = self.get_param("width_m")
        length = self.get_param("length_m")
        aperture = self.get_param("aperture_mm")
        efficiency = self.get_param("efficiency")
        moisture = self.get_param("moisture_pct")
        spray = self.get_param("spray_water")
        power = self.get_param("installed_power_kw")

        warnings = []

        # Корректировка эффективности по влажности
        if moisture > 10 and not spray:
            efficiency *= 0.85
            warnings.append("High moisture reduces screening efficiency")

        if spray:
            efficiency = min(0.98, efficiency * 1.05)

        # Расчёт площади
        area_m2 = width * length

        # Проверка пропускной способности
        # Типичная нагрузка 50-100 т/(м²·ч) для мелкого грохочения
        specific_capacity = feed.solids_tph / area_m2
        if specific_capacity > 80:
            warnings.append(
                f"High specific load: {specific_capacity:.0f} t/(m²·h) - may reduce efficiency"
            )

        # Разделение массы
        undersize_frac, oversize_frac = partition_by_screen(feed.psd, aperture, efficiency)

        # Масс-баланс
        solids_oversize = feed.solids_tph * oversize_frac
        solids_undersize = feed.solids_tph * undersize_frac

        # Вода уходит в основном в подситовый
        water_split_to_undersize = 0.7 if spray else 0.3
        water_oversize = feed.water_tph * (1 - water_split_to_undersize)
        water_undersize = feed.water_tph * water_split_to_undersize

        # Генерация PSD продуктов
        oversize_psd = generate_screen_product_psd(feed.psd, aperture, is_oversize=True)
        undersize_psd = generate_screen_product_psd(feed.psd, aperture, is_oversize=False)

        # Определение фазы
        oversize_phase = MaterialPhase.SOLID if feed.water_tph < 1 else MaterialPhase.SLURRY
        undersize_phase = MaterialPhase.SLURRY if spray else oversize_phase

        # Выходные потоки
        oversize_material = Material(
            name=f"{feed.name or 'Feed'} +{aperture:.0f}mm",
            phase=oversize_phase,
            solids_tph=solids_oversize,
            water_tph=water_oversize,
            psd=oversize_psd,
            quality=feed.quality,
        )

        undersize_material = Material(
            name=f"{feed.name or 'Feed'} -{aperture:.0f}mm",
            phase=undersize_phase,
            solids_tph=solids_undersize,
            water_tph=water_undersize,
            psd=undersize_psd,
            quality=feed.quality,
        )

        oversize_stream = Stream(
            name=f"{self.name} Oversize",
            stream_type=(
                StreamType.SLURRY if oversize_phase == MaterialPhase.SLURRY else StreamType.SOLIDS
            ),
            material=oversize_material,
        )

        undersize_stream = Stream(
            name=f"{self.name} Undersize",
            stream_type=(
                StreamType.SLURRY if undersize_phase == MaterialPhase.SLURRY else StreamType.SOLIDS
            ),
            material=undersize_material,
        )

        # Фактическая мощность
        actual_power = power * (feed.solids_tph / 500) if feed.solids_tph < 500 else power

        return NodeResult(
            success=True,
            outputs={
                "oversize": oversize_stream,
                "undersize": undersize_stream,
            },
            kpis={
                "aperture_mm": aperture,
                "oversize_pct": oversize_frac * 100,
                "undersize_pct": undersize_frac * 100,
                "efficiency": efficiency,
                "specific_capacity_t_m2h": specific_capacity,
                "screen_area_m2": area_m2,
            },
            warnings=warnings,
            power_kw=actual_power,
            throughput_tph=feed.solids_tph,
        )


# ============================================================
# Banana Screen (для тонкого грохочения)
# ============================================================


@NodeRegistry.register
class BananaScreen(BaseNode):
    """
    Банановый грохот (наклонный многоуровневый).

    Используется для тонкого грохочения с высокой производительностью.
    Имеет переменный угол наклона по длине.
    """

    node_type: ClassVar[str] = "banana_screen"
    display_name: ClassVar[str] = "Banana Screen"
    category: ClassVar[NodeCategory] = NodeCategory.SCREEN
    description: ClassVar[str] = "Банановый грохот для тонкого грохочения"
    icon: ClassVar[str] = "🍌"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
            )
        )
        self._add_port(
            NodePort(
                name="oversize",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
            )
        )
        self._add_port(
            NodePort(
                name="undersize",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
            )
        )

    def _define_parameters(self) -> None:
        self._add_parameter(
            NodeParameter(
                name="width_m",
                display_name="Ширина",
                param_type=ParameterType.FLOAT,
                default=3.6,
                unit="m",
                min_value=2.0,
                max_value=5.0,
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="length_m",
                display_name="Длина",
                param_type=ParameterType.FLOAT,
                default=7.3,
                unit="m",
                min_value=4.0,
                max_value=10.0,
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="aperture_mm",
                display_name="Размер ячейки",
                param_type=ParameterType.FLOAT,
                default=1.0,
                unit="mm",
                min_value=0.1,
                max_value=25.0,
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="panel_count",
                display_name="Количество панелей",
                param_type=ParameterType.INT,
                default=5,
                unit="",
                min_value=3,
                max_value=8,
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="efficiency",
                display_name="Эффективность",
                param_type=ParameterType.FLOAT,
                default=0.90,
                unit="",
                min_value=0.7,
                max_value=0.95,
                group="operating",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт бананового грохота."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material

        if not feed or not feed.psd:
            return NodeResult(success=False, errors=["Feed must have PSD defined"])

        # Параметры
        width = self.get_param("width_m")
        length = self.get_param("length_m")
        aperture = self.get_param("aperture_mm")
        efficiency = self.get_param("efficiency")

        warnings = []

        # Банановый грохот имеет повышенную производительность
        area_m2 = width * length
        effective_area = area_m2 * 1.3  # Коэффициент за счёт угла

        undersize_frac, oversize_frac = partition_by_screen(feed.psd, aperture, efficiency)

        # Масс-баланс
        solids_oversize = feed.solids_tph * oversize_frac
        solids_undersize = feed.solids_tph * undersize_frac
        water_undersize = feed.water_tph * 0.6
        water_oversize = feed.water_tph * 0.4

        # PSD продуктов
        oversize_psd = generate_screen_product_psd(feed.psd, aperture, is_oversize=True)
        undersize_psd = generate_screen_product_psd(feed.psd, aperture, is_oversize=False)

        oversize_material = Material(
            name=f"{feed.name or 'Feed'} +{aperture:.1f}mm",
            phase=MaterialPhase.SLURRY,
            solids_tph=solids_oversize,
            water_tph=water_oversize,
            psd=oversize_psd,
            quality=feed.quality,
        )

        undersize_material = Material(
            name=f"{feed.name or 'Feed'} -{aperture:.1f}mm",
            phase=MaterialPhase.SLURRY,
            solids_tph=solids_undersize,
            water_tph=water_undersize,
            psd=undersize_psd,
            quality=feed.quality,
        )

        return NodeResult(
            success=True,
            outputs={
                "oversize": Stream(
                    name=f"{self.name} Oversize",
                    stream_type=StreamType.SLURRY,
                    material=oversize_material,
                ),
                "undersize": Stream(
                    name=f"{self.name} Undersize",
                    stream_type=StreamType.SLURRY,
                    material=undersize_material,
                ),
            },
            kpis={
                "aperture_mm": aperture,
                "oversize_pct": oversize_frac * 100,
                "undersize_pct": undersize_frac * 100,
                "efficiency": efficiency,
                "effective_area_m2": effective_area,
            },
            warnings=warnings,
            throughput_tph=feed.solids_tph,
        )


# ============================================================
# Export
# ============================================================

__all__ = [
    "screen_efficiency_curve",
    "partition_by_screen",
    "generate_screen_product_psd",
    "VibScreen",
    "BananaScreen",
]
