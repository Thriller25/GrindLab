import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

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
    db: Session = Depends(get_db),
) -> CalcRunListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcRun).filter(models.CalcRun.flowsheet_version_id == flowsheet_version_id)
    if status:
        query = query.filter(models.CalcRun.status == status)

    total = query.with_entities(func.count()).scalar() or 0

    runs = (
        query.order_by(models.CalcRun.started_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [CalcRunListItem.model_validate(run, from_attributes=True) for run in runs]
    return CalcRunListResponse(items=items, total=total)
