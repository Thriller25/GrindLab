"""
Classifier Models — Модели классификаторов (Гидроциклоны).

Реализует модель гидроциклона на основе:
- Модель Plitt (1976)
- Упрощённые эмпирические зависимости

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
# Cyclone Efficiency Curve
# ============================================================


def rosin_rammler_efficiency(
    size_mm: float,
    d50c_mm: float,
    sharpness: float = 2.5,
) -> float:
    """
    Эффективность классификации по кривой Rosin-Rammler.

    E(d) = 1 - exp(-0.693 * (d/d50c)^n)

    Args:
        size_mm: Размер частицы, мм
        d50c_mm: Скорректированный d50, мм
        sharpness: Параметр резкости (обычно 2-4)

    Returns:
        Эффективность извлечения в пески (0-1)
    """
    if d50c_mm <= 0:
        return 0.5

    ratio = size_mm / d50c_mm
    if ratio <= 0:
        return 0.0

    efficiency = 1 - math.exp(-0.693 * (ratio**sharpness))
    return max(0.0, min(1.0, efficiency))


def partition_psd(
    feed_psd: PSD,
    d50c_mm: float,
    sharpness: float,
    bypass_fraction: float = 0.0,
) -> tuple[PSD, PSD]:
    """
    Разделение PSD питания на пески и слив.

    Args:
        feed_psd: PSD питания
        d50c_mm: Скорректированный d50, мм
        sharpness: Параметр резкости
        bypass_fraction: Доля байпаса в пески (0-1)

    Returns:
        (PSD песков, PSD слива)
    """
    underflow_points = []
    overflow_points = []

    # Преобразуем в интервальное распределение
    sorted_points = sorted(feed_psd.points, key=lambda p: p.size_mm)

    for i, point in enumerate(sorted_points):
        size_mm = point.size_mm
        cum_passing = point.cum_passing

        # Эффективность для данного размера
        e_corrected = rosin_rammler_efficiency(size_mm, d50c_mm, sharpness)

        # Учёт байпаса: E_actual = bypass + (1-bypass) * E_corrected
        e_actual = bypass_fraction + (1 - bypass_fraction) * e_corrected

        # Доля в пески = E_actual, доля в слив = (1 - E_actual)
        # Для cum_passing нужно пересчитать

        # Упрощение: сохраняем форму, но сдвигаем P50
        underflow_points.append(
            PSDPoint(size_mm=size_mm, cum_passing=cum_passing * (1 - e_actual + 0.5))
        )
        overflow_points.append(PSDPoint(size_mm=size_mm, cum_passing=cum_passing * e_actual + 10))

    # Нормализация и генерация корректных PSD
    # Пески - грубее (меньше cum_passing для мелких)
    # Слив - тоньше (больше cum_passing для мелких)

    # Более точный подход: генерируем по целевым P80
    underflow_p80_mm = d50c_mm * 2.5  # Пески грубее d50
    overflow_p80_mm = d50c_mm * 0.5  # Слив тоньше d50

    underflow_psd = _generate_cyclone_product_psd(underflow_p80_mm, coarse=True)
    overflow_psd = _generate_cyclone_product_psd(overflow_p80_mm, coarse=False)

    return underflow_psd, overflow_psd


def _generate_cyclone_product_psd(target_p80_mm: float, coarse: bool) -> PSD:
    """Генерация PSD продукта циклона."""
    if coarse:
        # Пески - более широкое распределение
        sizes = [
            target_p80_mm * 5,
            target_p80_mm * 3,
            target_p80_mm * 2,
            target_p80_mm * 1.5,
            target_p80_mm,
            target_p80_mm * 0.7,
            target_p80_mm * 0.4,
            target_p80_mm * 0.2,
        ]
        n = 1.8
    else:
        # Слив - более узкое
        sizes = [
            target_p80_mm * 4,
            target_p80_mm * 2.5,
            target_p80_mm * 1.5,
            target_p80_mm,
            target_p80_mm * 0.6,
            target_p80_mm * 0.3,
            target_p80_mm * 0.15,
            target_p80_mm * 0.075,
        ]
        n = 2.5

    x63 = target_p80_mm / (0.84 ** (1 / n))

    points = []
    for size in sizes:
        if size > 0:
            cum_passing = 100 * (1 - math.exp(-((size / x63) ** n)))
            cum_passing = max(0, min(100, cum_passing))
            points.append(PSDPoint(size_mm=size, cum_passing=cum_passing))

    points = sorted(points, key=lambda p: p.size_mm)

    # Монотонность
    for i in range(1, len(points)):
        if points[i].cum_passing < points[i - 1].cum_passing:
            points[i] = PSDPoint(size_mm=points[i].size_mm, cum_passing=points[i - 1].cum_passing)

    return PSD(points=points)


# ============================================================
# Plitt Model Parameters
# ============================================================


def plitt_d50c(
    dc_mm: float,
    di_mm: float,
    do_mm: float,
    du_mm: float,
    h_mm: float,
    q_m3h: float,
    rho_s: float,
    phi_v: float,
    rho_l: float = 1.0,
) -> float:
    """
    Расчёт d50c по модели Plitt (1976).

    Args:
        dc_mm: Диаметр циклона, мм
        di_mm: Диаметр входного патрубка, мм
        do_mm: Диаметр сливного патрубка (vortex finder), мм
        du_mm: Диаметр песковой насадки, мм
        h_mm: Высота свободного вихря, мм
        q_m3h: Объёмный расход питания, м³/ч
        rho_s: Плотность твёрдого, т/м³
        phi_v: Объёмная концентрация твёрдого (0-1)
        rho_l: Плотность жидкости, т/м³

    Returns:
        d50c в микронах
    """
    # Упрощённая формула Plitt
    # d50c = 39.7 * Dc^0.46 * Di^0.6 * Do^1.21 * exp(0.063*Cv)
    #        / (Du^0.71 * h^0.38 * Q^0.45 * (ρs - ρl)^0.5)

    cv = phi_v * 100  # % объёмная концентрация

    numerator = 39.7 * (dc_mm**0.46) * (di_mm**0.6) * (do_mm**1.21) * math.exp(0.063 * cv)

    denominator = (du_mm**0.71) * (h_mm**0.38) * (q_m3h**0.45) * ((rho_s - rho_l) ** 0.5)

    if denominator <= 0:
        return 100  # Дефолт

    d50c_um = numerator / denominator

    return max(10, min(d50c_um, 500))


# ============================================================
# Hydrocyclone
# ============================================================


@NodeRegistry.register
class Hydrocyclone(BaseNode):
    """
    Гидроциклон для классификации пульпы.

    Разделяет питание на:
    - Пески (underflow) - грубая фракция → возврат в мельницу
    - Слив (overflow) - тонкая фракция → на флотацию/сгущение
    """

    node_type: ClassVar[str] = "hydrocyclone"
    display_name: ClassVar[str] = "Hydrocyclone"
    category: ClassVar[NodeCategory] = NodeCategory.CLASSIFIER
    description: ClassVar[str] = "Гидроциклон для классификации пульпы"
    icon: ClassVar[str] = "🌀"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
                description="Питание (пульпа из мельницы)",
            )
        )
        self._add_port(
            NodePort(
                name="overflow",
                direction=PortDirection.OUTPUT,
                port_type=PortType.OVERFLOW,
                required=True,
                description="Слив (тонкий продукт)",
            )
        )
        self._add_port(
            NodePort(
                name="underflow",
                direction=PortDirection.OUTPUT,
                port_type=PortType.UNDERFLOW,
                required=True,
                description="Пески (грубый продукт)",
            )
        )

    def _define_parameters(self) -> None:
        # Конструкция циклона
        self._add_parameter(
            NodeParameter(
                name="cyclone_diameter_mm",
                display_name="Диаметр циклона",
                param_type=ParameterType.FLOAT,
                default=650.0,
                unit="mm",
                min_value=100.0,
                max_value=1500.0,
                description="Номинальный диаметр корпуса",
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="inlet_diameter_mm",
                display_name="Диаметр входа",
                param_type=ParameterType.FLOAT,
                default=200.0,
                unit="mm",
                min_value=50.0,
                max_value=500.0,
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="vortex_finder_mm",
                display_name="Диаметр сливного патрубка",
                param_type=ParameterType.FLOAT,
                default=250.0,
                unit="mm",
                min_value=75.0,
                max_value=600.0,
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="apex_diameter_mm",
                display_name="Диаметр песковой насадки",
                param_type=ParameterType.FLOAT,
                default=120.0,
                unit="mm",
                min_value=25.0,
                max_value=300.0,
                group="geometry",
            )
        )

        # Операционные
        self._add_parameter(
            NodeParameter(
                name="number_operating",
                display_name="Количество работающих",
                param_type=ParameterType.INT,
                default=6,
                unit="шт",
                min_value=1,
                max_value=20,
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="feed_pressure_kpa",
                display_name="Давление питания",
                param_type=ParameterType.FLOAT,
                default=120.0,
                unit="kPa",
                min_value=50.0,
                max_value=250.0,
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="target_d50_um",
                display_name="Целевой d50",
                param_type=ParameterType.FLOAT,
                default=75.0,
                unit="μm",
                min_value=20.0,
                max_value=300.0,
                description="Размер разделения (d50c)",
                group="operating",
            )
        )

        # Модельные
        self._add_parameter(
            NodeParameter(
                name="sharpness",
                display_name="Резкость разделения",
                param_type=ParameterType.FLOAT,
                default=2.5,
                unit="",
                min_value=1.5,
                max_value=5.0,
                description="Параметр кривой эффективности",
                group="model",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="water_split_to_underflow",
                display_name="Доля воды в пески",
                param_type=ParameterType.FLOAT,
                default=0.25,
                unit="",
                min_value=0.1,
                max_value=0.5,
                group="model",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт гидроциклона."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material

        if not feed or not feed.psd:
            return NodeResult(success=False, errors=["Feed must have PSD defined"])

        # Параметры
        # Эти параметры сохранены для будущей реализации модели Plitt
        # dc = self.get_param("cyclone_diameter_mm")
        # di = self.get_param("inlet_diameter_mm")
        # do = self.get_param("vortex_finder_mm")
        # du = self.get_param("apex_diameter_mm")
        # n_cyclones = self.get_param("number_operating")
        # pressure = self.get_param("feed_pressure_kpa")
        target_d50 = self.get_param("target_d50_um")
        sharpness = self.get_param("sharpness")
        water_split = self.get_param("water_split_to_underflow")

        warnings = []

        # d50c из модели или целевого значения
        d50c_mm = target_d50 / 1000.0

        # Извлечение в пески (грубая оценка)
        # Интегрируем эффективность по PSD
        recovery_to_uf = 0.0
        n_points = 0

        for point in feed.psd.points:
            size = point.size_mm
            e = rosin_rammler_efficiency(size, d50c_mm, sharpness)
            recovery_to_uf += e
            n_points += 1

        if n_points > 0:
            recovery_to_uf /= n_points

        # Корректировка на байпас
        bypass = 0.05  # 5% тонкого в пески
        recovery_to_uf = bypass + (1 - bypass) * recovery_to_uf

        recovery_to_uf = max(0.2, min(0.8, recovery_to_uf))
        recovery_to_of = 1 - recovery_to_uf

        # Масс-баланс твёрдого
        solids_uf = feed.solids_tph * recovery_to_uf
        solids_of = feed.solids_tph * recovery_to_of

        # Масс-баланс воды
        water_uf = feed.water_tph * water_split
        water_of = feed.water_tph * (1 - water_split)

        # Генерация PSD продуктов
        uf_p80_mm = d50c_mm * 2.0  # Пески грубее
        of_p80_mm = d50c_mm * 0.5  # Слив тоньше

        uf_psd = _generate_cyclone_product_psd(uf_p80_mm, coarse=True)
        of_psd = _generate_cyclone_product_psd(of_p80_mm, coarse=False)

        # Расчёт % твёрдого
        uf_solids_pct = (
            solids_uf / (solids_uf + water_uf) * 100 if (solids_uf + water_uf) > 0 else 0
        )
        of_solids_pct = (
            solids_of / (solids_of + water_of) * 100 if (solids_of + water_of) > 0 else 0
        )

        # Проверки
        if uf_solids_pct > 80:
            warnings.append(f"Underflow density very high: {uf_solids_pct:.0f}% - risk of roping")

        if of_solids_pct < 20:
            warnings.append(f"Overflow very dilute: {of_solids_pct:.0f}%")

        # Выходные потоки
        underflow_material = Material(
            name=f"{feed.name or 'Feed'} U/F",
            phase=MaterialPhase.SLURRY,
            solids_tph=solids_uf,
            water_tph=water_uf,
            psd=uf_psd,
            quality=feed.quality,
        )

        overflow_material = Material(
            name=f"{feed.name or 'Feed'} O/F",
            phase=MaterialPhase.SLURRY,
            solids_tph=solids_of,
            water_tph=water_of,
            psd=of_psd,
            quality=feed.quality,
        )

        underflow_stream = Stream(
            name=f"{self.name} Underflow",
            stream_type=StreamType.SLURRY,
            material=underflow_material,
        )

        overflow_stream = Stream(
            name=f"{self.name} Overflow",
            stream_type=StreamType.SLURRY,
            material=overflow_material,
        )

        return NodeResult(
            success=True,
            outputs={
                "overflow": overflow_stream,
                "underflow": underflow_stream,
            },
            kpis={
                "d50c_um": target_d50,
                "recovery_to_underflow_pct": recovery_to_uf * 100,
                "underflow_p80_um": uf_p80_mm * 1000,
                "overflow_p80_um": of_p80_mm * 1000,
                "underflow_solids_pct": uf_solids_pct,
                "overflow_solids_pct": of_solids_pct,
                "circulating_load_pct": (
                    (solids_uf / feed.solids_tph * 100) if feed.solids_tph > 0 else 0
                ),
            },
            warnings=warnings,
            throughput_tph=feed.solids_tph,
        )


# ============================================================
# Export
# ============================================================

__all__ = [
    "rosin_rammler_efficiency",
    "partition_psd",
    "plitt_d50c",
    "Hydrocyclone",
]
