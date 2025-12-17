import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas.calc_run import CalcRunCreate, CalcRunRead
from app.services.calc_service import (
    CalculationError,
    get_flowsheet_version_or_404,
    run_flowsheet_calculation,
    run_flowsheet_calculation_by_scenario,
)
from app.routers.auth import get_current_user_optional

router = APIRouter(prefix="/api/calc", tags=["calc"])
logger = logging.getLogger(__name__)


@router.post("/flowsheet-run", response_model=CalcRunRead)
def calc_flowsheet(
    payload: CalcRunCreate,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcRunRead:
    """
    Run comminution flowsheet calculation and persist CalcRun metadata.
    """
    try:
        get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
        started_by_user_id = current_user.id if current_user and isinstance(current_user.id, uuid.UUID) else None
        payload_with_user = payload.model_copy(
            update={"started_by_user_id": started_by_user_id}
        )
        return run_flowsheet_calculation(db=db, payload=payload_with_user)
    except CalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Internal calculation error")
        raise HTTPException(status_code=500, detail="Internal calculation error")


@router.post("/flowsheet-run/by-scenario/{scenario_id}", response_model=CalcRunRead)
def calc_flowsheet_by_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcRunRead:
    """
    Run calculation using default input stored on CalcScenario.
    """
    try:
        started_by_user_id = current_user.id if current_user and isinstance(current_user.id, uuid.UUID) else None
        return run_flowsheet_calculation_by_scenario(
            db=db,
            scenario_id=scenario_id,
            started_by_user_id=started_by_user_id,
        )
    except CalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Internal calculation error")
        raise HTTPException(status_code=500, detail="Internal calculation error")
