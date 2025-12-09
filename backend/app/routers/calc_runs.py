import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas.calc_run import (
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


@router.get(
    "/by-flowsheet-version/{flowsheet_version_id}",
    response_model=CalcRunListResponse,
)
def list_calc_runs(
    flowsheet_version_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    scenario_id: Optional[uuid.UUID] = None,
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

    items = [CalcRunListItem.model_validate(run, from_attributes=True) for run in runs]
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
