import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import CalcRunRead

router = APIRouter(prefix="/api/calc-runs", tags=["calc-runs"])


@router.get("/by-flowsheet-version/{flowsheet_version_id}", response_model=List[CalcRunRead])
def list_calc_runs(flowsheet_version_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.CalcRun)
        .filter(models.CalcRun.flowsheet_version_id == flowsheet_version_id)
        .order_by(models.CalcRun.created_at.desc())
        .all()
    )
