import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import (
    CalcComparisonCreate,
    CalcComparisonDetailResponse,
    CalcComparisonListItem,
    CalcComparisonListResponse,
    CalcComparisonRead,
    CalcRunCompareResponse,
    CalcRunComparisonItem,
)
from app.schemas.calc_io import CalcInput, CalcResultSummary
from app.services.calc_service import get_flowsheet_version_or_404

router = APIRouter(prefix="/api/calc-comparisons", tags=["calc-comparisons"])


def _build_compare_response(
    db: Session, run_ids: list[uuid.UUID], only_success: bool = True
) -> CalcRunCompareResponse:
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


@router.post("/", response_model=CalcComparisonRead, status_code=status.HTTP_201_CREATED)
def create_calc_comparison(
    payload: CalcComparisonCreate, db: Session = Depends(get_db)
) -> CalcComparisonRead:
    if not payload.run_ids:
        raise HTTPException(status_code=400, detail="run_ids must be provided")

    get_flowsheet_version_or_404(db, payload.flowsheet_version_id)

    runs = (
        db.query(models.CalcRun)
        .filter(models.CalcRun.id.in_(payload.run_ids))
        .all()
    )
    if len(runs) != len(payload.run_ids):
        raise HTTPException(status_code=400, detail="Some run_ids were not found")

    for run in runs:
        if run.flowsheet_version_id != payload.flowsheet_version_id:
            raise HTTPException(
                status_code=400,
                detail=f"CalcRun {run.id} does not belong to flowsheet version {payload.flowsheet_version_id}",
            )

    comparison = models.CalcComparison(
        flowsheet_version_id=payload.flowsheet_version_id,
        name=payload.name,
        description=payload.description,
        run_ids_json=[str(rid) for rid in payload.run_ids],
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return CalcComparisonRead.model_validate(
        {
            "id": comparison.id,
            "flowsheet_version_id": comparison.flowsheet_version_id,
            "name": comparison.name,
            "description": comparison.description,
            "run_ids": [uuid.UUID(str(rid)) for rid in comparison.run_ids_json],
            "created_at": comparison.created_at,
            "updated_at": comparison.updated_at,
        }
    )


@router.get("/{comparison_id}", response_model=CalcComparisonDetailResponse)
def get_calc_comparison(
    comparison_id: uuid.UUID,
    only_success: bool = Query(True, description="Whether to include only successful runs"),
    db: Session = Depends(get_db),
) -> CalcComparisonDetailResponse:
    comparison = db.get(models.CalcComparison, comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="CalcComparison not found")

    run_ids = [uuid.UUID(str(rid)) for rid in (comparison.run_ids_json or [])]
    runs_response = (
        _build_compare_response(db, run_ids, only_success=only_success) if run_ids else CalcRunCompareResponse(items=[], total=0)
    )

    comparison_read = CalcComparisonRead.model_validate(
        {
            "id": comparison.id,
            "flowsheet_version_id": comparison.flowsheet_version_id,
            "name": comparison.name,
            "description": comparison.description,
            "run_ids": run_ids,
            "created_at": comparison.created_at,
            "updated_at": comparison.updated_at,
        }
    )

    return CalcComparisonDetailResponse(comparison=comparison_read, runs=runs_response)


@router.get(
    "/by-flowsheet-version/{flowsheet_version_id}",
    response_model=CalcComparisonListResponse,
)
def list_calc_comparisons(
    flowsheet_version_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> CalcComparisonListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcComparison).filter(models.CalcComparison.flowsheet_version_id == flowsheet_version_id)

    total = query.with_entities(func.count()).scalar() or 0
    comparisons = query.order_by(models.CalcComparison.created_at.desc()).offset(offset).limit(limit).all()
    items = [CalcComparisonListItem.model_validate(comp, from_attributes=True) for comp in comparisons]
    return CalcComparisonListResponse(items=items, total=total)


@router.delete("/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calc_comparison(comparison_id: uuid.UUID, db: Session = Depends(get_db)):
    comparison = db.get(models.CalcComparison, comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="CalcComparison not found")
    db.delete(comparison)
    db.commit()
    return None
