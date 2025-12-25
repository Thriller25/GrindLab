"""
Stream — Технологический поток между узлами.

Содержит массовый расход, PSD и свойства пульпы.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StreamPSD:
    """
    Particle Size Distribution — гранулометрический состав.

    Хранится как список точек (size_mm, cum_passing_pct).
    Сортирован по size_mm по возрастанию.
    """

    points: list[tuple[float, float]] = field(default_factory=list)

    def __post_init__(self):
        # Сортируем по размеру
        self.points = sorted(self.points, key=lambda p: p[0])

    @classmethod
    def from_f80(cls, f80_mm: float) -> "StreamPSD":
        """
        Создать синтетическое PSD на основе F80.
        Использует Rosin-Rammler приближение.
        """
        # Rosin-Rammler: P(x) = 100 * (1 - exp(-(x/x63.2)^n))
        # P80 => x63.2 ≈ F80 / 1.44 при n=1.0
        x63 = f80_mm / 1.44
        n = 1.0  # modulus

        # Генерируем точки от 0.01*F80 до 3*F80
        sizes = [
            f80_mm * mult for mult in [0.01, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0]
        ]
        points = []
        for size in sizes:
            cum_pass = 100.0 * (1.0 - math.exp(-((size / x63) ** n)))
            cum_pass = min(100.0, max(0.0, cum_pass))
            points.append((size, cum_pass))

        return cls(points=points)

    def get_pxx(self, target_pct: float) -> Optional[float]:
        """
        Интерполяция размера при заданном % прохождения.
        Логарифмическая интерполяция по размеру.
        """
        if not self.points:
            return None

        if target_pct <= self.points[0][1]:
            return self.points[0][0]
        if target_pct >= self.points[-1][1]:
            return self.points[-1][0]

        for i in range(len(self.points) - 1):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i + 1]

            if y1 <= target_pct <= y2:
                if y2 == y1:
                    return x1
                # Логарифмическая интерполяция по размеру
                if x1 <= 0 or x2 <= 0:
                    # Fallback to linear
                    ratio = (target_pct - y1) / (y2 - y1)
                    return x1 + ratio * (x2 - x1)

                log_x1, log_x2 = math.log(x1), math.log(x2)
                ratio = (target_pct - y1) / (y2 - y1)
                return math.exp(log_x1 + ratio * (log_x2 - log_x1))

        return self.points[-1][0]

    @property
    def p98(self) -> Optional[float]:
        """Размер при 98% прохождения (близко к макс. размеру)."""
        return self.get_pxx(98.0)

    @property
    def p80(self) -> Optional[float]:
        """Размер при 80% прохождения (стандартный P80)."""
        return self.get_pxx(80.0)

    @property
    def p50(self) -> Optional[float]:
        """Размер при 50% прохождения (медиана)."""
        return self.get_pxx(50.0)

    @property
    def p20(self) -> Optional[float]:
        """Размер при 20% прохождения."""
        return self.get_pxx(20.0)

    def passing_at_size(self, size_mm: float) -> float:
        """
        Получить % прохождения при заданном размере.

        Используется для расчёта P240 (240 mesh = 0.063 мм).

        Args:
            size_mm: Размер в мм

        Returns:
            Cumulative passing percent (0-100)
        """
        return self._interp_at_size(size_mm)

    def get_passing_240_mesh(self) -> float:
        """
        Получить % прохода через сито 240 mesh (63 мкм = 0.063 мм).

        Стандартный KPI для циркуляции в мельницах.
        """
        return self.passing_at_size(0.063)

    def scale_by_factor(self, factor: float) -> "StreamPSD":
        """Масштабировать PSD — уменьшить все размеры в factor раз."""
        new_points = [(size / factor, cum) for size, cum in self.points]
        return StreamPSD(points=new_points)

    def blend_with(self, other: "StreamPSD", my_fraction: float) -> "StreamPSD":
        """
        Смешать два PSD с заданной пропорцией.
        my_fraction — доля текущего PSD (0-1).
        """
        if not self.points or not other.points:
            return self if self.points else other

        # Объединяем все уникальные размеры
        all_sizes = sorted(set(p[0] for p in self.points) | set(p[0] for p in other.points))

        blended = []
        for size in all_sizes:
            my_cum = self._interp_at_size(size)
            other_cum = other._interp_at_size(size)
            blended_cum = my_fraction * my_cum + (1 - my_fraction) * other_cum
            blended.append((size, blended_cum))

        return StreamPSD(points=blended)

    def _interp_at_size(self, target_size: float) -> float:
        """Интерполировать cum_passing при заданном размере."""
        if not self.points:
            return 0.0

        if target_size <= self.points[0][0]:
            return self.points[0][1]
        if target_size >= self.points[-1][0]:
            return self.points[-1][1]

        for i in range(len(self.points) - 1):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i + 1]

            if x1 <= target_size <= x2:
                if x2 == x1:
                    return y1
                ratio = (target_size - x1) / (x2 - x1)
                return y1 + ratio * (y2 - y1)

        return self.points[-1][1]

    def to_dict(self) -> dict:
        return {
            "points": [{"size_mm": s, "cum_passing_pct": c} for s, c in self.points],
            "p98_mm": self.p98,
            "p80_mm": self.p80,
            "p50_mm": self.p50,
            "p20_mm": self.p20,
            "passing_240_mesh_pct": round(self.get_passing_240_mesh(), 1),
        }


@dataclass
class Stream:
    """
    Технологический поток.

    Содержит массу, PSD и свойства пульпы.
    """

    id: str
    mass_tph: float = 0.0
    solids_pct: float = 100.0  # % твёрдого
    psd: Optional[StreamPSD] = None
    source_node_id: Optional[str] = None
    source_port: Optional[str] = None
    target_node_id: Optional[str] = None
    target_port: Optional[str] = None

    @property
    def water_tph(self) -> float:
        """Расход воды в т/ч."""
        if self.solids_pct >= 100:
            return 0.0
        return self.mass_tph * (100 - self.solids_pct) / self.solids_pct

    @property
    def total_flow_tph(self) -> float:
        """Общий расход пульпы (твёрдое + вода)."""
        return self.mass_tph + self.water_tph

    @property
    def p80_mm(self) -> Optional[float]:
        return self.psd.p80 if self.psd else None

    def clone(self, new_id: str) -> "Stream":
        """Создать копию потока с новым ID."""
        return Stream(
            id=new_id,
            mass_tph=self.mass_tph,
            solids_pct=self.solids_pct,
            psd=StreamPSD(points=list(self.psd.points)) if self.psd else None,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mass_tph": round(self.mass_tph, 2),
            "solids_pct": round(self.solids_pct, 1),
            "water_tph": round(self.water_tph, 2),
            "total_flow_tph": round(self.total_flow_tph, 2),
            "p80_mm": round(self.p80_mm, 4) if self.p80_mm else None,
            "psd": self.psd.to_dict() if self.psd else None,
        }
