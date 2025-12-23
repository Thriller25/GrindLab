import uuid

from app import models
from app.core.exceptions import raise_not_found
from app.db import get_db
from app.schemas import PaginatedResponse, PlantCreate, PlantRead, PlantUpdate
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[PlantRead])
def list_plants(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(models.Plant)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{plant_id}", response_model=PlantRead)
def get_plant(plant_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.get(models.Plant, plant_id)
    if not obj:
        raise_not_found("Plant", plant_id)
    return obj


@router.post("/", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
def create_plant(payload: PlantCreate, db: Session = Depends(get_db)):
    obj = models.Plant(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{plant_id}", response_model=PlantRead)
def update_plant(plant_id: uuid.UUID, payload: PlantUpdate, db: Session = Depends(get_db)):
    obj = db.get(models.Plant, plant_id)
    if not obj:
        raise_not_found("Plant", plant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plant(plant_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.get(models.Plant, plant_id)
    if not obj:
        raise_not_found("Plant", plant_id)
    obj.is_active = False
    db.commit()
    return None
