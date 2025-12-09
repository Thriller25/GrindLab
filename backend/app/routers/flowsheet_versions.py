import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import (
    CalcRunRead,
    CalcScenarioListItem,
    CalcScenarioRead,
    FlowsheetVersionCloneRequest,
    FlowsheetVersionCloneResponse,
    FlowsheetVersionCreate,
    FlowsheetVersionOverviewResponse,
    FlowsheetVersionRead,
    FlowsheetVersionUpdate,
    ScenarioWithLatestRun,
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


@router.post("/{version_id}/clone", response_model=FlowsheetVersionCloneResponse, status_code=status.HTTP_201_CREATED)
def clone_flowsheet_version(
    version_id: uuid.UUID,
    payload: FlowsheetVersionCloneRequest,
    db: Session = Depends(get_db),
) -> FlowsheetVersionCloneResponse:
    source_version = get_flowsheet_version_or_404(db, version_id)
    new_label = payload.new_version_name or f"{source_version.version_label} (copy)"

    cloned_version = models.FlowsheetVersion(
        flowsheet_id=source_version.flowsheet_id,
        version_label=new_label,
        status=source_version.status,
        is_active=source_version.is_active,
        comment=source_version.comment,
        created_by=source_version.created_by,
    )
    db.add(cloned_version)
    db.commit()
    db.refresh(cloned_version)

    cloned_scenarios: list[CalcScenarioRead] = []
    if payload.clone_scenarios:
        source_scenarios = (
            db.query(models.CalcScenario)
            .filter(models.CalcScenario.flowsheet_version_id == version_id)
            .all()
        )
        for scenario in source_scenarios:
            cloned = models.CalcScenario(
                flowsheet_version_id=cloned_version.id,
                name=scenario.name,
                description=scenario.description,
                default_input_json=scenario.default_input_json,
                is_baseline=scenario.is_baseline,
            )
            db.add(cloned)
            cloned_scenarios.append(cloned)
        db.commit()
        for scenario in cloned_scenarios:
            db.refresh(scenario)

    return FlowsheetVersionCloneResponse(
        flowsheet_version=FlowsheetVersionRead.model_validate(cloned_version, from_attributes=True),
        scenarios=[CalcScenarioRead.model_validate(s, from_attributes=True) for s in cloned_scenarios],
    )


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
