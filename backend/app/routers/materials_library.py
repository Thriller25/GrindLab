"""
Materials Library Router — API для хранения и управления материалами.

F4.4: Назначение Material на feed

Эндпоинты:
- GET /api/materials — список всех материалов
- GET /api/materials/{id} — получить материал по ID
- POST /api/materials — создать материал
- DELETE /api/materials/{id} — удалить материал
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/materials", tags=["materials", "library"])


# ==================== In-Memory Storage (MVP) ====================
# TODO: Перенести в БД после стабилизации контрактов

_materials_storage: Dict[str, "MaterialRecord"] = {}


# ==================== Models ====================


class PSDPointCreate(BaseModel):
    """Точка PSD."""

    size_mm: float = Field(..., gt=0, description="Размер частиц, мм")
    cum_passing: float = Field(..., ge=0, le=100, description="Кумулятивный % прохода")


class MaterialCreate(BaseModel):
    """Создание материала."""

    name: str = Field(..., min_length=1, max_length=255, description="Название материала")
    source: Optional[str] = Field(None, description="Источник (месторождение, блок)")
    solids_tph: Optional[float] = Field(None, ge=0, description="Расход твёрдого, т/ч")
    p80_mm: Optional[float] = Field(None, gt=0, description="P80, мм")
    psd: Optional[List[PSDPointCreate]] = Field(None, description="Гранулометрия")
    bond_wi: Optional[float] = Field(None, gt=0, description="Bond Work Index, кВт·ч/т")
    sg: Optional[float] = Field(None, gt=0, description="Удельный вес, т/м³")


class MaterialRecord(BaseModel):
    """Полная запись материала."""

    id: str = Field(..., description="UUID материала")
    name: str
    source: Optional[str] = None
    solids_tph: Optional[float] = None
    p80_mm: Optional[float] = None
    psd: Optional[List[PSDPointCreate]] = None
    bond_wi: Optional[float] = None
    sg: Optional[float] = None
    created_at: str = Field(..., description="ISO timestamp")


class MaterialSummary(BaseModel):
    """Краткая информация о материале для списка."""

    id: str
    name: str
    source: Optional[str] = None
    solids_tph: Optional[float] = None
    p80_mm: Optional[float] = None
    psd_points_count: int = 0
    created_at: str


class MaterialListResponse(BaseModel):
    """Ответ со списком материалов."""

    items: List[MaterialSummary]
    total: int


# ==================== Demo Data ====================


def _seed_demo_materials() -> None:
    """Заполняет хранилище демо-данными."""
    if _materials_storage:
        return

    demo_materials = [
        MaterialCreate(
            name="ROM Feed - Block A",
            source="Block A, Level 340",
            solids_tph=1500,
            p80_mm=125,
            psd=[
                PSDPointCreate(size_mm=0.075, cum_passing=5),
                PSDPointCreate(size_mm=0.150, cum_passing=12),
                PSDPointCreate(size_mm=0.300, cum_passing=22),
                PSDPointCreate(size_mm=0.600, cum_passing=35),
                PSDPointCreate(size_mm=1.18, cum_passing=48),
                PSDPointCreate(size_mm=2.36, cum_passing=60),
                PSDPointCreate(size_mm=4.75, cum_passing=72),
                PSDPointCreate(size_mm=9.5, cum_passing=82),
                PSDPointCreate(size_mm=19.0, cum_passing=88),
                PSDPointCreate(size_mm=37.5, cum_passing=92),
                PSDPointCreate(size_mm=75.0, cum_passing=96),
                PSDPointCreate(size_mm=150.0, cum_passing=100),
            ],
            bond_wi=14.5,
            sg=2.75,
        ),
        MaterialCreate(
            name="SAG Feed - Blend",
            source="Stockpile Blend",
            solids_tph=2000,
            p80_mm=95,
            psd=[
                PSDPointCreate(size_mm=0.075, cum_passing=8),
                PSDPointCreate(size_mm=0.300, cum_passing=25),
                PSDPointCreate(size_mm=1.18, cum_passing=42),
                PSDPointCreate(size_mm=4.75, cum_passing=65),
                PSDPointCreate(size_mm=19.0, cum_passing=85),
                PSDPointCreate(size_mm=75.0, cum_passing=95),
                PSDPointCreate(size_mm=125.0, cum_passing=100),
            ],
            bond_wi=13.2,
            sg=2.68,
        ),
        MaterialCreate(
            name="Crusher Feed - Hard Ore",
            source="Block C, Level 380",
            solids_tph=800,
            p80_mm=180,
            bond_wi=18.5,
            sg=2.85,
        ),
    ]

    for mat in demo_materials:
        _create_material_internal(mat)


def _create_material_internal(data: MaterialCreate) -> MaterialRecord:
    """Внутренняя функция создания материала."""
    material_id = str(uuid.uuid4())
    record = MaterialRecord(
        id=material_id,
        name=data.name,
        source=data.source,
        solids_tph=data.solids_tph,
        p80_mm=data.p80_mm,
        psd=data.psd,
        bond_wi=data.bond_wi,
        sg=data.sg,
        created_at=datetime.utcnow().isoformat(),
    )
    _materials_storage[material_id] = record
    return record


# ==================== Endpoints ====================


@router.get("", response_model=MaterialListResponse)
async def list_materials() -> MaterialListResponse:
    """
    Получить список всех материалов.

    Возвращает краткую информацию для отображения в dropdown.
    """
    # Seed demo data on first call
    _seed_demo_materials()

    items = []
    for mat in _materials_storage.values():
        items.append(
            MaterialSummary(
                id=mat.id,
                name=mat.name,
                source=mat.source,
                solids_tph=mat.solids_tph,
                p80_mm=mat.p80_mm,
                psd_points_count=len(mat.psd) if mat.psd else 0,
                created_at=mat.created_at,
            )
        )

    # Sort by name
    items.sort(key=lambda x: x.name)

    return MaterialListResponse(items=items, total=len(items))


@router.get("/{material_id}", response_model=MaterialRecord)
async def get_material(material_id: str) -> MaterialRecord:
    """
    Получить полную информацию о материале по ID.
    """
    _seed_demo_materials()

    if material_id not in _materials_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material {material_id} not found",
        )

    return _materials_storage[material_id]


@router.post("", response_model=MaterialRecord, status_code=status.HTTP_201_CREATED)
async def create_material(data: MaterialCreate) -> MaterialRecord:
    """
    Создать новый материал.
    """
    return _create_material_internal(data)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(material_id: str) -> None:
    """
    Удалить материал по ID.
    """
    if material_id not in _materials_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material {material_id} not found",
        )

    del _materials_storage[material_id]
