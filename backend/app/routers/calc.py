import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.calc_run import CalcRunCreate, CalcRunRead
from app.services.calc_service import (
    CalculationError,
    get_flowsheet_version_or_404,
    run_flowsheet_calculation,
)

router = APIRouter(prefix="/api/calc", tags=["calc"])
logger = logging.getLogger(__name__)


@router.post("/flowsheet-run", response_model=CalcRunRead)
def calc_flowsheet(payload: CalcRunCreate, db: Session = Depends(get_db)) -> CalcRunRead:
    """
    Run comminution flowsheet calculation and persist CalcRun metadata.
    """
    try:
        get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
        return run_flowsheet_calculation(db=db, payload=payload)
    except CalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Internal calculation error")
        raise HTTPException(status_code=500, detail="Internal calculation error")
