import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import UnitCreate, UnitRead, UnitUpdate

router = APIRouter()


@router.get("/", response_model=List[UnitRead])
def list_units(db: Session = Depends(get_db)):
    return db.query(models.Unit).all()


@router.get("/{unit_id}", response_model=UnitRead)
def get_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Unit).get(unit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    return obj


@router.post("/", response_model=UnitRead, status_code=status.HTTP_201_CREATED)
def create_unit(payload: UnitCreate, db: Session = Depends(get_db)):
    obj = models.Unit(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{unit_id}", response_model=UnitRead)
def update_unit(unit_id: uuid.UUID, payload: UnitUpdate, db: Session = Depends(get_db)):
    obj = db.query(models.Unit).get(unit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Unit).get(unit_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    obj.is_active = False
    db.commit()
    return None
