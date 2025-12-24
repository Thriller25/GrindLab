"""
Mill Models — Модели мельниц (SAG, Ball, Rod).

Реализует упрощённую модель измельчения на основе:
- Bond Work Index
- Формула Bond для расчёта энергии
- Эмпирические функции распределения продукта

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
# Mill Types
# ============================================================


class MillType:
    """Типы мельниц."""

    SAG = "sag"
    BALL = "ball"
    ROD = "rod"
    VERTICAL = "vertical"
    HPGR = "hpgr"


# ============================================================
# Energy Calculations
# ============================================================


def bond_energy(
    feed_p80_um: float,
    product_p80_um: float,
    work_index: float,
) -> float:
    """
    Расчёт удельного расхода энергии по формуле Bond.

    W = 10 * Wi * (1/√P80 - 1/√F80)

    Args:
        feed_p80_um: P80 питания в микронах
        product_p80_um: P80 продукта в микронах
        work_index: Bond Work Index, кВт·ч/т

    Returns:
        Удельный расход энергии, кВт·ч/т
    """
    if feed_p80_um <= 0 or product_p80_um <= 0:
        return 0.0

    # Формула Bond
    w = 10 * work_index * (1 / math.sqrt(product_p80_um) - 1 / math.sqrt(feed_p80_um))

    return max(0, w)


def estimate_product_p80(
    feed_p80_um: float,
    work_index: float,
    specific_energy: float,
) -> float:
    """
    Обратный расчёт P80 продукта по потребляемой энергии.

    Args:
        feed_p80_um: P80 питания в микронах
        work_index: Bond Work Index, кВт·ч/т
        specific_energy: Удельный расход энергии, кВт·ч/т

    Returns:
        P80 продукта в микронах
    """
    if work_index <= 0 or specific_energy <= 0:
        return feed_p80_um

    # W = 10 * Wi * (1/√P - 1/√F)
    # 1/√P = W/(10*Wi) + 1/√F
    inv_sqrt_f = 1 / math.sqrt(feed_p80_um)
    inv_sqrt_p = specific_energy / (10 * work_index) + inv_sqrt_f

    if inv_sqrt_p <= 0:
        return 100  # Минимальный P80

    product_p80 = 1 / (inv_sqrt_p**2)

    return max(50, min(product_p80, feed_p80_um))


def generate_product_psd(target_p80_mm: float, spread: float = 2.0) -> PSD:
    """
    Генерация PSD продукта мельницы.

    Использует модифицированное распределение Rosin-Rammler.

    Args:
        target_p80_mm: Целевой P80, мм
        spread: Параметр ширины распределения

    Returns:
        PSD продукта
    """
    # Стандартные размеры для мельничного продукта
    sizes_mm = [
        target_p80_mm * 3,
        target_p80_mm * 2,
        target_p80_mm * 1.5,
        target_p80_mm,  # P80
        target_p80_mm * 0.7,
        target_p80_mm * 0.5,
        target_p80_mm * 0.3,
        target_p80_mm * 0.15,
        target_p80_mm * 0.075,
        target_p80_mm * 0.038,
    ]

    # Rosin-Rammler: P(x) = 100 * (1 - exp(-(x/x63)^n))
    # где x63 ≈ P80 / 0.84^(1/n) для P80
    n = spread
    x63 = target_p80_mm / (0.84 ** (1 / n))

    points = []
    for size in sizes_mm:
        if size > 0:
            cum_passing = 100 * (1 - math.exp(-((size / x63) ** n)))
            cum_passing = max(0, min(100, cum_passing))
            points.append(PSDPoint(size_mm=size, cum_passing=cum_passing))

    # Сортируем и нормализуем
    points = sorted(points, key=lambda p: p.size_mm)

    # Монотонность
    for i in range(1, len(points)):
        if points[i].cum_passing < points[i - 1].cum_passing:
            points[i] = PSDPoint(size_mm=points[i].size_mm, cum_passing=points[i - 1].cum_passing)

    return PSD(points=points)


# ============================================================
# SAG Mill
# ============================================================


@NodeRegistry.register
class SAGMill(BaseNode):
    """
    Мельница полусамоизмельчения (SAG Mill).

    Первичное измельчение после дробления.
    Типичные размеры: вход 100-200 мм, выход 1-3 мм.
    """

    node_type: ClassVar[str] = "sag_mill"
    display_name: ClassVar[str] = "SAG Mill"
    category: ClassVar[NodeCategory] = NodeCategory.MILL
    description: ClassVar[str] = "Мельница полусамоизмельчения"
    icon: ClassVar[str] = "⚙️"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
                description="Питание мельницы (дроблёная руда)",
            )
        )
        self._add_port(
            NodePort(
                name="water",
                direction=PortDirection.INPUT,
                port_type=PortType.WATER,
                required=False,
                description="Добавочная вода",
            )
        )
        self._add_port(
            NodePort(
                name="product",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
                description="Разгрузка мельницы (пульпа)",
            )
        )

    def _define_parameters(self) -> None:
        # Геометрия
        self._add_parameter(
            NodeParameter(
                name="diameter_m",
                display_name="Диаметр внутри футеровки",
                param_type=ParameterType.FLOAT,
                default=10.0,
                unit="m",
                min_value=5.0,
                max_value=15.0,
                description="Диаметр барабана внутри футеровки",
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="length_m",
                display_name="Длина (EGL)",
                param_type=ParameterType.FLOAT,
                default=5.0,
                unit="m",
                min_value=2.0,
                max_value=10.0,
                description="Эффективная длина размола",
                group="geometry",
            )
        )

        # Операционные параметры
        self._add_parameter(
            NodeParameter(
                name="speed_pct_critical",
                display_name="Скорость (% от критической)",
                param_type=ParameterType.FLOAT,
                default=75.0,
                unit="%",
                min_value=60.0,
                max_value=90.0,
                description="Частота вращения",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="ball_charge_pct",
                display_name="Шаровая загрузка",
                param_type=ParameterType.FLOAT,
                default=12.0,
                unit="%",
                min_value=5.0,
                max_value=20.0,
                description="Объём шаров от объёма мельницы",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="total_filling_pct",
                display_name="Общее заполнение",
                param_type=ParameterType.FLOAT,
                default=30.0,
                unit="%",
                min_value=20.0,
                max_value=40.0,
                description="Объём загрузки от объёма мельницы",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="solids_pct",
                display_name="% твёрдого в разгрузке",
                param_type=ParameterType.FLOAT,
                default=75.0,
                unit="%",
                min_value=60.0,
                max_value=85.0,
                description="Содержание твёрдого в пульпе",
                group="operating",
            )
        )

        # Мощность
        self._add_parameter(
            NodeParameter(
                name="installed_power_kw",
                display_name="Установленная мощность",
                param_type=ParameterType.FLOAT,
                default=15000.0,
                unit="kW",
                min_value=3000.0,
                max_value=30000.0,
                description="Мощность привода",
                group="design",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="motor_efficiency",
                display_name="КПД привода",
                param_type=ParameterType.FLOAT,
                default=0.95,
                unit="",
                min_value=0.85,
                max_value=0.98,
                description="КПД электродвигателя",
                group="design",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт SAG мельницы."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material
        water_stream = inputs.get("water")

        if not feed or not feed.psd:
            return NodeResult(success=False, errors=["Feed must have PSD defined"])

        # Параметры
        diameter = self.get_param("diameter_m")
        length = self.get_param("length_m")
        speed_pct = self.get_param("speed_pct_critical")
        ball_charge = self.get_param("ball_charge_pct")
        filling = self.get_param("total_filling_pct")
        solids_pct = self.get_param("solids_pct")
        installed_power = self.get_param("installed_power_kw")
        motor_eff = self.get_param("motor_efficiency")

        warnings = []

        # Work Index из материала или по умолчанию
        work_index = 15.0  # kWh/t default
        if feed.quality and feed.quality.bond_work_index_kwh_t:
            work_index = feed.quality.bond_work_index_kwh_t

        # Расчёт потребляемой мощности (упрощённая модель)
        # P = k * D^2.5 * L * (% filling) * (% speed)
        k = 3.5  # Эмпирический коэффициент для SAG

        mill_power = (
            k
            * (diameter**2.5)
            * length
            * (filling / 100)
            * (speed_pct / 100)
            * (1 + ball_charge / 100)
        )

        mill_power = min(mill_power, installed_power * motor_eff)

        # Удельный расход энергии
        specific_energy = mill_power / feed.solids_tph if feed.solids_tph > 0 else 0

        # Расчёт P80 продукта
        feed_p80_mm = feed.psd.p80 or 100
        feed_p80_um = feed_p80_mm * 1000

        product_p80_um = estimate_product_p80(feed_p80_um, work_index, specific_energy)
        product_p80_mm = product_p80_um / 1000

        # Проверки
        if product_p80_mm > feed_p80_mm * 0.8:
            warnings.append("Low grinding efficiency - check operating parameters")

        if specific_energy > 20:
            warnings.append(f"High specific energy: {specific_energy:.1f} kWh/t")

        # Генерация PSD продукта
        product_psd = generate_product_psd(product_p80_mm, spread=2.0)

        # Расчёт воды в продукте
        total_water = feed.water_tph
        if water_stream and water_stream.material:
            total_water += water_stream.material.water_tph

        # Корректировка воды по целевому % твёрдого
        required_water = feed.solids_tph * (100 - solids_pct) / solids_pct
        if required_water > total_water:
            warnings.append(
                f"Need more water: {required_water - total_water:.0f} t/h to achieve "
                f"{solids_pct:.0f}% solids"
            )

        actual_water = max(total_water, required_water)
        actual_solids_pct = (
            feed.solids_tph / (feed.solids_tph + actual_water) * 100
            if (feed.solids_tph + actual_water) > 0
            else 0
        )

        # Выходной материал
        product_material = Material(
            name=f"{feed.name or 'Feed'} Ground",
            phase=MaterialPhase.SLURRY,
            solids_tph=feed.solids_tph,
            water_tph=actual_water,
            psd=product_psd,
            quality=feed.quality,
        )

        product_stream = Stream(
            name=f"{self.name} Discharge",
            stream_type=StreamType.SLURRY,
            material=product_material,
        )

        # KPI
        return NodeResult(
            success=True,
            outputs={"product": product_stream},
            kpis={
                "feed_p80_mm": feed_p80_mm,
                "product_p80_mm": product_p80_mm,
                "specific_energy_kwh_t": specific_energy,
                "mill_power_kw": mill_power,
                "solids_pct": actual_solids_pct,
                "reduction_ratio": feed_p80_mm / product_p80_mm if product_p80_mm > 0 else 0,
            },
            warnings=warnings,
            power_kw=mill_power,
            throughput_tph=feed.solids_tph,
            efficiency=mill_power / installed_power if installed_power > 0 else 0,
        )


# ============================================================
# Ball Mill
# ============================================================


@NodeRegistry.register
class BallMill(BaseNode):
    """
    Шаровая мельница.

    Вторичное измельчение после SAG или классификатора.
    Типичные размеры: вход 1-5 мм, выход 0.05-0.3 мм.
    """

    node_type: ClassVar[str] = "ball_mill"
    display_name: ClassVar[str] = "Ball Mill"
    category: ClassVar[NodeCategory] = NodeCategory.MILL
    description: ClassVar[str] = "Шаровая мельница для тонкого измельчения"
    icon: ClassVar[str] = "⚫"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
                description="Питание мельницы (пески циклона)",
            )
        )
        self._add_port(
            NodePort(
                name="water",
                direction=PortDirection.INPUT,
                port_type=PortType.WATER,
                required=False,
                description="Добавочная вода",
            )
        )
        self._add_port(
            NodePort(
                name="product",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
                description="Разгрузка мельницы",
            )
        )

    def _define_parameters(self) -> None:
        # Геометрия
        self._add_parameter(
            NodeParameter(
                name="diameter_m",
                display_name="Диаметр внутри футеровки",
                param_type=ParameterType.FLOAT,
                default=6.0,
                unit="m",
                min_value=3.0,
                max_value=8.0,
                description="Диаметр барабана",
                group="geometry",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="length_m",
                display_name="Длина (EGL)",
                param_type=ParameterType.FLOAT,
                default=10.0,
                unit="m",
                min_value=4.0,
                max_value=15.0,
                description="Эффективная длина размола",
                group="geometry",
            )
        )

        # Операционные
        self._add_parameter(
            NodeParameter(
                name="speed_pct_critical",
                display_name="Скорость (% от критической)",
                param_type=ParameterType.FLOAT,
                default=75.0,
                unit="%",
                min_value=65.0,
                max_value=85.0,
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="ball_charge_pct",
                display_name="Шаровая загрузка",
                param_type=ParameterType.FLOAT,
                default=30.0,
                unit="%",
                min_value=25.0,
                max_value=40.0,
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="solids_pct",
                display_name="% твёрдого в мельнице",
                param_type=ParameterType.FLOAT,
                default=75.0,
                unit="%",
                min_value=65.0,
                max_value=82.0,
                group="operating",
            )
        )

        # Мощность
        self._add_parameter(
            NodeParameter(
                name="installed_power_kw",
                display_name="Установленная мощность",
                param_type=ParameterType.FLOAT,
                default=8000.0,
                unit="kW",
                min_value=2000.0,
                max_value=20000.0,
                group="design",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт шаровой мельницы."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material
        water_stream = inputs.get("water")

        if not feed or not feed.psd:
            return NodeResult(success=False, errors=["Feed must have PSD defined"])

        # Параметры
        diameter = self.get_param("diameter_m")
        length = self.get_param("length_m")
        speed_pct = self.get_param("speed_pct_critical")
        ball_charge = self.get_param("ball_charge_pct")
        solids_pct = self.get_param("solids_pct")
        installed_power = self.get_param("installed_power_kw")

        warnings = []

        # Work Index
        work_index = 15.0
        if feed.quality and feed.quality.bond_work_index_kwh_t:
            work_index = feed.quality.bond_work_index_kwh_t

        # Расчёт мощности (модель Austin)
        k = 4.0  # Коэффициент для шаровой мельницы
        mill_power = k * (diameter**2.5) * length * (ball_charge / 100) * (speed_pct / 100)
        mill_power = min(mill_power, installed_power * 0.95)

        # Удельный расход энергии
        specific_energy = mill_power / feed.solids_tph if feed.solids_tph > 0 else 0

        # P80 продукта
        feed_p80_mm = feed.psd.p80 or 1.0
        feed_p80_um = feed_p80_mm * 1000

        product_p80_um = estimate_product_p80(feed_p80_um, work_index, specific_energy)
        product_p80_mm = product_p80_um / 1000

        # Шаровая мельница даёт более узкое распределение
        product_psd = generate_product_psd(product_p80_mm, spread=2.5)

        # Вода
        total_water = feed.water_tph
        if water_stream and water_stream.material:
            total_water += water_stream.material.water_tph

        required_water = feed.solids_tph * (100 - solids_pct) / solids_pct
        actual_water = max(total_water, required_water)

        # Выходной материал
        product_material = Material(
            name=f"{feed.name or 'Feed'} Ground",
            phase=MaterialPhase.SLURRY,
            solids_tph=feed.solids_tph,
            water_tph=actual_water,
            psd=product_psd,
            quality=feed.quality,
        )

        product_stream = Stream(
            name=f"{self.name} Discharge",
            stream_type=StreamType.SLURRY,
            material=product_material,
        )

        actual_solids_pct = (
            feed.solids_tph / (feed.solids_tph + actual_water) * 100
            if (feed.solids_tph + actual_water) > 0
            else 0
        )

        return NodeResult(
            success=True,
            outputs={"product": product_stream},
            kpis={
                "feed_p80_mm": feed_p80_mm,
                "product_p80_mm": product_p80_mm,
                "specific_energy_kwh_t": specific_energy,
                "mill_power_kw": mill_power,
                "solids_pct": actual_solids_pct,
            },
            warnings=warnings,
            power_kw=mill_power,
            throughput_tph=feed.solids_tph,
        )


# ============================================================
# Export
# ============================================================

__all__ = [
    "MillType",
    "bond_energy",
    "estimate_product_p80",
    "generate_product_psd",
    "SAGMill",
    "BallMill",
]
