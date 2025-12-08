import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas.calc_run import CalcRunListItem, CalcRunListResponse
from app.services.calc_service import get_flowsheet_version_or_404

router = APIRouter(prefix="/api/calc-runs", tags=["calc-runs"])


@router.get(
    "/by-flowsheet-version/{flowsheet_version_id}",
    response_model=CalcRunListResponse,
)
def list_calc_runs(
    flowsheet_version_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    scenario_query: Optional[str] = Query(None, description="Substring to match in scenario_name"),
    started_from: Optional[datetime] = Query(None, description="Lower bound for started_at (inclusive)"),
    started_to: Optional[datetime] = Query(None, description="Upper bound for started_at (inclusive)"),
    db: Session = Depends(get_db),
) -> CalcRunListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcRun).filter(models.CalcRun.flowsheet_version_id == flowsheet_version_id)
    if status:
        query = query.filter(models.CalcRun.status == status)
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
