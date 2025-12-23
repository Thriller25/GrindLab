import uuid

from app import models
from app.core.exceptions import raise_not_found
from app.db import get_db
from app.schemas import PaginatedResponse, UnitCreate, UnitRead, UnitUpdate
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[UnitRead])
def list_units(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(models.Unit)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{unit_id}", response_model=UnitRead)
def get_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Unit).get(unit_id)
    if not obj:
        raise_not_found("Unit", unit_id)
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
        raise_not_found("Unit", unit_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(unit_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Unit).get(unit_id)
    if not obj:
        raise_not_found("Unit", unit_id)
    obj.is_active = False
    db.commit()
    return None
