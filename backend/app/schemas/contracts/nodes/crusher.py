"""
Crusher Models — Модели дробилок (Jaw, Cone, Gyratory).

Реализует упрощённую модель дробления на основе:
- CSS (Closed Side Setting) — закрытая щель
- Коэффициент дробления
- Функция дробления (breakage function)

Версия: 1.0
"""

from __future__ import annotations

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
# Crusher Types
# ============================================================


class CrusherType:
    """Типы дробилок."""

    JAW = "jaw"
    CONE = "cone"
    GYRATORY = "gyratory"
    IMPACT = "impact"
    HPGR = "hpgr"


# ============================================================
# Crusher Model Functions
# ============================================================


def apply_css_crushing(psd: PSD, css_mm: float, reduction_ratio: float = 3.0) -> PSD:
    """
    Применить модель дробления с CSS.

    Простая модель:
    - Всё что крупнее CSS * reduction_ratio — дробится
    - Материал распределяется логнормально вниз до CSS

    Args:
        psd: Исходный PSD
        css_mm: Закрытая щель, мм
        reduction_ratio: Коэффициент дробления

    Returns:
        Новый PSD после дробления
    """
    if not psd.points:
        return psd

    # Максимальный размер на выходе ~ CSS * k
    max_product_size = css_mm * 1.5  # Некоторый материал может быть крупнее CSS

    # Получаем точки и их значения
    sorted_points = sorted(psd.points, key=lambda p: p.size_mm)

    # Новые точки
    new_points = []

    for point in sorted_points:
        if point.size_mm <= max_product_size:
            # Материал мельче max_product проходит без изменений
            new_points.append(point)
        else:
            # Крупный материал дробится - его cum_passing увеличивается
            # Упрощённая модель: весь материал > max_product переходит в < max_product
            pass  # Будет обработан ниже

    # Находим процент материала > max_product_size
    try:
        passing_at_max = psd.get_passing(max_product_size)
    except Exception:
        passing_at_max = 100.0

    # Весь материал теперь проходит через max_product_size
    # Перераспределяем крупный класс вниз

    # Генерируем точки продукта
    product_points = []

    # Стандартные размеры для выходного PSD
    sizes = [
        max_product_size,
        max_product_size * 0.7,
        css_mm,
        css_mm * 0.7,
        css_mm * 0.5,
        css_mm * 0.3,
        css_mm * 0.15,
        css_mm * 0.075,
    ]

    # Убираем дубликаты и сортируем
    sizes = sorted(set(s for s in sizes if s > 0))

    # Вычисляем cum_passing для продукта
    # Упрощённая модель: логнормальное распределение
    for size in sizes:
        if size >= max_product_size:
            cum_pass = 100.0
        else:
            # Интерполируем между исходным и 100%
            try:
                orig_pass = psd.get_passing(size)
            except Exception:
                orig_pass = 0.0

            # Добавляем дроблённый материал
            # Доля дроблённого = (100 - passing_at_max)
            crushed_fraction = 100.0 - passing_at_max

            # Распределение дроблённого материала (грубая модель)
            # Чем ближе к CSS, тем больше материала
            if size >= css_mm:
                crushed_pass = crushed_fraction * (size / max_product_size) ** 0.5
            else:
                crushed_pass = crushed_fraction * (size / css_mm) ** 0.3

            cum_pass = min(100.0, orig_pass + crushed_pass)

        product_points.append(PSDPoint(size_mm=size, cum_passing=cum_pass))

    # Сортируем и нормализуем
    product_points = sorted(product_points, key=lambda p: p.size_mm)

    # Убедимся в монотонности
    for i in range(1, len(product_points)):
        if product_points[i].cum_passing < product_points[i - 1].cum_passing:
            product_points[i] = PSDPoint(
                size_mm=product_points[i].size_mm,
                cum_passing=product_points[i - 1].cum_passing,
            )

    return PSD(points=product_points)


# ============================================================
# Jaw Crusher
# ============================================================


@NodeRegistry.register
class JawCrusher(BaseNode):
    """
    Щековая дробилка.

    Первичное дробление крупной руды (ROM).
    Типичные размеры: вход 500-1500 мм, выход 100-300 мм.
    """

    node_type: ClassVar[str] = "jaw_crusher"
    display_name: ClassVar[str] = "Jaw Crusher"
    category: ClassVar[NodeCategory] = NodeCategory.CRUSHER
    description: ClassVar[str] = "Щековая дробилка для первичного дробления"
    icon: ClassVar[str] = "🪨"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
                description="Питание дробилки (ROM)",
            )
        )
        self._add_port(
            NodePort(
                name="product",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
                description="Дроблёный продукт",
            )
        )

    def _define_parameters(self) -> None:
        self._add_parameter(
            NodeParameter(
                name="css",
                display_name="CSS (Closed Side Setting)",
                param_type=ParameterType.FLOAT,
                default=150.0,
                unit="mm",
                min_value=50.0,
                max_value=400.0,
                description="Закрытая щель дробилки",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="oss",
                display_name="OSS (Open Side Setting)",
                param_type=ParameterType.FLOAT,
                default=200.0,
                unit="mm",
                min_value=80.0,
                max_value=500.0,
                description="Открытая щель дробилки",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="capacity_tph",
                display_name="Номинальная производительность",
                param_type=ParameterType.FLOAT,
                default=1000.0,
                unit="t/h",
                min_value=100.0,
                max_value=5000.0,
                description="Максимальная производительность",
                group="design",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="power_kw",
                display_name="Установленная мощность",
                param_type=ParameterType.FLOAT,
                default=250.0,
                unit="kW",
                min_value=50.0,
                max_value=1000.0,
                description="Мощность привода",
                group="design",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт щековой дробилки."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material

        if not feed or not feed.psd:
            return NodeResult(
                success=False,
                errors=["Feed must have PSD defined"],
            )

        css = self.get_param("css")
        capacity = self.get_param("capacity_tph")
        power = self.get_param("power_kw")

        warnings = []

        # Проверка производительности
        if feed.solids_tph > capacity:
            warnings.append(
                f"Feed rate {feed.solids_tph:.0f} t/h exceeds capacity {capacity:.0f} t/h"
            )

        # Дробление
        product_psd = apply_css_crushing(feed.psd, css_mm=css)

        # Создаём выходной материал
        product_material = Material(
            name=f"{feed.name or 'Feed'} Crushed",
            phase=MaterialPhase.SOLID,
            solids_tph=feed.solids_tph,
            water_tph=feed.water_tph,
            psd=product_psd,
            quality=feed.quality,
        )

        # Выходной поток
        product_stream = Stream(
            name=f"{self.name} Product",
            stream_type=StreamType.SOLIDS,
            material=product_material,
        )

        # KPI
        feed_p80 = feed.psd.p80 or 0
        product_p80 = product_psd.p80 or 0
        reduction_ratio = feed_p80 / product_p80 if product_p80 > 0 else 0

        # Удельный расход энергии (упрощённо)
        specific_energy = power / feed.solids_tph if feed.solids_tph > 0 else 0

        return NodeResult(
            success=True,
            outputs={"product": product_stream},
            kpis={
                "feed_p80_mm": feed_p80,
                "product_p80_mm": product_p80,
                "reduction_ratio": reduction_ratio,
                "specific_energy_kwh_t": specific_energy,
            },
            warnings=warnings,
            power_kw=power,
            throughput_tph=feed.solids_tph,
        )


# ============================================================
# Cone Crusher
# ============================================================


@NodeRegistry.register
class ConeCrusher(BaseNode):
    """
    Конусная дробилка.

    Вторичное/третичное дробление.
    Типичные размеры: вход 100-300 мм, выход 20-50 мм.
    """

    node_type: ClassVar[str] = "cone_crusher"
    display_name: ClassVar[str] = "Cone Crusher"
    category: ClassVar[NodeCategory] = NodeCategory.CRUSHER
    description: ClassVar[str] = "Конусная дробилка для вторичного дробления"
    icon: ClassVar[str] = "🔷"

    def _define_ports(self) -> None:
        self._add_port(
            NodePort(
                name="feed",
                direction=PortDirection.INPUT,
                port_type=PortType.FEED,
                required=True,
                description="Питание дробилки",
            )
        )
        self._add_port(
            NodePort(
                name="product",
                direction=PortDirection.OUTPUT,
                port_type=PortType.PRODUCT,
                required=True,
                description="Дроблёный продукт",
            )
        )

    def _define_parameters(self) -> None:
        self._add_parameter(
            NodeParameter(
                name="css",
                display_name="CSS (Closed Side Setting)",
                param_type=ParameterType.FLOAT,
                default=25.0,
                unit="mm",
                min_value=10.0,
                max_value=100.0,
                description="Закрытая щель дробилки",
                group="operating",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="eccentric_throw",
                display_name="Эксцентриситет",
                param_type=ParameterType.FLOAT,
                default=20.0,
                unit="mm",
                min_value=10.0,
                max_value=50.0,
                description="Ход эксцентрика",
                group="design",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="capacity_tph",
                display_name="Номинальная производительность",
                param_type=ParameterType.FLOAT,
                default=500.0,
                unit="t/h",
                min_value=50.0,
                max_value=2000.0,
                description="Максимальная производительность",
                group="design",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="power_kw",
                display_name="Установленная мощность",
                param_type=ParameterType.FLOAT,
                default=200.0,
                unit="kW",
                min_value=30.0,
                max_value=600.0,
                description="Мощность привода",
                group="design",
            )
        )
        self._add_parameter(
            NodeParameter(
                name="liner_wear_pct",
                display_name="Износ футеровки",
                param_type=ParameterType.FLOAT,
                default=0.0,
                unit="%",
                min_value=0.0,
                max_value=100.0,
                description="Степень износа футеровки",
                group="condition",
            )
        )

    def calculate(self, inputs: Dict[str, Stream]) -> NodeResult:
        """Расчёт конусной дробилки."""
        errors = self.validate_inputs(inputs)
        if errors:
            return NodeResult(success=False, errors=errors)

        feed_stream = inputs["feed"]
        feed = feed_stream.material

        if not feed or not feed.psd:
            return NodeResult(
                success=False,
                errors=["Feed must have PSD defined"],
            )

        css = self.get_param("css")
        capacity = self.get_param("capacity_tph")
        power = self.get_param("power_kw")
        liner_wear = self.get_param("liner_wear_pct")

        warnings = []

        # Корректировка CSS на износ (увеличивается)
        effective_css = css * (1 + liner_wear / 200)

        # Проверка производительности
        if feed.solids_tph > capacity:
            warnings.append(
                f"Feed rate {feed.solids_tph:.0f} t/h exceeds capacity {capacity:.0f} t/h"
            )

        # Предупреждение о крупном питании
        if feed.psd.p80 and feed.psd.p80 > css * 4:
            warnings.append(
                f"Feed P80 ({feed.psd.p80:.1f} mm) is too coarse for CSS ({css:.1f} mm)"
            )

        # Дробление с более высоким коэффициентом для конуса
        product_psd = apply_css_crushing(feed.psd, css_mm=effective_css, reduction_ratio=4.0)

        # Создаём выходной материал
        product_material = Material(
            name=f"{feed.name or 'Feed'} Crushed",
            phase=MaterialPhase.SOLID,
            solids_tph=feed.solids_tph,
            water_tph=feed.water_tph,
            psd=product_psd,
            quality=feed.quality,
        )

        product_stream = Stream(
            name=f"{self.name} Product",
            stream_type=StreamType.SOLIDS,
            material=product_material,
        )

        # KPI
        feed_p80 = feed.psd.p80 or 0
        product_p80 = product_psd.p80 or 0
        reduction_ratio = feed_p80 / product_p80 if product_p80 > 0 else 0
        specific_energy = power / feed.solids_tph if feed.solids_tph > 0 else 0

        return NodeResult(
            success=True,
            outputs={"product": product_stream},
            kpis={
                "feed_p80_mm": feed_p80,
                "product_p80_mm": product_p80,
                "reduction_ratio": reduction_ratio,
                "specific_energy_kwh_t": specific_energy,
                "effective_css_mm": effective_css,
            },
            warnings=warnings,
            power_kw=power,
            throughput_tph=feed.solids_tph,
        )


# ============================================================
# Export
# ============================================================

__all__ = [
    "CrusherType",
    "apply_css_crushing",
    "JawCrusher",
    "ConeCrusher",
]
