"""
Stream — Поток между узлами технологической схемы.

Stream = узел-источник → узел-приёмник + Material.
Используется для связывания узлов (Node) в Flowsheet.

Версия контракта: 1.0
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .material import Material


class StreamType(str, Enum):
    """Тип потока."""

    SOLIDS = "solids"  # Сухой материал (конвейер)
    SLURRY = "slurry"  # Пульпа
    WATER = "water"  # Технологическая вода
    OVERFLOW = "overflow"  # Слив (классификатора)
    UNDERFLOW = "underflow"  # Пески (классификатора)
    FEED = "feed"  # Питание
    PRODUCT = "product"  # Продукт
    RECYCLE = "recycle"  # Рецикл (циркулирующая нагрузка)
    REJECT = "reject"  # Отвальный продукт


class StreamPort(str, Enum):
    """Стандартные порты узлов."""

    IN = "in"
    IN_1 = "in_1"
    IN_2 = "in_2"
    OUT = "out"
    OUT_1 = "out_1"
    OUT_2 = "out_2"
    OVERFLOW = "overflow"
    UNDERFLOW = "underflow"
    WATER_IN = "water_in"
    RECYCLE_IN = "recycle_in"


class Stream(BaseModel):
    """
    Поток между двумя узлами технологической схемы.

    Example:
        >>> stream = Stream(
        ...     name="SAG Discharge",
        ...     stream_type=StreamType.SLURRY,
        ...     source_node_id=sag_mill_id,
        ...     source_port=StreamPort.OUT,
        ...     target_node_id=screen_id,
        ...     target_port=StreamPort.IN,
        ...     material=Material(solids_tph=1500, water_tph=500)
        ... )
    """

    contract_version: str = Field(default="1.0", description="Версия контракта Stream")

    # Идентификация
    id: UUID = Field(default_factory=uuid4, description="UUID потока")
    name: Optional[str] = Field(None, description="Название потока")

    # Тип потока
    stream_type: StreamType = Field(default=StreamType.SLURRY)

    # === Топология ===
    # Опциональны для расчётов вне графа (unit tests, standalone calc)
    source_node_id: Optional[UUID] = Field(None, description="UUID узла-источника")
    source_port: str = Field(default="out", description="Порт выхода на источнике")

    target_node_id: Optional[UUID] = Field(None, description="UUID узла-приёмника")
    target_port: str = Field(default="in", description="Порт входа на приёмнике")

    # === Содержимое потока ===
    material: Optional[Material] = Field(None, description="Материал в потоке")

    # === Состояние расчёта ===
    is_calculated: bool = Field(default=False, description="Рассчитан ли поток")
    iteration: Optional[int] = Field(None, description="Номер итерации расчёта")

    # === Визуализация ===
    color: Optional[str] = Field(None, description="Цвет потока для UI (#RRGGBB)")

    model_config = {"frozen": False}

    @property
    def solids_tph(self) -> float:
        """Расход твёрдого в потоке."""
        if self.material:
            return self.material.solids_tph
        return 0.0

    @property
    def water_tph(self) -> float:
        """Расход воды в потоке."""
        if self.material:
            return self.material.water_tph
        return 0.0

    @property
    def total_tph(self) -> float:
        """Общий расход."""
        if self.material:
            return self.material.total_tph
        return 0.0

    @property
    def p80_mm(self) -> Optional[float]:
        """P80 материала в потоке."""
        if self.material and self.material.psd:
            return self.material.psd.p80
        return None

    def with_material(self, material: Material) -> "Stream":
        """Возвращает копию потока с новым материалом."""
        return self.model_copy(
            update={
                "material": material,
                "is_calculated": True,
            }
        )

    def reverse(self) -> "Stream":
        """
        Создаёт обратный поток (меняет source/target).
        Полезно для отладки.
        """
        return self.model_copy(
            update={
                "id": uuid4(),
                "source_node_id": self.target_node_id,
                "source_port": self.target_port,
                "target_node_id": self.source_node_id,
                "target_port": self.source_port,
            }
        )

    def summary(self) -> str:
        """Краткое описание потока для логов."""
        mat_info = ""
        if self.material:
            mat_info = f" [{self.material.solids_tph:.1f} tph"
            if self.p80_mm:
                mat_info += f", P80={self.p80_mm:.2f}mm"
            mat_info += "]"

        return f"{self.name or self.id.hex[:8]}: {self.stream_type.value}{mat_info}"

    def to_dict(self) -> dict:
        """Сериализация в dict для result_json."""
        result = {
            "id": str(self.id),
            "name": self.name,
            "stream_type": self.stream_type.value,
        }

        if self.material:
            material_dict = {
                "solids_tph": self.material.solids_tph,
                "water_tph": self.material.water_tph,
                "total_tph": self.material.total_tph,
            }

            if self.material.psd:
                psd_dict = {
                    "points": [
                        {"size_mm": p.size_mm, "cum_passing": p.cum_passing}
                        for p in self.material.psd.points
                    ],
                    "p80": self.material.psd.p80,
                    "p50": self.material.psd.p50,
                }
                if hasattr(self.material.psd, "p240_passing"):
                    psd_dict["p240_passing"] = self.material.psd.p240_passing
                material_dict["psd"] = psd_dict

            result["material"] = material_dict

        return result
