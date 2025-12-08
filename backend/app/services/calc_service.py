import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.schemas.calc_io import CalcInput, CalcResultSummary
from app.schemas.calc_run import CalcRunCreate, CalcRunRead

logger = logging.getLogger(__name__)


class CalculationError(Exception):
    """Raised for predictable calculation/validation errors."""


class CalcRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


def get_flowsheet_version_or_404(db: Session, flowsheet_version_id):
    """
    Fetch FlowsheetVersion by primary key or raise 404.
    """
    instance = db.get(models.FlowsheetVersion, flowsheet_version_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"FlowsheetVersion {flowsheet_version_id} not found")
    return instance


def get_calc_scenario_or_404(db: Session, scenario_id: uuid.UUID):
    """
    Fetch CalcScenario by primary key or raise 404.
    """
    scenario = db.get(models.CalcScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"CalcScenario {scenario_id} not found")
    return scenario


def validate_input_json(input_json: Any) -> CalcInput:
    if input_json is None:
        raise CalculationError("input_json is required and must be an object")

    if isinstance(input_json, CalcInput):
        model = input_json
    elif isinstance(input_json, dict):
        try:
            model = CalcInput.model_validate(input_json)
        except Exception:
            raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")
    else:
        raise CalculationError("input_json is required and must be an object")

    if model.feed_tph <= 0 or model.target_p80_microns <= 0:
        raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")

    return model


def _persist_status(
    db: Session,
    calc_run: models.CalcRun,
    status: CalcRunStatus,
    finished_at: datetime | None = None,
    result_json: Dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    calc_run.status = status.value
    if finished_at:
        calc_run.finished_at = finished_at
    if result_json is not None:
        calc_run.result_json = result_json
    calc_run.error_message = error_message
    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)


def run_flowsheet_calculation(db: Session, payload: CalcRunCreate) -> CalcRunRead:
    """
    MVP calculation: persist CalcRun, mock result JSON, and update status.
    """
    get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
    validated_input = validate_input_json(payload.input_json)

    started_at = datetime.now(timezone.utc)
    calc_run = models.CalcRun(
        flowsheet_version_id=payload.flowsheet_version_id,
        scenario_name=payload.scenario_name,
        comment=payload.comment,
        status=CalcRunStatus.PENDING.value,
        started_at=started_at,
        input_json=validated_input.model_dump(),
        error_message=None,
    )
    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)

    try:
        _persist_status(db, calc_run, CalcRunStatus.RUNNING)

        result_model = CalcResultSummary(
            throughput_tph=validated_input.feed_tph,
            specific_energy_kwh_per_t=10.0,
            p80_out_microns=validated_input.target_p80_microns,
            circuit_efficiency_index=0.95,
        )
        result_json: Dict[str, Any] = result_model.model_dump()

        _persist_status(
            db,
            calc_run,
            CalcRunStatus.SUCCESS,
            finished_at=datetime.now(timezone.utc),
            result_json=result_json,
            error_message=None,
        )
    except CalculationError as exc:
        _persist_status(
            db,
            calc_run,
            CalcRunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_message=str(exc),
        )
        raise
    except Exception as exc:  # pragma: no cover - unexpected error branch
        _persist_status(
            db,
            calc_run,
            CalcRunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_message="Internal calculation error",
        )
        logger.exception("Unexpected calculation error")
        raise
    return CalcRunRead.model_validate(calc_run, from_attributes=True)


def run_flowsheet_calculation_by_scenario(db: Session, scenario_id: uuid.UUID) -> CalcRunRead:
    """
    Run calculation using stored CalcScenario defaults.
    """
    scenario = get_calc_scenario_or_404(db, scenario_id)
    validated_input = validate_input_json(scenario.default_input_json)
    payload = CalcRunCreate(
        flowsheet_version_id=scenario.flowsheet_version_id,
        scenario_name=scenario.name,
        input_json=validated_input,
    )
    return run_flowsheet_calculation(db=db, payload=payload)
