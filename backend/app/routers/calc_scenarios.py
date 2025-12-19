import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.routers.auth import get_current_user_optional
from app.schemas.calc_scenario import (
    CalcScenarioCreate,
    CalcScenarioListItem,
    CalcScenarioListResponse,
    CalcScenarioRead,
    CalcScenarioUpdate,
)
from app.services.calc_service import (
    CalculationError,
    get_calc_scenario_or_404,
    get_flowsheet_version_or_404,
    validate_input_json,
)

router = APIRouter(prefix="/api/calc-scenarios", tags=["calc-scenarios"])


def _get_project_or_404(db: Session, project_id: int) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _check_project_read_access(db: Session, project: models.Project, user: models.User | None) -> None:
    if project.owner_user_id is None:
        return
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if project.owner_user_id == user.id:
        return
    membership = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user.id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def _ensure_version_linked_to_project(db: Session, project_id: int, flowsheet_version_id: uuid.UUID) -> None:
    link_exists = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(
            models.ProjectFlowsheetVersion.project_id == project_id,
            models.ProjectFlowsheetVersion.flowsheet_version_id == flowsheet_version_id,
        )
        .first()
    )
    if link_exists is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flowsheet version is not linked to project")


def _clear_project_baseline(db: Session, project_id: int, exclude_id: Optional[uuid.UUID] = None) -> None:
    query = db.query(models.CalcScenario).filter(models.CalcScenario.project_id == project_id)
    if exclude_id:
        query = query.filter(models.CalcScenario.id != exclude_id)
    query.update({models.CalcScenario.is_baseline: False}, synchronize_session=False)


def _apply_baseline(db: Session, scenario: models.CalcScenario, is_baseline: bool) -> None:
    if is_baseline:
        _clear_project_baseline(db, project_id=scenario.project_id, exclude_id=scenario.id)
    scenario.is_baseline = is_baseline
    db.add(scenario)


@router.post("", response_model=CalcScenarioRead, status_code=status.HTTP_201_CREATED)
def create_calc_scenario(payload: CalcScenarioCreate, db: Session = Depends(get_db)) -> CalcScenarioRead:
    try:
        get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
        project = _get_project_or_404(db, payload.project_id)
        _ensure_version_linked_to_project(db, project.id, payload.flowsheet_version_id)
        validated_input = validate_input_json(payload.default_input_json)
    except CalculationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    scenario = models.CalcScenario(
        flowsheet_version_id=payload.flowsheet_version_id,
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        default_input_json=validated_input.model_dump(),
        is_baseline=payload.is_baseline,
    )
    db.add(scenario)
    if payload.is_baseline:
        _clear_project_baseline(db, project_id=payload.project_id)
        scenario.is_baseline = True
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/{scenario_id}", response_model=CalcScenarioRead)
def get_calc_scenario(scenario_id: uuid.UUID, db: Session = Depends(get_db)) -> CalcScenarioRead:
    scenario = db.get(models.CalcScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CalcScenario not found")
    return scenario


@router.get(
    "/by-flowsheet-version/{flowsheet_version_id}",
    response_model=CalcScenarioListResponse,
)
def list_calc_scenarios(
    flowsheet_version_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> CalcScenarioListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcScenario).filter(models.CalcScenario.flowsheet_version_id == flowsheet_version_id)
    if project_id is not None:
        _get_project_or_404(db, project_id)
        _ensure_version_linked_to_project(db, project_id, flowsheet_version_id)
        query = query.filter(models.CalcScenario.project_id == project_id)

    total = query.with_entities(func.count()).scalar() or 0
    scenarios = query.order_by(models.CalcScenario.created_at.desc()).offset(offset).limit(limit).all()
    items = [CalcScenarioListItem.model_validate(scenario, from_attributes=True) for scenario in scenarios]
    return CalcScenarioListResponse(items=items, total=total)


@router.get("/by-project/{project_id}", response_model=CalcScenarioListResponse)
def list_calc_scenarios_by_project(
    project_id: int,
    flowsheet_version_id: Optional[uuid.UUID] = Query(None, description="Optional flowsheet version filter"),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> CalcScenarioListResponse:
    project = _get_project_or_404(db, project_id)
    query = db.query(models.CalcScenario).filter(models.CalcScenario.project_id == project.id)
    if flowsheet_version_id:
        get_flowsheet_version_or_404(db, flowsheet_version_id)
        _ensure_version_linked_to_project(db, project.id, flowsheet_version_id)
        query = query.filter(models.CalcScenario.flowsheet_version_id == flowsheet_version_id)

    total = query.with_entities(func.count()).scalar() or 0
    scenarios = query.order_by(models.CalcScenario.created_at.desc()).offset(offset).limit(limit).all()
    items = [CalcScenarioListItem.model_validate(scenario, from_attributes=True) for scenario in scenarios]
    return CalcScenarioListResponse(items=items, total=total)


@router.patch("/{scenario_id}", response_model=CalcScenarioRead)
def update_calc_scenario(
    scenario_id: uuid.UUID,
    payload: CalcScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcScenarioRead:
    scenario = get_calc_scenario_or_404(db, scenario_id)
    project = _get_project_or_404(db, scenario.project_id)
    _check_project_read_access(db, project, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    if "default_input_json" in update_data:
        try:
            validated_input = validate_input_json(update_data["default_input_json"])
        except CalculationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        scenario.default_input_json = validated_input.model_dump()
        update_data.pop("default_input_json")

    baseline_value = update_data.pop("is_baseline", None)

    for field, value in update_data.items():
        setattr(scenario, field, value)

    if baseline_value is not None:
        _apply_baseline(db, scenario, baseline_value)
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.post("/{scenario_id}/set-baseline", response_model=CalcScenarioRead)
def set_baseline_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcScenarioRead:
    scenario = get_calc_scenario_or_404(db, scenario_id)
    project = _get_project_or_404(db, scenario.project_id)
    _check_project_read_access(db, project, current_user)
    _apply_baseline(db, scenario, True)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.post("/{scenario_id}/unset-baseline", response_model=CalcScenarioRead)
def unset_baseline_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CalcScenarioRead:
    scenario = get_calc_scenario_or_404(db, scenario_id)
    project = _get_project_or_404(db, scenario.project_id)
    _check_project_read_access(db, project, current_user)
    _apply_baseline(db, scenario, False)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calc_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    scenario = get_calc_scenario_or_404(db, scenario_id)
    project = _get_project_or_404(db, scenario.project_id)
    _check_project_read_access(db, project, current_user)

    has_runs = (
        db.query(models.CalcRun.id).filter(models.CalcRun.scenario_id == scenario.id).limit(1).first() is not None
    )
    if has_runs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scenario has runs; cannot delete",
        )

    if scenario.is_baseline:
        _clear_project_baseline(db, project_id=scenario.project_id, exclude_id=scenario.id)
    db.delete(scenario)
    db.commit()
    return None
