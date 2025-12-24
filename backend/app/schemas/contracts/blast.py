"""
Blast — Контракт для взрывного блока (блок руды из карьера).

Blast содержит:
- Идентификацию блока
- Геологические координаты
- PSD от взрыва
- Качественные характеристики
- Привязку к партии руды

Используется для прослеживаемости руды от карьера до переработки.

Версия контракта: 1.0
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .material import MaterialQuality
from .psd import PSD

if TYPE_CHECKING:
    from .material import Material


class BlastSource(str, Enum):
    """Источник данных о взрыве."""

    MINE_DISPATCH = "mine_dispatch"  # Диспетчерская карьера
    GEOLOGY = "geology"  # Геологическая модель
    MANUAL = "manual"  # Ручной ввод
    INKA = "inka"  # Система INKA
    IMPORT = "import"  # Импорт из файла


class BlastStatus(str, Enum):
    """Статус взрывного блока."""

    PLANNED = "planned"  # Запланирован
    BLASTED = "blasted"  # Взорван
    IN_TRANSIT = "in_transit"  # В пути
    STOCKPILED = "stockpiled"  # На складе
    PROCESSING = "processing"  # В переработке
    COMPLETED = "completed"  # Переработан


class GeoLocation(BaseModel):
    """Географические/геологические координаты блока."""

    pit: Optional[str] = Field(None, description="Название карьера")
    bench: Optional[str] = Field(None, description="Горизонт/уступ")
    x: Optional[float] = Field(None, description="X координата (м)")
    y: Optional[float] = Field(None, description="Y координата (м)")
    z: Optional[float] = Field(None, description="Z координата (высота, м)")
    zone: Optional[str] = Field(None, description="Зона/сектор")


class BlastBlock(BaseModel):
    """
    Отдельный блок внутри взрыва.

    Взрыв может состоять из нескольких блоков с разными характеристиками.
    """

    block_id: str = Field(..., description="ID блока")
    tonnage_t: Annotated[float, Field(gt=0, description="Тоннаж блока, т")]

    # Качество блока
    quality: Optional[MaterialQuality] = None
    ore_type: Optional[str] = Field(None, description="Тип руды")

    # Геология
    location: Optional[GeoLocation] = None


class Blast(BaseModel):
    """
    Взрывной блок (партия руды).

    Представляет партию руды от взрыва в карьере с полной характеристикой:
    PSD, качество, геология, прослеживаемость.

    Example:
        >>> blast = Blast(
        ...     blast_id="BL-2024-001",
        ...     name="Blast Zone A, 2024-01-15",
        ...     timestamp=datetime.now(),
        ...     total_tonnage_t=50000,
        ...     psd=PSD.from_cumulative(
        ...         sizes_mm=[50, 100, 200, 300, 500],
        ...         cum_passing=[5, 20, 50, 80, 98]
        ...     ),
        ...     quality=MaterialQuality(
        ...         chemistry={"Cu": 0.55, "Fe": 14.0},
        ...         bond_work_index_kwh_t=14.2,
        ...         sg=2.75
        ...     )
        ... )
    """

    contract_version: str = Field(default="1.0", description="Версия контракта Blast")

    # === Идентификация ===
    id: UUID = Field(default_factory=uuid4, description="UUID")
    blast_id: str = Field(..., description="Бизнес-ID взрыва (из карьера)")
    name: Optional[str] = Field(None, description="Название/описание")

    # === Временные метки ===
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Время взрыва/регистрации"
    )
    blasted_at: Optional[datetime] = Field(None, description="Дата взрыва")
    processed_at: Optional[datetime] = Field(None, description="Дата переработки")

    # === Статус ===
    status: BlastStatus = Field(default=BlastStatus.BLASTED)
    source: BlastSource = Field(default=BlastSource.MANUAL)

    # === Тоннаж ===
    total_tonnage_t: Annotated[float, Field(gt=0, description="Общий тоннаж взрыва, т")]
    remaining_tonnage_t: Optional[float] = Field(None, description="Остаток на складе, т")

    # === Гранулометрия ===
    psd: Optional[PSD] = Field(None, description="PSD после взрыва")
    fragmentation_model: Optional[str] = Field(
        None, description="Модель фрагментации (Kuz-Ram, Swebrec, etc.)"
    )

    # === Качество ===
    quality: Optional[MaterialQuality] = Field(None, description="Качественные характеристики")
    ore_type: Optional[str] = Field(None, description="Тип руды")

    # === Геология ===
    location: Optional[GeoLocation] = Field(None, description="Местоположение")

    # === Блоки (если взрыв состоит из нескольких блоков) ===
    blocks: List[BlastBlock] = Field(default_factory=list, description="Блоки в составе взрыва")

    # === Прослеживаемость ===
    parent_blast_id: Optional[str] = Field(
        None, description="ID родительского взрыва (для split/merge)"
    )
    child_blast_ids: List[str] = Field(default_factory=list, description="ID дочерних взрывов")

    # === Метаданные ===
    tags: List[str] = Field(default_factory=list, description="Теги для фильтрации")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные данные")

    model_config = {"frozen": False}

    @property
    def p80_mm(self) -> Optional[float]:
        """P80 взрыва."""
        if self.psd:
            return self.psd.p80
        return None

    @property
    def is_composite(self) -> bool:
        """Является ли взрыв составным (несколько блоков)."""
        return len(self.blocks) > 1

    @property
    def average_grade(self) -> Optional[float]:
        """Среднее содержание основного металла (первый элемент в chemistry)."""
        if self.quality and self.quality.chemistry:
            # Возвращаем первое значение (обычно Cu)
            return next(iter(self.quality.chemistry.values()), None)
        return None

    def consume(self, tonnage_t: float) -> "Blast":
        """
        Потребить часть тоннажа (для прослеживаемости).

        Returns:
            Новый объект Blast с уменьшенным remaining_tonnage_t
        """
        current = self.remaining_tonnage_t or self.total_tonnage_t
        new_remaining = max(0, current - tonnage_t)

        new_status = self.status
        if new_remaining == 0:
            new_status = BlastStatus.COMPLETED
        elif new_remaining < current:
            new_status = BlastStatus.PROCESSING

        return self.model_copy(
            update={
                "remaining_tonnage_t": new_remaining,
                "status": new_status,
            }
        )

    def merge_with(self, other: "Blast") -> "Blast":
        """
        Объединяет два взрыва (блендинг).

        Returns:
            Новый Blast с объединёнными характеристиками
        """
        total = self.total_tonnage_t + other.total_tonnage_t
        self_fraction = self.total_tonnage_t / total
        other_fraction = other.total_tonnage_t / total

        # Среднее качество (упрощённо)
        merged_quality = None
        if self.quality and other.quality:
            merged_chemistry = {}
            all_keys = set(self.quality.chemistry.keys()) | set(other.quality.chemistry.keys())
            for key in all_keys:
                v1 = self.quality.chemistry.get(key, 0)
                v2 = other.quality.chemistry.get(key, 0)
                merged_chemistry[key] = v1 * self_fraction + v2 * other_fraction

            merged_quality = MaterialQuality(
                chemistry=merged_chemistry,
                bond_work_index_kwh_t=(
                    (
                        (self.quality.bond_work_index_kwh_t or 0) * self_fraction
                        + (other.quality.bond_work_index_kwh_t or 0) * other_fraction
                    )
                    if (self.quality.bond_work_index_kwh_t or other.quality.bond_work_index_kwh_t)
                    else None
                ),
                sg=(
                    (
                        (self.quality.sg or 0) * self_fraction
                        + (other.quality.sg or 0) * other_fraction
                    )
                    if (self.quality.sg or other.quality.sg)
                    else None
                ),
            )

        return Blast(
            blast_id=f"MERGE-{self.blast_id}-{other.blast_id}",
            name=f"Merged: {self.name or self.blast_id} + {other.name or other.blast_id}",
            total_tonnage_t=total,
            quality=merged_quality,
            parent_blast_id=None,  # Это новый объединённый взрыв
            tags=list(set(self.tags + other.tags)),
            metadata={
                "merged_from": [self.blast_id, other.blast_id],
                "merge_fractions": {
                    self.blast_id: self_fraction,
                    other.blast_id: other_fraction,
                },
            },
        )

    def to_material(self, rate_tph: float) -> "Material":
        """
        Конвертирует Blast в Material с заданным расходом.

        Args:
            rate_tph: Расход подачи, т/ч
        """
        from .material import Material, MaterialPhase

        return Material(
            name=f"Feed from {self.blast_id}",
            phase=MaterialPhase.SOLID,
            solids_tph=rate_tph,
            psd=self.psd,
            quality=self.quality,
            source_blast_id=self.blast_id,
        )

    def summary(self) -> str:
        """Краткое описание для логов."""
        grade_info = ""
        if self.quality and self.quality.chemistry:
            grades = ", ".join(f"{k}={v:.2f}%" for k, v in list(self.quality.chemistry.items())[:2])
            grade_info = f" [{grades}]"

        psd_info = f", P80={self.p80_mm:.1f}mm" if self.p80_mm else ""

        return f"{self.blast_id}: {self.total_tonnage_t:.0f}t{psd_info}{grade_info}"
