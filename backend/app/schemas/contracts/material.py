"""
Material — Контракт для описания материала в технологическом потоке.

Материал содержит:
- Массовый расход (tph)
- Содержание твёрдого (% или т/ч)
- Плотность
- Гранулометрический состав (PSD)
- Качественные характеристики (химия, прочность)

Версия контракта: 1.0
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, model_validator

from .psd import PSD


class MaterialPhase(str, Enum):
    """Фаза материала."""

    SOLID = "solid"  # Твёрдое
    SLURRY = "slurry"  # Пульпа (твёрдое + вода)
    WATER = "water"  # Вода
    AIR = "air"  # Воздух (для классификаторов)


class MaterialComponent(BaseModel):
    """
    Компонент материала (для многокомпонентных смесей).

    Используется когда нужно отслеживать несколько потоков руды
    с разными характеристиками (блендинг).
    """

    component_id: str = Field(..., description="ID компонента (blast_id, ore_type)")
    name: Optional[str] = Field(None, description="Название компонента")

    # Массовая доля в смеси
    mass_fraction: Annotated[float, Field(ge=0, le=1, description="Массовая доля (0-1)")]

    # Характеристики компонента
    psd: Optional[PSD] = None
    quality: Optional["MaterialQuality"] = None

    model_config = {"frozen": True}


class MaterialQuality(BaseModel):
    """
    Качественные характеристики материала.

    Расширяемая структура для хранения химического состава,
    физических свойств, индексов измельчаемости.
    """

    contract_version: str = Field(default="1.0")

    # Химический состав (ключ = элемент/оксид, значение = %)
    chemistry: Dict[str, float] = Field(
        default_factory=dict, description="Химический состав: {'Cu': 0.5, 'Fe': 15.0, 'S': 2.1}"
    )

    # Индексы измельчаемости / твёрдости
    bond_work_index_kwh_t: Optional[float] = Field(
        None, description="Bond Work Index (BWi), кВт·ч/т"
    )
    abrasion_index_ai: Optional[float] = Field(None, description="Abrasion Index (Ai)")
    spi: Optional[float] = Field(None, description="SAG Power Index")
    a_axb: Optional[float] = Field(
        None, description="A×b — параметр измельчаемости (JK Drop Weight Test)"
    )
    ta: Optional[float] = Field(None, description="ta — параметр абразивности")

    # Плотность
    sg: Optional[float] = Field(
        None, ge=1.0, le=8.0, description="Specific Gravity (удельный вес), т/м³"
    )
    bulk_density_t_m3: Optional[float] = Field(None, description="Насыпная плотность, т/м³")

    # Влажность
    moisture_percent: Optional[float] = Field(None, ge=0, le=100, description="Влажность, %")

    # Произвольные расширения
    extra: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные параметры")


class Material(BaseModel):
    """
    Основной контракт материала.

    Представляет технологический поток материала с полным набором
    характеристик: расход, PSD, качество.

    Example:
        >>> material = Material(
        ...     name="SAG Feed",
        ...     phase=MaterialPhase.SOLID,
        ...     solids_tph=1500.0,
        ...     psd=PSD.from_cumulative(
        ...         sizes_mm=[25, 50, 75, 100, 150],
        ...         cum_passing=[10, 30, 55, 75, 95]
        ...     ),
        ...     quality=MaterialQuality(
        ...         bond_work_index_kwh_t=14.5,
        ...         sg=2.7,
        ...         chemistry={"Cu": 0.45, "Fe": 12.0}
        ...     )
        ... )
    """

    contract_version: str = Field(default="1.0", description="Версия контракта Material")

    # Идентификация
    id: Optional[UUID] = Field(None, description="UUID материала")
    name: Optional[str] = Field(None, description="Название потока")

    # Фаза
    phase: MaterialPhase = Field(default=MaterialPhase.SOLID)

    # === Массовые расходы ===
    solids_tph: Annotated[float, Field(ge=0, description="Расход твёрдого, т/ч")]
    water_tph: float = Field(default=0.0, ge=0, description="Расход воды, т/ч")

    # === Параметры пульпы (если phase=SLURRY) ===
    # Альтернативный способ задать воду — через % твёрдого
    solids_percent: Optional[Annotated[float, Field(gt=0, le=100)]] = Field(
        None, description="Содержание твёрдого в пульпе, % (альтернатива water_tph)"
    )
    slurry_sg: Optional[float] = Field(None, description="Плотность пульпы, т/м³")

    # === Гранулометрия ===
    psd: Optional[PSD] = Field(None, description="Гранулометрический состав")

    # === Качество ===
    quality: Optional[MaterialQuality] = Field(None, description="Качественные характеристики")

    # === Компоненты (для блендинга) ===
    components: List[MaterialComponent] = Field(
        default_factory=list, description="Компоненты смеси (для многокомпонентных потоков)"
    )

    # === Метаданные ===
    source_blast_id: Optional[str] = Field(None, description="ID взрывного блока")
    timestamp: Optional[str] = Field(None, description="ISO datetime")

    model_config = {"frozen": False}

    @model_validator(mode="after")
    def compute_slurry_params(self) -> "Material":
        """
        Если задан solids_percent, вычисляем water_tph.
        Если задан water_tph, вычисляем solids_percent.
        """
        if self.phase == MaterialPhase.SLURRY:
            if self.solids_percent is not None and self.water_tph == 0.0:
                # Вычисляем воду из % твёрдого
                # solids_percent = solids / (solids + water) * 100
                # water = solids * (100 - solids_percent) / solids_percent
                if self.solids_percent > 0:
                    water = self.solids_tph * (100 - self.solids_percent) / self.solids_percent
                    object.__setattr__(self, "water_tph", water)

            elif self.water_tph > 0 and self.solids_percent is None:
                # Вычисляем % твёрдого
                total = self.solids_tph + self.water_tph
                if total > 0:
                    pct = (self.solids_tph / total) * 100
                    object.__setattr__(self, "solids_percent", pct)

        return self

    @computed_field
    @property
    def total_tph(self) -> float:
        """Общий массовый расход (твёрдое + вода)."""
        return self.solids_tph + self.water_tph

    @computed_field
    @property
    def water_solids_ratio(self) -> Optional[float]:
        """Соотношение Ж:Т (вода к твёрдому)."""
        if self.solids_tph > 0:
            return self.water_tph / self.solids_tph
        return None

    @property
    def p80_mm(self) -> Optional[float]:
        """P80 материала, если есть PSD."""
        if self.psd:
            return self.psd.p80
        return None

    @property
    def density_t_m3(self) -> Optional[float]:
        """Плотность твёрдого из quality."""
        if self.quality and self.quality.sg:
            return self.quality.sg
        return None

    def blend_with(self, other: "Material", other_fraction: float = 0.5) -> "Material":
        """
        Смешивает два материала.

        Args:
            other: Другой материал для смешивания
            other_fraction: Доля другого материала (0-1)

        Returns:
            Новый смешанный Material
        """
        self_fraction = 1.0 - other_fraction

        new_solids = self.solids_tph * self_fraction + other.solids_tph * other_fraction
        new_water = self.water_tph * self_fraction + other.water_tph * other_fraction

        # TODO: Смешивание PSD требует более сложной логики
        # TODO: Смешивание качества — средневзвешенное

        return Material(
            name=f"Blend({self.name or 'A'}, {other.name or 'B'})",
            phase=self.phase,
            solids_tph=new_solids,
            water_tph=new_water,
            components=[
                MaterialComponent(
                    component_id=self.id.hex if self.id else "A",
                    name=self.name,
                    mass_fraction=self_fraction,
                    psd=self.psd,
                    quality=self.quality,
                ),
                MaterialComponent(
                    component_id=other.id.hex if other.id else "B",
                    name=other.name,
                    mass_fraction=other_fraction,
                    psd=other.psd,
                    quality=other.quality,
                ),
            ],
        )

    def with_psd(self, psd: PSD) -> "Material":
        """Возвращает копию с новым PSD."""
        return self.model_copy(update={"psd": psd})

    def with_quality(self, quality: MaterialQuality) -> "Material":
        """Возвращает копию с новым quality."""
        return self.model_copy(update={"quality": quality})
