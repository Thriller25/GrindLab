import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas.calc_scenario import (
    CalcScenarioCreate,
    CalcScenarioListItem,
    CalcScenarioListResponse,
    CalcScenarioRead,
    CalcScenarioUpdate,
)
from app.services.calc_service import CalculationError, get_flowsheet_version_or_404, validate_input_json

router = APIRouter(prefix="/api/calc-scenarios", tags=["calc-scenarios"])


@router.post("/", response_model=CalcScenarioRead, status_code=status.HTTP_201_CREATED)
def create_calc_scenario(payload: CalcScenarioCreate, db: Session = Depends(get_db)) -> CalcScenarioRead:
    try:
        get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
        validated_input = validate_input_json(payload.default_input_json)
    except CalculationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    scenario = models.CalcScenario(
        flowsheet_version_id=payload.flowsheet_version_id,
        name=payload.name,
        description=payload.description,
        default_input_json=validated_input.model_dump(),
    )
    db.add(scenario)
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
    db: Session = Depends(get_db),
) -> CalcScenarioListResponse:
    get_flowsheet_version_or_404(db, flowsheet_version_id)
    query = db.query(models.CalcScenario).filter(models.CalcScenario.flowsheet_version_id == flowsheet_version_id)

    total = query.with_entities(func.count()).scalar() or 0
    scenarios = query.order_by(models.CalcScenario.created_at.desc()).offset(offset).limit(limit).all()
    items = [CalcScenarioListItem.model_validate(scenario, from_attributes=True) for scenario in scenarios]
    return CalcScenarioListResponse(items=items, total=total)


@router.patch("/{scenario_id}", response_model=CalcScenarioRead)
def update_calc_scenario(
    scenario_id: uuid.UUID, payload: CalcScenarioUpdate, db: Session = Depends(get_db)
) -> CalcScenarioRead:
    scenario = db.get(models.CalcScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CalcScenario not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "default_input_json" in update_data:
        try:
            validated_input = validate_input_json(update_data["default_input_json"])
        except CalculationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        scenario.default_input_json = validated_input.model_dump()
        update_data.pop("default_input_json")

    for field, value in update_data.items():
        setattr(scenario, field, value)

    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calc_scenario(scenario_id: uuid.UUID, db: Session = Depends(get_db)):
    scenario = db.get(models.CalcScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CalcScenario not found")
    db.delete(scenario)
    db.commit()
    return None
