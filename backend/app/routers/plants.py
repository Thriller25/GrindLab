import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import PlantCreate, PlantRead, PlantUpdate

router = APIRouter()


@router.get("/", response_model=List[PlantRead])
def list_plants(db: Session = Depends(get_db)):
    return db.query(models.Plant).all()


@router.get("/{plant_id}", response_model=PlantRead)
def get_plant(plant_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Plant).get(plant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return obj


@router.post("/", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
def create_plant(payload: PlantCreate, db: Session = Depends(get_db)):
    obj = models.Plant(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{plant_id}", response_model=PlantRead)
def update_plant(plant_id: uuid.UUID, payload: PlantUpdate, db: Session = Depends(get_db)):
    obj = db.query(models.Plant).get(plant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plant(plant_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Plant).get(plant_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    obj.is_active = False
    db.commit()
    return None
