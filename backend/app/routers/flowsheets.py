import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import FlowsheetCreate, FlowsheetRead, FlowsheetUpdate

router = APIRouter()


@router.get("/", response_model=List[FlowsheetRead])
def list_flowsheets(db: Session = Depends(get_db)):
    return db.query(models.Flowsheet).all()


@router.get("/{flowsheet_id}", response_model=FlowsheetRead)
def get_flowsheet(flowsheet_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Flowsheet).get(flowsheet_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet not found")
    return obj


@router.post("/", response_model=FlowsheetRead, status_code=status.HTTP_201_CREATED)
def create_flowsheet(payload: FlowsheetCreate, db: Session = Depends(get_db)):
    obj = models.Flowsheet(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{flowsheet_id}", response_model=FlowsheetRead)
def update_flowsheet(flowsheet_id: uuid.UUID, payload: FlowsheetUpdate, db: Session = Depends(get_db)):
    obj = db.query(models.Flowsheet).get(flowsheet_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{flowsheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flowsheet(flowsheet_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Flowsheet).get(flowsheet_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet not found")
    obj.status = "ARCHIVED"
    db.commit()
    return None
