import logging
import uuid

from app import models
from app.core.rate_limit import limiter
from app.db import get_db
from app.routers.auth import get_current_user_optional
from app.schemas.calc_run import CalcRunCreate, CalcRunRead
from app.schemas.grind_mvp import (
    GrindMvpInput,
    GrindMvpRunDetail,
    GrindMvpRunResponse,
    GrindMvpRunSummary,
)
from app.services.calc_service import (
    CalculationError,
    get_flowsheet_version_or_404,
    run_flowsheet_calculation,
    run_flowsheet_calculation_by_scenario,
    run_grind_mvp_calculation,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/calc", tags=["calc"])
logger = logging.getLogger(__name__)


@router.post("/flowsheet-run", response_model=CalcRunRead)
@limiter.limit("10/minute")
def calc_flowsheet(
    request: Request,
    payload: CalcRunCreate,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcRunRead:
    """
    Run comminution flowsheet calculation and persist CalcRun metadata.

    Rate limit: 10 requests per minute
    """
    try:
        get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
        started_by_user_id = (
            current_user.id if current_user and isinstance(current_user.id, uuid.UUID) else None
        )
        payload_with_user = payload.model_copy(update={"started_by_user_id": started_by_user_id})
        return run_flowsheet_calculation(db=db, payload=payload_with_user)
    except CalculationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", "input_json"], "msg": str(exc), "type": "value_error"}],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Internal calculation error")
        raise HTTPException(status_code=500, detail="Internal calculation error")


def _is_grind_mvp_run(run: models.CalcRun) -> bool:
    data = run.input_json if isinstance(run.input_json, dict) else {}
    model_version = data.get("model_version") if isinstance(data, dict) else None
    return isinstance(model_version, str) and "grind_mvp" in model_version


def _grind_mvp_summary(run: models.CalcRun) -> GrindMvpRunSummary:
    input_json = run.input_json if isinstance(run.input_json, dict) else {}
    result_json = run.result_json if isinstance(run.result_json, dict) else {}
    kpi = result_json.get("kpi") if isinstance(result_json, dict) else {}
    return GrindMvpRunSummary(
        id=run.id,
        created_at=run.created_at,
        model_version=result_json.get("model_version")
        or input_json.get("model_version")
        or "grind_mvp_v1",
        plant_id=(
            str(input_json.get("plant_id")) if input_json.get("plant_id") is not None else None
        ),
        project_id=run.project_id,
        flowsheet_version_id=(
            str(run.flowsheet_version_id) if run.flowsheet_version_id is not None else None
        ),
        scenario_id=run.scenario_id,
        scenario_name=input_json.get("scenario_name"),
        comment=run.comment,
        throughput_tph=kpi.get("throughput_tph") if isinstance(kpi, dict) else None,
        product_p80_mm=kpi.get("product_p80_mm") if isinstance(kpi, dict) else None,
        specific_energy_kwhpt=(
            kpi.get("specific_energy_kwh_per_t") if isinstance(kpi, dict) else None
        ),
    )


def _grind_mvp_detail(run: models.CalcRun) -> GrindMvpRunDetail:
    input_json = run.input_json if isinstance(run.input_json, dict) else {}
    result_json = run.result_json if isinstance(run.result_json, dict) else {}
    return GrindMvpRunDetail(
        id=run.id,
        created_at=run.created_at,
        model_version=result_json.get("model_version")
        or input_json.get("model_version")
        or "grind_mvp_v1",
        plant_id=(
            str(input_json.get("plant_id")) if input_json.get("plant_id") is not None else None
        ),
        project_id=run.project_id,
        flowsheet_version_id=(
            str(run.flowsheet_version_id) if run.flowsheet_version_id is not None else None
        ),
        scenario_id=run.scenario_id,
        scenario_name=input_json.get("scenario_name"),
        comment=run.comment,
        input=GrindMvpInput.model_validate(input_json),
        result=result_json,
    )


@router.post("/grind-mvp-runs", response_model=GrindMvpRunResponse)
@limiter.limit("10/minute")
def create_grind_mvp_run(
    request: Request,
    payload: GrindMvpInput,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> GrindMvpRunResponse:
    """
    Create Grind MVP calculation run.

    Rate limit: 10 requests per minute
    """
    try:
        result = run_grind_mvp_calculation(db, payload)
        return GrindMvpRunResponse.model_validate(result)
    except CalculationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Internal calculation error")
        raise HTTPException(status_code=500, detail="Internal calculation error")


@router.get("/grind-mvp-runs", response_model=list[GrindMvpRunSummary])
def list_grind_mvp_runs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> list[GrindMvpRunSummary]:
    query = db.query(models.CalcRun).filter(models.CalcRun.status == "success")
    runs = query.order_by(models.CalcRun.created_at.desc()).offset(offset).limit(limit).all()
    return [_grind_mvp_summary(run) for run in runs if _is_grind_mvp_run(run)]


def _get_grind_run_or_404(db: Session, run_id: uuid.UUID) -> models.CalcRun:
    run = db.get(models.CalcRun, run_id)
    if run is None or not _is_grind_mvp_run(run):
        raise HTTPException(status_code=404, detail="Grind MVP run not found")
    return run


@router.get("/grind-mvp-runs/{run_id}", response_model=GrindMvpRunDetail)
def get_grind_mvp_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> GrindMvpRunDetail:
    run = _get_grind_run_or_404(db, run_id)
    return _grind_mvp_detail(run)


@router.put("/grind-mvp-runs/{run_id}/comment", response_model=GrindMvpRunDetail)
def update_grind_mvp_comment(
    run_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> GrindMvpRunDetail:
    run = _get_grind_run_or_404(db, run_id)
    comment = payload.get("comment") if isinstance(payload, dict) else None
    if comment is None:
        raise HTTPException(status_code=400, detail="comment is required")
    run.comment = comment
    db.add(run)
    db.commit()
    db.refresh(run)
    return _grind_mvp_detail(run)


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
        started_by_user_id = (
            current_user.id if current_user and isinstance(current_user.id, uuid.UUID) else None
        )
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
