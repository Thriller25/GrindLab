import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import (
    FlowsheetVersionCreate,
    FlowsheetVersionRead,
    FlowsheetVersionUpdate,
    FlowsheetVersionOverviewResponse,
    ScenarioWithLatestRun,
    CalcRunRead,
    CalcScenarioListItem,
)
from app.services.calc_service import get_flowsheet_version_or_404

router = APIRouter()


@router.get("/", response_model=List[FlowsheetVersionRead])
def list_flowsheet_versions(db: Session = Depends(get_db)):
    return db.query(models.FlowsheetVersion).all()


@router.get("/{version_id}", response_model=FlowsheetVersionRead)
def get_flowsheet_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found")
    return obj


@router.post("/", response_model=FlowsheetVersionRead, status_code=status.HTTP_201_CREATED)
def create_flowsheet_version(payload: FlowsheetVersionCreate, db: Session = Depends(get_db)):
    obj = models.FlowsheetVersion(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{version_id}", response_model=FlowsheetVersionRead)
def update_flowsheet_version(version_id: uuid.UUID, payload: FlowsheetVersionUpdate, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flowsheet_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found")
    obj.is_active = False
    db.commit()
    return None


@router.get("/{version_id}/overview", response_model=FlowsheetVersionOverviewResponse)
def get_flowsheet_version_overview(
    version_id: uuid.UUID,
    status: Optional[str] = Query("success", description="Status filter for latest scenario runs"),
    db: Session = Depends(get_db),
) -> FlowsheetVersionOverviewResponse:
    flowsheet_version = get_flowsheet_version_or_404(db, version_id)

    scenarios = (
        db.query(models.CalcScenario)
        .filter(models.CalcScenario.flowsheet_version_id == version_id)
        .order_by(models.CalcScenario.created_at.desc())
        .all()
    )

    scenario_items: list[ScenarioWithLatestRun] = []
    for scenario in scenarios:
        run_query = db.query(models.CalcRun).filter(models.CalcRun.scenario_id == scenario.id)
        if status is not None:
            run_query = run_query.filter(models.CalcRun.status == status)

        latest_run = run_query.order_by(models.CalcRun.started_at.desc().nullslast()).limit(1).first()

        scenario_items.append(
            ScenarioWithLatestRun(
                scenario=CalcScenarioListItem.model_validate(scenario, from_attributes=True),
                latest_run=CalcRunRead.model_validate(latest_run, from_attributes=True) if latest_run else None,
            )
        )

    return FlowsheetVersionOverviewResponse(
        flowsheet_version=FlowsheetVersionRead.model_validate(flowsheet_version, from_attributes=True),
        scenarios=scenario_items,
    )
