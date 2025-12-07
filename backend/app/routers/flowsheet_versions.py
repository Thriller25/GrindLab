import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import (
    FlowsheetVersionCreate,
    FlowsheetVersionRead,
    FlowsheetVersionUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[FlowsheetVersionRead])
def list_flowsheet_versions(db: Session = Depends(get_db)):
    return db.query(models.FlowsheetVersion).all()


@router.get("/{version_id}", response_model=FlowsheetVersionRead)
def get_flowsheet_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found")
    return obj


@router.post("/", response_model=FlowsheetVersionRead, status_code=status.HTTP_201_CREATED)
def create_flowsheet_version(payload: FlowsheetVersionCreate, db: Session = Depends(get_db)):
    obj = models.FlowsheetVersion(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{version_id}", response_model=FlowsheetVersionRead)
def update_flowsheet_version(version_id: uuid.UUID, payload: FlowsheetVersionUpdate, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flowsheet_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found")
    obj.is_active = False
    db.commit()
    return None
