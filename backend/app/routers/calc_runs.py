import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.routers.auth import get_current_user_optional
from app.schemas.calc_run import (
    CalcRunBaselineComparison,
    CalcRunCompareResponse,
    CalcRunComparisonItem,
    CalcRunCompareWithBaselineItem,
    CalcRunCompareWithBaselineResponse,
    CalcRunDelta,
    CalcRunListItem,
    CalcRunListResponse,
    CalcRunRead,
)
from app.schemas.calc_io import CalcInput, CalcResultSummary
from app.schemas.grind_mvp import GrindMvpResult
from app.services.calc_service import get_calc_scenario_or_404, get_flowsheet_version_or_404

router = APIRouter(prefix="/api/calc-runs", tags=["calc-runs"])


def _to_comparison_item(run: models.CalcRun) -> CalcRunComparisonItem:
    input_model = CalcInput.model_validate(run.input_json)
    result_model = CalcResultSummary.model_validate(run.result_json) if run.result_json is not None else None
    return CalcRunComparisonItem(
        id=run.id,
        scenario_id=run.scenario_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        input=input_model,
        result=result_model,
    )


def _compute_deltas(baseline: CalcRunComparisonItem, run_item: CalcRunComparisonItem) -> CalcRunDelta:
    if baseline.result is None or run_item.result is None:
        return CalcRunDelta()

    def pct_delta(b_value: float | None, r_value: float | None) -> Optional[float]:
        if b_value is None or r_value is None or b_value == 0:
            return None
        return (r_value - b_value) / b_value * 100.0

    b_res = baseline.result
    r_res = run_item.result
    throughput_delta_abs = r_res.throughput_tph - b_res.throughput_tph if r_res.throughput_tph is not None else None
    specific_energy_delta_abs = (
        r_res.specific_energy_kwh_per_t - b_res.specific_energy_kwh_per_t
        if r_res.specific_energy_kwh_per_t is not None
        else None
    )
    p80_out_delta_abs = r_res.p80_out_microns - b_res.p80_out_microns if r_res.p80_out_microns is not None else None

    return CalcRunDelta(
        throughput_delta_abs=throughput_delta_abs,
        throughput_delta_pct=pct_delta(b_res.throughput_tph, r_res.throughput_tph),
        specific_energy_delta_abs=specific_energy_delta_abs,
        specific_energy_delta_pct=pct_delta(b_res.specific_energy_kwh_per_t, r_res.specific_energy_kwh_per_t),
        p80_out_delta_abs=p80_out_delta_abs,
        p80_out_delta_pct=pct_delta(b_res.p80_out_microns, r_res.p80_out_microns),
    )


def _safe_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


def _is_baseline_run(run: models.CalcRun) -> bool:
    scenario = getattr(run, "scenario", None)
    return bool(getattr(scenario, "is_baseline", False)) if scenario is not None else False


def _target_flowsheet_version_id(run: models.CalcRun) -> uuid.UUID | None:
    if isinstance(run.input_json, dict):
        raw = run.input_json.get("flowsheet_version_id")
        parsed = _safe_uuid(raw) if raw else None
        if parsed:
            return parsed
    return getattr(run, "flowsheet_version_id", None)


def _clear_baseline_flags(db: Session, flowsheet_version_id: uuid.UUID) -> None:
    db.query(models.CalcRun).filter(models.CalcRun.flowsheet_version_id == flowsheet_version_id).update(
        {models.CalcRun.baseline_run_id: None}, synchronize_session=False
    )
    if hasattr(models, "CalcScenario"):
        db.query(models.CalcScenario).filter(models.CalcScenario.flowsheet_version_id == flowsheet_version_id).update(
            {models.CalcScenario.is_baseline: False}, synchronize_session=False
        )


def _find_baseline_run(db: Session, run: models.CalcRun) -> models.CalcRun | None:
    target_version_id = _target_flowsheet_version_id(run)
    if target_version_id is None:
        return None

    if getattr(run, "baseline_run_id", None):
        baseline = db.get(models.CalcRun, run.baseline_run_id)
        if baseline and _target_flowsheet_version_id(baseline) == target_version_id:
            return baseline

    baseline_scenario = (
        db.query(models.CalcScenario)
        .filter(
            models.CalcScenario.flowsheet_version_id == target_version_id,
            models.CalcScenario.is_baseline.is_(True),
        )
        .first()
        if hasattr(models, "CalcScenario")
        else None
    )
    if baseline_scenario:
        scenario_run = (
            db.query(models.CalcRun)
            .filter(
                models.CalcRun.scenario_id == baseline_scenario.id,
                models.CalcRun.status == "success",
            )
            .order_by(models.CalcRun.started_at.desc().nullslast())
            .first()
        )
        if scenario_run:
            return scenario_run

    baseline_self = (
        db.query(models.CalcRun)
        .filter(
            models.CalcRun.flowsheet_version_id == target_version_id,
            models.CalcRun.baseline_run_id == models.CalcRun.id,
        )
        .order_by(models.CalcRun.started_at.desc().nullslast())
        .first()
    )
    if baseline_self:
        return baseline_self

    return None


@router.get(
    "/by-flowsheet-version/{flowsheet_version_id}",
    response_model=CalcRunListResponse,
)
def list_calc_runs(
    flowsheet_version_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Optional status filter"),
    scenario_id: Optional[uuid.UUID] = Query(None, description="Filter by scenario id"),
    scenario_query: Optional[str] = Query(None, description="Substring to match in scenario_name"),
    started_from: Optional[datetime] = Query(None, description="Lower bound for started_at (inclusive)"),
    started_to: Optional[datetime] = Query(None, description="Upper bound for started_at (inclusive)"),
    db: Session = Depends(get_db),
) -> CalcRunListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcRun).filter(models.CalcRun.flowsheet_version_id == flowsheet_version_id)
    if status:
        query = query.filter(models.CalcRun.status == status)
    if scenario_id:
        query = query.filter(models.CalcRun.scenario_id == scenario_id)
    if scenario_query:
        query = query.filter(models.CalcRun.scenario_name.ilike(f"%{scenario_query}%"))
    if started_from:
        query = query.filter(models.CalcRun.started_at >= started_from)
    if started_to:
        query = query.filter(models.CalcRun.started_at <= started_to)

    total = query.with_entities(func.count()).scalar() or 0

    runs = (
        query.order_by(models.CalcRun.started_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[CalcRunListItem] = []
    for run in runs:
        run.is_baseline = _is_baseline_run(run)
        items.append(CalcRunListItem.model_validate(run, from_attributes=True))
    return CalcRunListResponse(items=items, total=total)


@router.get(
    "/latest/by-scenario/{scenario_id}",
    response_model=CalcRunRead,
)
def get_latest_calc_run_by_scenario(
    scenario_id: uuid.UUID,
    status: Optional[str] = Query("success", description="Optional status filter, default 'success'"),
    db: Session = Depends(get_db),
) -> CalcRunRead:
    get_calc_scenario_or_404(db, scenario_id)

    query = db.query(models.CalcRun).filter(models.CalcRun.scenario_id == scenario_id)
    if status is not None:
        query = query.filter(models.CalcRun.status == status)

    calc_run = query.order_by(models.CalcRun.started_at.desc().nullslast()).limit(1).first()
    if calc_run is None:
        raise HTTPException(status_code=404, detail=f"No calc runs found for scenario {scenario_id}")

    calc_run.is_baseline = _is_baseline_run(calc_run)
    return CalcRunRead.model_validate(calc_run, from_attributes=True)


@router.get("/compare", response_model=CalcRunCompareResponse)
def compare_calc_runs(
    run_ids: Optional[list[uuid.UUID]] = Query(default=None),
    only_success: bool = Query(True, description="Whether to include only successful runs"),
    db: Session = Depends(get_db),
) -> CalcRunCompareResponse:
    if not run_ids:
        raise HTTPException(status_code=400, detail="run_ids query parameter is required")

    query = db.query(models.CalcRun).filter(models.CalcRun.id.in_(run_ids))
    if only_success:
        query = query.filter(models.CalcRun.status == "success")

    runs = query.all()
    if not runs:
        raise HTTPException(status_code=404, detail="No calc runs found for provided ids")

    run_map = {run.id: run for run in runs}
    ordered_runs = [run_map[run_id] for run_id in run_ids if run_id in run_map]
    items: list[CalcRunComparisonItem] = []
    for run in ordered_runs:
        input_model = CalcInput.model_validate(run.input_json)
        result_model = CalcResultSummary.model_validate(run.result_json) if run.result_json is not None else None
        items.append(
            CalcRunComparisonItem(
                id=run.id,
                scenario_id=run.scenario_id,
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                input=input_model,
                result=result_model,
            )
        )

    return CalcRunCompareResponse(items=items, total=len(items))


@router.get("/compare-with-baseline", response_model=CalcRunCompareWithBaselineResponse)
def compare_calc_runs_with_baseline(
    baseline_run_id: uuid.UUID = Query(..., description="Baseline calc run id"),
    run_ids: Optional[list[uuid.UUID]] = Query(default=None),
    only_success: bool = Query(True, description="Whether to include only successful runs"),
    db: Session = Depends(get_db),
) -> CalcRunCompareWithBaselineResponse:
    if not run_ids:
        raise HTTPException(status_code=400, detail="run_ids query parameter is required")

    baseline_run = db.get(models.CalcRun, baseline_run_id)
    if baseline_run is None:
        raise HTTPException(status_code=404, detail="Baseline calc run not found")
    if only_success and baseline_run.status != "success":
        raise HTTPException(status_code=400, detail="Baseline calc run must have status 'success'")

    query = db.query(models.CalcRun).filter(models.CalcRun.id.in_(run_ids))
    if only_success:
        query = query.filter(models.CalcRun.status == "success")

    runs = query.all()
    if not runs:
        raise HTTPException(status_code=404, detail="No calc runs found for provided ids")

    for run in runs:
        if run.flowsheet_version_id != baseline_run.flowsheet_version_id:
            raise HTTPException(
                status_code=400,
                detail="All runs must belong to the same flowsheet version as baseline",
            )

    baseline_item = _to_comparison_item(baseline_run)
    run_map = {run.id: run for run in runs}
    ordered_runs = [run_map[rid] for rid in run_ids if rid in run_map]

    items: list[CalcRunCompareWithBaselineItem] = []
    for run in ordered_runs:
        run_item = _to_comparison_item(run)
        deltas = _compute_deltas(baseline_item, run_item)
        items.append(CalcRunCompareWithBaselineItem(run=run_item, deltas=deltas))

    return CalcRunCompareWithBaselineResponse(baseline=baseline_item, items=items, total=len(items))


@router.get(
    "/{calc_run_id}/baseline-comparison",
    response_model=CalcRunBaselineComparison,
)
def get_calc_run_baseline_comparison(
    calc_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_optional),
) -> CalcRunBaselineComparison:
    run = db.query(models.CalcRun).filter(models.CalcRun.id == calc_run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Calc run not found")

    target_version_id = _target_flowsheet_version_id(run)
    baseline_run = _find_baseline_run(db, run)

    if baseline_run is None or (target_version_id and _target_flowsheet_version_id(baseline_run) != target_version_id):
        raise HTTPException(status_code=404, detail="Baseline run not found")

    try:
        current_result = GrindMvpResult.model_validate(run.result_json)
        baseline_result = GrindMvpResult.model_validate(baseline_run.result_json)
    except Exception:
        raise HTTPException(status_code=404, detail="Baseline comparison data is not available")

    return CalcRunBaselineComparison.from_results(
        run_id=run.id,
        baseline_run_id=baseline_run.id,
        current_result=current_result,
        baseline_result=baseline_result,
    )


@router.post("/{run_id}/set-baseline", response_model=CalcRunRead)
def set_calc_run_baseline(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcRunRead:
    run = db.query(models.CalcRun).filter(models.CalcRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Calc run not found")

    target_version_id = _target_flowsheet_version_id(run)
    if target_version_id is None:
        raise HTTPException(status_code=400, detail="Calc run has no flowsheet version")

    _clear_baseline_flags(db, target_version_id)

    scenario = getattr(run, "scenario", None)
    if scenario is not None and hasattr(models.CalcScenario, "is_baseline"):
        scenario.is_baseline = True
        db.add(scenario)

    db.query(models.CalcRun).filter(models.CalcRun.flowsheet_version_id == target_version_id).update(
        {models.CalcRun.baseline_run_id: run.id}, synchronize_session=False
    )
    run.baseline_run_id = run.id

    db.commit()
    db.refresh(run)
    run.is_baseline = _is_baseline_run(run)
    return CalcRunRead.model_validate(run, from_attributes=True)
