from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.calc import FlowsheetCalcRequest, FlowsheetCalcResult
from app.services.calc_service import run_flowsheet_calc

router = APIRouter(prefix="/api/calc", tags=["calc"])


@router.post("/flowsheet-run", response_model=FlowsheetCalcResult)
def calc_flowsheet(payload: FlowsheetCalcRequest, db: Session = Depends(get_db)):
    """
    Run comminution flowsheet calculation.
    """
    return run_flowsheet_calc(db=db, payload=payload)
