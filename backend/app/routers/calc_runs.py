import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID as _UUID

from app import models
from app.core.engine.executor import execute_flowsheet
from app.db import get_db
from app.routers.auth import get_current_user
from app.schemas.calc_io import CalcInput, CalcResultSummary
from app.schemas.calc_run import (
    BatchRunRequest,
    BatchRunResponse,
    CalcRunCompareResponse,
    CalcRunCompareWithBaselineItem,
    CalcRunCompareWithBaselineResponse,
    CalcRunComparisonItem,
    CalcRunDelta,
    CalcRunListItem,
    CalcRunListResponse,
    CalcRunRead,
)
from app.services.calc_service import get_calc_scenario_or_404, get_flowsheet_version_or_404
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/api/calc-runs", tags=["calc-runs"])


def _to_comparison_item(run: models.CalcRun) -> CalcRunComparisonItem:
    input_model = CalcInput.model_validate(run.input_json)
    result_model = (
        CalcResultSummary.model_validate(run.result_json) if run.result_json is not None else None
    )
    return CalcRunComparisonItem(
        id=run.id,
        scenario_id=run.scenario_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        input=input_model,
        result=result_model,
    )


def _compute_deltas(
    baseline: CalcRunComparisonItem, run_item: CalcRunComparisonItem
) -> CalcRunDelta:
    if baseline.result is None or run_item.result is None:
        return CalcRunDelta()

    def pct_delta(b_value: float | None, r_value: float | None) -> Optional[float]:
        if b_value is None or r_value is None or b_value == 0:
            return None
        return (r_value - b_value) / b_value * 100.0

    b_res = baseline.result
    r_res = run_item.result
    throughput_delta_abs = (
        r_res.throughput_tph - b_res.throughput_tph if r_res.throughput_tph is not None else None
    )
    specific_energy_delta_abs = (
        r_res.specific_energy_kwh_per_t - b_res.specific_energy_kwh_per_t
        if r_res.specific_energy_kwh_per_t is not None
        else None
    )
    p80_out_delta_abs = (
        r_res.p80_out_microns - b_res.p80_out_microns if r_res.p80_out_microns is not None else None
    )

    return CalcRunDelta(
        throughput_delta_abs=throughput_delta_abs,
        throughput_delta_pct=pct_delta(b_res.throughput_tph, r_res.throughput_tph),
        specific_energy_delta_abs=specific_energy_delta_abs,
        specific_energy_delta_pct=pct_delta(
            b_res.specific_energy_kwh_per_t, r_res.specific_energy_kwh_per_t
        ),
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
    started_from: Optional[datetime] = Query(
        None, description="Lower bound for started_at (inclusive)"
    ),
    started_to: Optional[datetime] = Query(
        None, description="Upper bound for started_at (inclusive)"
    ),
    db: Session = Depends(get_db),
) -> CalcRunListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcRun).filter(
        models.CalcRun.flowsheet_version_id == flowsheet_version_id
    )
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


@router.get("/my", response_model=CalcRunListResponse)
def get_my_calc_runs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Optional status filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CalcRunListResponse:
    # Start with base query
    base_query = db.query(models.CalcRun).filter(
        models.CalcRun.started_by_user_id == current_user.id
    )
    if status:
        base_query = base_query.filter(models.CalcRun.status == status)

    # Count before joinedload
    total = base_query.with_entities(func.count()).scalar() or 0

    # Apply joinedload
    query = base_query.options(
        joinedload(models.CalcRun.project),
        joinedload(models.CalcRun.scenario),
    )

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
    status: Optional[str] = Query(
        "success", description="Optional status filter, default 'success'"
    ),
    db: Session = Depends(get_db),
) -> CalcRunRead:
    get_calc_scenario_or_404(db, scenario_id)

    query = (
        db.query(models.CalcRun)
        .options(
            joinedload(models.CalcRun.project),
            joinedload(models.CalcRun.scenario),
        )
        .filter(models.CalcRun.scenario_id == scenario_id)
    )
    if status is not None:
        query = query.filter(models.CalcRun.status == status)

    calc_run = query.order_by(models.CalcRun.started_at.desc().nullslast()).limit(1).first()
    if calc_run is None:
        raise HTTPException(
            status_code=404, detail=f"No calc runs found for scenario {scenario_id}"
        )

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
        result_model = (
            CalcResultSummary.model_validate(run.result_json)
            if run.result_json is not None
            else None
        )
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
    "/{calc_run_id}",
    response_model=CalcRunRead,
    summary="Get calc run by id",
)
def get_calc_run_by_id(
    calc_run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CalcRunRead:
    calc_run = db.get(models.CalcRun, calc_run_id)
    if calc_run is None:
        raise HTTPException(status_code=404, detail="Calc run not found")
    return CalcRunRead.model_validate(calc_run, from_attributes=True)


# ============================================================================
# Run-and-save flowsheet simulation (F5.3)
# ============================================================================


class RunAndSaveRequest(BaseModel):
    flowsheet_version_id: _UUID = Field(..., description="Target flowsheet version id")
    project_id: Optional[int] = Field(None, description="Optional project id")
    scenario_id: Optional[_UUID] = Field(None, description="Optional scenario id")
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    nodes: list[dict]
    edges: list[dict]


@router.post(
    "/run-and-save",
    response_model=CalcRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Execute flowsheet and save result as calc run",
)
def run_and_save(
    body: RunAndSaveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> CalcRunRead:
    # Validate target flowsheet version exists
    get_flowsheet_version_or_404(db, body.flowsheet_version_id)

    started_at = datetime.utcnow()

    # Execute flowsheet via core engine
    result = execute_flowsheet(nodes_data=body.nodes, edges_data=body.edges)

    status_value = "success" if result.get("success") else "error"

    # Map KPI to dashboard-compatible fields
    global_kpi: dict = result.get("global_kpi") or {}
    kpi_for_dashboard: dict = {
        "throughput_tph": global_kpi.get("total_product_tph"),
        "product_p80_mm": global_kpi.get("product_p80_mm"),
        # keep legacy key expected by dashboards
        "specific_energy_kwh_per_t": global_kpi.get("specific_energy_kwh_t"),
        "circulating_load_percent": global_kpi.get("circulating_load_pct"),
    }

    result_json: dict = {
        "model_version": "flowsheet_engine_v1",
        "kpi": {k: v for k, v in kpi_for_dashboard.items() if v is not None},
        "global_kpi": global_kpi,
        "node_kpi": result.get("node_kpi") or {},
        "streams": result.get("streams") or {},
        "warnings": result.get("warnings") or [],
        "errors": result.get("errors") or [],
    }

    calc_run = models.CalcRun(
        flowsheet_version_id=body.flowsheet_version_id,
        scenario_id=body.scenario_id,
        scenario_name=body.scenario_name,
        project_id=body.project_id,
        comment=body.comment,
        started_by_user_id=None,  # TODO: align user ID types (Int vs UUID)
        status=status_value,
        started_at=started_at,
        finished_at=datetime.utcnow(),
        input_json={
            "model_version": "flowsheet_engine_v1",
            "nodes": body.nodes,
            "edges": body.edges,
        },
        result_json=result_json,
        error_message=(
            "; ".join(result.get("errors", []))
            if result.get("errors") and not result.get("success")
            else None
        ),
    )

    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)

    return CalcRunRead.model_validate(calc_run, from_attributes=True)


@router.post(
    "/batch-run",
    response_model=BatchRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def batch_run_scenarios(
    body: BatchRunRequest,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user),
) -> BatchRunResponse:
    """
    Run multiple scenarios for a flowsheet version.
    Executes scenarios sequentially.

    - **flowsheet_version_id**: Flowsheet version to use
    - **scenario_ids**: List of scenario IDs to execute
    - **project_id**: Optional project ID for tracking
    - **comment**: Optional comment for all runs
    """
    flowsheet_version = get_flowsheet_version_or_404(body.flowsheet_version_id, db)

    # Validate all scenarios exist
    scenarios = (
        db.query(models.CalcScenario)
        .filter(
            models.CalcScenario.flowsheet_version_id == body.flowsheet_version_id,
            models.CalcScenario.id.in_(body.scenario_ids),
        )
        .all()
    )

    if len(scenarios) != len(body.scenario_ids):
        missing_ids = set(body.scenario_ids) - {s.id for s in scenarios}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Some scenarios not found: {missing_ids}",
        )

    created_runs = []

    for scenario in scenarios:
        # Execute flowsheet
        result = execute_flowsheet(flowsheet_version.flowsheet_json, scenario.default_input_json)

        # Create CalcRun record
        calc_run = models.CalcRun(
            flowsheet_version_id=body.flowsheet_version_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            project_id=body.project_id,
            comment=body.comment or f"Batch run: {scenario.name}",
            started_by_user_id=current_user.id if current_user else None,
            status="success" if result.get("success") else "failed",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            input_json=scenario.default_input_json,
            result_json=CalcResultSummary.model_validate(result) if result.get("success") else None,
            error_message=(
                "; ".join(result.get("errors", []))
                if result.get("errors") and not result.get("success")
                else None
            ),
        )

        db.add(calc_run)
        db.flush()
        created_runs.append(CalcRunRead.model_validate(calc_run, from_attributes=True))

    db.commit()

    return BatchRunResponse(runs=created_runs, total=len(created_runs))
