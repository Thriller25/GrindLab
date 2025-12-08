from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.calc_run import CalcRunCreate, CalcRunRead
from app.services.calc_service import run_flowsheet_calculation

router = APIRouter(prefix="/api/calc", tags=["calc"])


@router.post("/flowsheet-run", response_model=CalcRunRead)
def calc_flowsheet(payload: CalcRunCreate, db: Session = Depends(get_db)) -> CalcRunRead:
    """
    Run comminution flowsheet calculation and persist CalcRun metadata.
    """
    return run_flowsheet_calculation(db=db, payload=payload)
