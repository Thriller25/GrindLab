"""
Unit Models — Модели оборудования для расчёта.

Каждый класс реализует calculate() для преобразования входных потоков в выходные.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .stream import Stream, StreamPSD


@dataclass
class UnitResult:
    """Результат расчёта узла."""

    outputs: dict[str, Stream] = field(default_factory=dict)  # port_id -> Stream
    kpi: dict[str, float] = field(default_factory=dict)
    converged: bool = True
    error: str | None = None


class UnitModel(ABC):
    """Базовый класс модели оборудования."""

    def __init__(self, node_id: str, node_type: str, params: dict[str, Any]):
        self.node_id = node_id
        self.node_type = node_type
        self.params = params

    @abstractmethod
    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        """
        Рассчитать выходные потоки на основе входных.

        Args:
            inputs: dict[port_id, Stream] — входные потоки

        Returns:
            UnitResult с выходными потоками и KPI
        """
        pass

    def get_param(self, name: str, default: Any = None) -> Any:
        return self.params.get(name, default)


class FeedUnit(UnitModel):
    """Узел питания — генерирует исходный поток."""

    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        tph = self.get_param("tph", 100.0)
        solids_pct = self.get_param("solids_pct", 100.0)
        f80_mm = self.get_param("f80_mm", 150.0)

        psd = StreamPSD.from_f80(f80_mm)

        output = Stream(
            id=f"{self.node_id}_out",
            mass_tph=tph,
            solids_pct=solids_pct,
            psd=psd,
            source_node_id=self.node_id,
            source_port="out",
        )

        # Расширенные KPI для питания
        kpi = {
            "feed_tph": tph,
            "f80_mm": f80_mm,
        }
        if psd.p50:
            kpi["f50_mm"] = psd.p50

        return UnitResult(
            outputs={"out": output},
            kpi=kpi,
        )


class ProductUnit(UnitModel):
    """Узел продукта — принимает конечный поток."""

    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        feed = inputs.get("in")
        if not feed:
            return UnitResult(error="No input stream")

        # Расширенные KPI для продукта
        kpi = {
            "product_tph": feed.mass_tph,
            "p80_mm": feed.p80_mm or 0.0,
            "solids_pct": feed.solids_pct,
        }

        # Добавляем PSD-метрики если есть PSD
        if feed.psd:
            kpi["p98_mm"] = feed.psd.p98 or 0.0
            kpi["p50_mm"] = feed.psd.p50 or 0.0
            kpi["p20_mm"] = feed.psd.p20 or 0.0
            kpi["passing_240_mesh_pct"] = feed.psd.get_passing_240_mesh()

        return UnitResult(
            outputs={},
            kpi=kpi,
        )


class CrusherUnit(UnitModel):
    """
    Модель дробилки (щековая, конусная).

    Использует упрощённую модель на основе CSS и степени дробления.
    P80_product ≈ CSS * 0.8
    """

    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        feed = inputs.get("feed")
        if not feed:
            return UnitResult(error="No feed stream")

        css = self.get_param("css", 100.0)  # мм
        reduction_ratio = self.get_param("reduction_ratio", 5.0)
        capacity_tph = self.get_param("capacity_tph", 500.0)

        # Проверка производительности
        if feed.mass_tph > capacity_tph * 1.1:
            return UnitResult(
                error=f"Feed {feed.mass_tph:.0f} t/h exceeds capacity {capacity_tph:.0f} t/h"
            )

        # Расчёт P80 продукта
        # P80_out = min(F80/reduction_ratio, CSS * 0.8)
        f80_in = feed.p80_mm or 150.0
        p80_theoretical = f80_in / reduction_ratio
        p80_css_limited = css * 0.8
        p80_out = max(min(p80_theoretical, p80_css_limited), css * 0.5)

        # Создаём новый PSD
        reduction_factor = f80_in / p80_out if p80_out > 0 else 1.0
        new_psd = (
            feed.psd.scale_by_factor(reduction_factor) if feed.psd else StreamPSD.from_f80(p80_out)
        )

        product = Stream(
            id=f"{self.node_id}_product",
            mass_tph=feed.mass_tph,  # Массовый баланс
            solids_pct=feed.solids_pct,
            psd=new_psd,
            source_node_id=self.node_id,
            source_port="product",
        )

        # Оценка энергопотребления (эмпирика)
        # E = Wi * (10/sqrt(P80) - 10/sqrt(F80)) * tph
        # Упрощённо: ~0.3 кВт*ч/т на каждый мм CSS
        specific_energy = 0.3 * (f80_in / css)
        power_kw = specific_energy * feed.mass_tph

        return UnitResult(
            outputs={"product": product},
            kpi={
                "f80_in_mm": f80_in,
                "p80_out_mm": p80_out,
                "reduction_ratio_actual": f80_in / p80_out if p80_out > 0 else 0,
                "throughput_tph": feed.mass_tph,
                "power_kw": round(power_kw, 1),
                "specific_energy_kwh_t": round(specific_energy, 2),
            },
        )


class MillUnit(UnitModel):
    """
    Модель мельницы (SAG, шаровая).

    Использует упрощённую Bond модель:
    W = Wi * (10/sqrt(P80) - 10/sqrt(F80))
    """

    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        feed = inputs.get("feed")
        if not feed:
            return UnitResult(error="No feed stream")

        power_kw = self.get_param("power_kw", 5000.0)
        # diameter_m = self.get_param("diameter_m", 5.0)  # TODO: use for capacity check

        # Bond Work Index (оценка для руды)
        wi = 15.0  # кВт*ч/т — типичное значение

        # Расчёт P80 по балансу энергии
        # W = power / tph = Wi * (10/sqrt(P80_um) - 10/sqrt(F80_um))
        f80_mm = feed.p80_mm or 10.0
        f80_um = f80_mm * 1000

        if feed.mass_tph <= 0:
            return UnitResult(error="Zero feed rate")

        specific_energy = power_kw / feed.mass_tph  # кВт*ч/т

        # Решаем уравнение Bond для P80
        # W = Wi * (10/sqrt(P80) - 10/sqrt(F80))
        # P80 = (Wi * 10 / (W + Wi*10/sqrt(F80)))^2
        term_f80 = wi * 10 / math.sqrt(f80_um)
        denominator = specific_energy + term_f80

        if denominator <= 0:
            p80_um = f80_um  # Нет измельчения
        else:
            p80_um = (wi * 10 / denominator) ** 2

        # Ограничения: P80 не может быть больше F80 и не меньше 20 мкм
        p80_um = max(20, min(p80_um, f80_um))
        p80_mm = p80_um / 1000

        # Масштабируем PSD
        reduction_factor = f80_mm / p80_mm if p80_mm > 0 else 1.0
        new_psd = (
            feed.psd.scale_by_factor(reduction_factor) if feed.psd else StreamPSD.from_f80(p80_mm)
        )

        # Добавляем воду для SAG/Ball mill (целевая плотность ~75% твёрдого)
        target_solids = 75.0 if self.node_type == "sag_mill" else 70.0
        output_solids = min(feed.solids_pct, target_solids)

        product = Stream(
            id=f"{self.node_id}_product",
            mass_tph=feed.mass_tph,
            solids_pct=output_solids,
            psd=new_psd,
            source_node_id=self.node_id,
            source_port="product",
        )

        return UnitResult(
            outputs={"product": product},
            kpi={
                "f80_mm": f80_mm,
                "p80_mm": round(p80_mm, 4),
                "power_kw": power_kw,
                "throughput_tph": feed.mass_tph,
                "specific_energy_kwh_t": round(specific_energy, 2),
                "reduction_ratio": round(f80_mm / p80_mm, 2) if p80_mm > 0 else 0,
            },
        )


class HydrocycloneUnit(UnitModel):
    """
    Модель гидроциклона.

    Разделяет поток на слив (overflow) и пески (underflow).
    Использует функцию разделения Плитта.
    """

    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        feed = inputs.get("feed")
        if not feed:
            return UnitResult(error="No feed stream")

        d50_um = self.get_param("d50_um", 75.0)
        sharpness = self.get_param("sharpness", 2.5)
        # num_cyclones = self.get_param("num_cyclones", 4)  # TODO: use for capacity

        d50_mm = d50_um / 1000

        # Расчёт разделения через функцию Плитта
        # E(d) = 1 - exp(-0.693*(d/d50)^sharpness)
        # Доля в underflow для частиц размера d

        if not feed.psd or not feed.psd.points:
            # Упрощённое разделение без PSD
            split_to_uf = 0.3  # 30% в пески
            overflow_mass = feed.mass_tph * (1 - split_to_uf)
            underflow_mass = feed.mass_tph * split_to_uf
        else:
            # Расчёт по классам крупности
            total_of_mass = 0.0
            total_uf_mass = 0.0

            prev_cum = 0.0
            for size_mm, cum_pass in feed.psd.points:
                # Доля класса
                class_fraction = (cum_pass - prev_cum) / 100.0
                class_mass = feed.mass_tph * class_fraction

                # Функция разделения Плитта
                # Частицы крупнее d50 идут в underflow
                if size_mm > 0:
                    eff = 1 - math.exp(-0.693 * (size_mm / d50_mm) ** sharpness)
                else:
                    eff = 0.0
                eff = max(0.0, min(1.0, eff))

                uf_mass = class_mass * eff
                of_mass = class_mass * (1 - eff)

                total_uf_mass += uf_mass
                total_of_mass += of_mass

                prev_cum = cum_pass

            total_mass = total_of_mass + total_uf_mass
            if total_mass > 0:
                overflow_mass = total_of_mass
                underflow_mass = total_uf_mass
            else:
                overflow_mass = feed.mass_tph * 0.7
                underflow_mass = feed.mass_tph * 0.3

        # Создаём PSD для потоков (упрощённо)
        # Overflow — более тонкий (P80 ≈ d50)
        # Underflow — более крупный (P80 ≈ 2*d50)
        overflow_psd = StreamPSD.from_f80(d50_mm * 0.8)
        underflow_psd = StreamPSD.from_f80(d50_mm * 2.5)

        # Плотность: слив разбавлен, пески сгущены
        of_solids = min(feed.solids_pct * 0.6, 40.0)
        uf_solids = min(feed.solids_pct * 1.2, 80.0)

        overflow = Stream(
            id=f"{self.node_id}_overflow",
            mass_tph=overflow_mass,
            solids_pct=of_solids,
            psd=overflow_psd,
            source_node_id=self.node_id,
            source_port="overflow",
        )

        underflow = Stream(
            id=f"{self.node_id}_underflow",
            mass_tph=underflow_mass,
            solids_pct=uf_solids,
            psd=underflow_psd,
            source_node_id=self.node_id,
            source_port="underflow",
        )

        return UnitResult(
            outputs={"overflow": overflow, "underflow": underflow},
            kpi={
                "feed_tph": feed.mass_tph,
                "overflow_tph": round(overflow_mass, 1),
                "underflow_tph": round(underflow_mass, 1),
                "overflow_p80_mm": overflow_psd.p80,
                "underflow_p80_mm": underflow_psd.p80,
                "split_to_uf_pct": (
                    round(100 * underflow_mass / feed.mass_tph, 1) if feed.mass_tph > 0 else 0
                ),
                "d50_um": d50_um,
            },
        )


class ScreenUnit(UnitModel):
    """
    Модель грохота (вибрационный, банановый).

    Разделяет на надрешётный (oversize) и подрешётный (undersize).
    """

    def calculate(self, inputs: dict[str, Stream]) -> UnitResult:
        feed = inputs.get("feed")
        if not feed:
            return UnitResult(error="No feed stream")

        aperture_mm = self.get_param("aperture_mm", 25.0)
        efficiency = self.get_param("efficiency", 90.0) / 100.0

        if not feed.psd or not feed.psd.points:
            # Без PSD — оценка по F80
            f80 = feed.p80_mm or 50.0
            if f80 > aperture_mm:
                oversize_frac = 0.6
            else:
                oversize_frac = 0.2
        else:
            # Расчёт по PSD
            # Подрешётный = cum_passing(aperture) * efficiency
            undersize_theoretical = feed.psd._interp_at_size(aperture_mm) / 100.0
            undersize_frac = undersize_theoretical * efficiency
            oversize_frac = 1 - undersize_frac

        oversize_mass = feed.mass_tph * oversize_frac
        undersize_mass = feed.mass_tph * (1 - oversize_frac)

        # PSD потоков
        oversize_psd = StreamPSD.from_f80(max(aperture_mm * 1.5, feed.p80_mm or aperture_mm * 1.5))
        undersize_psd = StreamPSD.from_f80(aperture_mm * 0.6)

        oversize = Stream(
            id=f"{self.node_id}_oversize",
            mass_tph=oversize_mass,
            solids_pct=feed.solids_pct,
            psd=oversize_psd,
            source_node_id=self.node_id,
            source_port="oversize",
        )

        undersize = Stream(
            id=f"{self.node_id}_undersize",
            mass_tph=undersize_mass,
            solids_pct=feed.solids_pct,
            psd=undersize_psd,
            source_node_id=self.node_id,
            source_port="undersize",
        )

        return UnitResult(
            outputs={"oversize": oversize, "undersize": undersize},
            kpi={
                "feed_tph": feed.mass_tph,
                "oversize_tph": round(oversize_mass, 1),
                "undersize_tph": round(undersize_mass, 1),
                "aperture_mm": aperture_mm,
                "efficiency_pct": efficiency * 100,
                "split_to_oversize_pct": round(100 * oversize_frac, 1),
            },
        )


def create_unit_model(node_id: str, node_type: str, params: dict[str, Any]) -> UnitModel:
    """Фабрика для создания моделей по типу узла."""
    models_map: dict[str, type[UnitModel]] = {
        "feed": FeedUnit,
        "product": ProductUnit,
        "jaw_crusher": CrusherUnit,
        "cone_crusher": CrusherUnit,
        "sag_mill": MillUnit,
        "ball_mill": MillUnit,
        "hydrocyclone": HydrocycloneUnit,
        "vib_screen": ScreenUnit,
        "banana_screen": ScreenUnit,
    }

    model_class = models_map.get(node_type)
    if not model_class:
        raise ValueError(f"Unknown node type: {node_type}")

    return model_class(node_id, node_type, params)
